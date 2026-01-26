import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, cast

from app.core.config import settings
from app.schemas.models import (
    ProcessingStage,
    ProcessingTask,
    TaskStatus,
    VideoMetadata,
    VideoSegment,
)
from app.services.asr_service import ASRService
from app.services.db_updater import DBUpdater
from app.services.llm_service import LLMService
from app.services.storage_service import storage_service
from app.services.vision_service import VisionService
from app.services.websocket_manager import websocket_manager

# Import vLLM service if enabled
if settings.USE_VLLM:
    from app.services.vllm_service import VLLMService
else:
    VLLMService = None  # type: ignore[assignment]
from app.utils.video_utils import (
    cleanup_temp_files,
    clear_vram,
    download_youtube_video,
    extract_audio,
    extract_frames,
    get_video_metadata,
    validate_video_file,
)

logger = logging.getLogger(__name__)

# Global task storage (in-memory cache, DB is source of truth)
TASKS: Dict[str, ProcessingTask] = {}


def run_in_threadpool(func, *args, **kwargs):
    """Run blocking function in thread pool"""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result()


class VideoPipeline:
    """Main pipeline for processing videos and generating quizzes"""

    def __init__(self):
        self.asr_service = ASRService()
        self.vision_service = VisionService()

        # Use vLLM or Ollama based on configuration
        if settings.USE_VLLM:
            logger.info("Using vLLM for LLM inference (faster)")
            if VLLMService is None:
                raise RuntimeError("USE_VLLM is True but VLLMService is unavailable")
            self.llm_service = VLLMService()
        else:
            logger.info("Using Ollama for LLM inference")
            self.llm_service = LLMService()

        self.models_preloaded = False

        # Preload all models if configured
        if settings.PRELOAD_ALL_MODELS:
            logger.info("🚀 Preloading all models (PRODUCTION mode)")
            self._preload_all_models()

    def _preload_all_models(self):
        """Preload all models into VRAM for faster processing"""
        try:
            logger.info("Loading ASR model...")
            self.asr_service.load_model()

            logger.info("Loading Vision model...")
            self.vision_service.load_model()

            logger.info("Loading LLM model...")
            self.llm_service.load_model()

            self.models_preloaded = True
            logger.info("✅ All models preloaded successfully")

            # Log VRAM usage
            from app.utils.video_utils import get_vram_usage

            allocated, reserved = get_vram_usage()
            logger.info(
                f"Total VRAM usage: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
            )

        except Exception as e:
            logger.error(f"Failed to preload models: {e}")
            self.models_preloaded = False
            raise

    def _maybe_unload_models(self):
        """Unload models if not in PRELOAD mode"""
        if not settings.MODELS_STAY_IN_MEMORY:
            logger.info("Unloading models to free VRAM")
            try:
                self.asr_service.unload_model()
                self.vision_service.unload_model()
                self.llm_service.unload_model()
                clear_vram()
            except Exception as e:
                logger.warning(f"Error during model cleanup: {e}")

    async def process_video(
        self,
        task_id: str,
        video_path: Path,
        source_url: Optional[str] = None,
        language: str = "ru",
    ) -> ProcessingTask:
        """
        Main video processing pipeline

        Args:
            task_id: Unique task identifier
            video_path: Path to video file
            source_url: Optional source URL (for YouTube videos)
            language: Language for quizzes (ru, en, kk)

        Returns:
            Completed ProcessingTask
        """
        task = TASKS.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        try:
            logger.info(f"Starting pipeline for task {task_id}")

            # Stage 1: Validate video
            await self._update_task_status(
                task_id,
                TaskStatus.PENDING,
                0.0,
                ProcessingStage.DOWNLOAD,
                "Validating video file",
            )
            await DBUpdater.set_processing_started(task_id)
            await asyncio.to_thread(validate_video_file, video_path)
            task.video_path = str(video_path)

            # Stage 2: Extract metadata
            await self._update_task_status(
                task_id,
                TaskStatus.EXTRACTING_AUDIO,
                10.0,
                ProcessingStage.AUDIO_EXTRACTION,
                "Extracting metadata",
            )
            await DBUpdater.set_stage_progress(task_id, "Extracting metadata", 10.0)
            metadata = await asyncio.to_thread(get_video_metadata, video_path)
            task.metadata = metadata
            logger.info(f"Video duration: {metadata.duration:.2f}s")

            # Stage 3: Extract audio
            await self._update_task_status(
                task_id,
                TaskStatus.EXTRACTING_AUDIO,
                15.0,
                ProcessingStage.AUDIO_EXTRACTION,
                "Extracting audio track",
            )
            await DBUpdater.set_stage_progress(task_id, "Extracting audio track", 15.0)
            audio_path = settings.TEMP_DIR / f"{task_id}_audio.wav"
            await asyncio.to_thread(extract_audio, video_path, audio_path)
            task.audio_path = str(audio_path)
            logger.info(f"Audio extracted: {audio_path}")

            # Stage 4: Transcribe audio
            await self._update_task_status(
                task_id,
                TaskStatus.TRANSCRIBING,
                25.0,
                ProcessingStage.TRANSCRIPTION,
                "Transcribing audio (this may take a few minutes)",
            )
            await DBUpdater.set_stage_progress(task_id, "Transcribing audio", 25.0)
            transcription = await asyncio.to_thread(
                self.asr_service.transcribe, audio_path
            )
            task.transcription = transcription
            logger.info(f"Transcription completed: {len(transcription)} segments")

            # Unload ASR model to free VRAM (only if not keeping in memory)
            if not settings.MODELS_STAY_IN_MEMORY:
                await asyncio.to_thread(self.asr_service.unload_model)
                await asyncio.to_thread(clear_vram)

            # Stage 5: Extract and analyze frames
            await self._update_task_status(
                task_id,
                TaskStatus.ANALYZING_FRAMES,
                50.0,
                ProcessingStage.FRAME_ANALYSIS,
                "Analyzing video frames",
            )
            await DBUpdater.set_stage_progress(task_id, "Analyzing video frames", 50.0)
            frames_dir = settings.TEMP_DIR / f"{task_id}_frames"
            frame_paths = await asyncio.to_thread(
                extract_frames, video_path, frames_dir
            )
            logger.info(f"Extracted {len(frame_paths)} frames")

            frame_analyses = await asyncio.to_thread(
                self.vision_service.analyze_frames, frame_paths
            )
            task.frame_analyses = frame_analyses
            logger.info(f"Frame analysis completed: {len(frame_analyses)} frames")

            # Unload vision model to free VRAM (only if not keeping in memory)
            if not settings.MODELS_STAY_IN_MEMORY:
                await asyncio.to_thread(self.vision_service.unload_model)
                await asyncio.to_thread(clear_vram)

            # Stage 6: Segment video and generate quizzes
            await self._update_task_status(
                task_id,
                TaskStatus.GENERATING_QUIZZES,
                70.0,
                ProcessingStage.SEGMENTATION,
                "Segmenting content and generating quizzes",
            )
            await DBUpdater.set_stage_progress(task_id, "Generating quizzes", 70.0)
            segments = await asyncio.to_thread(
                cast(Callable[..., Any], self.llm_service.segment_and_generate_quizzes),
                transcription,
                frame_analyses,
                metadata.duration,
                language,
            )
            task.segments = segments
            logger.info(f"Generated {len(segments)} segments with quizzes")

            for seg in segments:
                await websocket_manager.send_to_task(
                    task_id,
                    {
                        "event": "segment_ready",
                        "segment": seg.dict(),
                    },
                )

            # Generate video title
            logger.info("Generating video title")
            video_title = await asyncio.to_thread(
                cast(Callable[..., Any], self.llm_service.generate_video_title),
                transcription,
                frame_analyses,
                metadata.duration,
                language,
            )
            logger.info(f"Generated video title: {video_title}")

            # Update task with video title in database
            await DBUpdater.update_video_title(task_id, video_title)

            # Unload LLM model to free VRAM (only if not keeping in memory)
            if not settings.MODELS_STAY_IN_MEMORY:
                await asyncio.to_thread(self.llm_service.unload_model)
                await asyncio.to_thread(clear_vram)

            # Stage 7: Finalization
            await self._update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                100.0,
                ProcessingStage.FINALIZATION,
                "Processing completed successfully",
            )

            # Update database with results
            segments_json = [seg.dict() for seg in task.segments]
            video_metadata_dict = {
                "duration": metadata.duration,
                "width": metadata.width,
                "height": metadata.height,
                "fps": metadata.fps,
            }
            await DBUpdater.set_completed(
                task_id=task_id,
                segments=segments_json,
                duration=metadata.duration,
                video_metadata=video_metadata_dict,
            )

            logger.info(
                f"Sending 'completed' WebSocket event for task {task_id} with {len(segments_json)} segments"
            )
            await websocket_manager.send_to_task(
                task_id,
                {
                    "event": "completed",
                    "total_segments": len(segments_json),
                    "message": "Video processing completed",
                },
            )
            logger.info(
                f"'completed' WebSocket event sent successfully for task {task_id}"
            )

            # Upload video to S3 if enabled (before cleanup)
            if settings.S3_ENABLED and video_path.exists():
                try:
                    logger.info(f"Uploading video to S3 for task {task_id}")
                    s3_key = storage_service.get_object_key_for_task(
                        task_id, video_path.name
                    )

                    # Detect content type
                    ext = video_path.suffix.lower()
                    content_type_map = {
                        ".mp4": "video/mp4",
                        ".avi": "video/x-msvideo",
                        ".mov": "video/quicktime",
                        ".mkv": "video/x-matroska",
                        ".webm": "video/webm",
                        ".flv": "video/x-flv",
                    }
                    content_type = content_type_map.get(ext, "video/mp4")

                    await storage_service.upload_file(
                        video_path,
                        s3_key,
                        content_type=content_type,
                        metadata={"task_id": task_id},
                    )
                    logger.info(f"Video uploaded to S3: {s3_key}")

                    # Update database with S3 path
                    from uuid import UUID

                    from sqlalchemy import select, update

                    from app.db.models import Video
                    from app.db.session import AsyncSessionLocal
                    from app.services.task_service import TaskService

                    async with AsyncSessionLocal() as db:
                        # Update old Task model
                        task_service = TaskService(db, None)
                        await task_service.update_task_path(
                            task_id=task_id,
                            video_path=s3_key,
                            file_size=video_path.stat().st_size,
                            original_filename=video_path.name,
                        )

                        # Update new Video model
                        try:
                            task_uuid = UUID(task_id)
                            result = await db.execute(
                                select(Video).where(Video.task_id == task_uuid)
                            )
                            video = result.scalar_one_or_none()
                            if video:
                                await db.execute(
                                    update(Video)
                                    .where(Video.task_id == task_uuid)
                                    .values(file_path=s3_key)
                                )
                                await db.commit()
                                logger.info(
                                    f"Updated Video model with S3 path: {s3_key}"
                                )
                        except Exception as e:
                            logger.error(f"Failed to update Video model: {e}")

                    logger.info(f"Updated database with S3 path: {s3_key}")
                except Exception as e:
                    logger.error(f"Failed to upload video to S3: {e}")
                    logger.warning("Video will remain in local storage")

            # Cleanup temporary files (including video if uploaded to S3)
            logger.info("Cleaning up temporary files")
            if settings.S3_ENABLED and video_path.exists():
                # Video was uploaded to S3, safe to delete local copy
                await asyncio.to_thread(
                    cleanup_temp_files, audio_path, frames_dir, video_path
                )
            else:
                # Keep video locally if S3 is disabled or upload failed
                await asyncio.to_thread(cleanup_temp_files, audio_path, frames_dir)

            logger.info(f"Pipeline completed successfully for task {task_id}")
            return task

        except Exception as e:
            logger.error(f"Pipeline failed for task {task_id}: {e}", exc_info=True)
            await self._update_task_status(
                task_id, TaskStatus.FAILED, 0.0, None, f"Error: {str(e)}"
            )
            task.error = str(e)
            await DBUpdater.set_failed(task_id, str(e))
            raise

        finally:
            # Ensure all models are unloaded (only if not keeping in memory)
            if not settings.MODELS_STAY_IN_MEMORY:
                try:
                    await asyncio.to_thread(self.asr_service.unload_model)
                    await asyncio.to_thread(self.vision_service.unload_model)
                    await asyncio.to_thread(self.llm_service.unload_model)
                    await asyncio.to_thread(clear_vram)
                except Exception as e:
                    logger.warning(f"Error during model cleanup: {e}")

    async def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float,
        stage: Optional[ProcessingStage],
        message: Optional[str] = None,
    ):
        """Update task status in storage and DB"""
        task = TASKS.get(task_id)
        if task:
            task.status = status
            task.progress = progress
            if stage:
                task.current_stage = stage
            if message:
                logger.info(f"Task {task_id}: {message}")
            task.updated_at = datetime.utcnow()

            try:
                await websocket_manager.send_to_task(
                    task_id,
                    {
                        "event": "progress",
                        "progress": progress or 0.0,
                        "current_stage": stage.value if stage else None,
                        "message": message,
                    },
                )
            except Exception:
                logger.debug("WS progress send failed for task %s", task_id)


# Task management functions
def create_task(
    video_path: Optional[str] = None, source_url: Optional[str] = None
) -> str:
    """
    Create a new processing task

    Args:
        video_path: Path to video file
        source_url: Optional source URL

    Returns:
        Task ID
    """
    task_id = str(uuid.uuid4())

    metadata = None
    if source_url:
        metadata = VideoMetadata(
            duration=0.0,
            fps=0.0,
            width=0,
            height=0,
            format="unknown",
            source_url=source_url,
        )

    task = ProcessingTask(
        task_id=task_id,
        status=TaskStatus.PENDING,
        video_path=video_path,
        metadata=metadata,
    )

    TASKS[task_id] = task
    logger.info(f"Created task {task_id}")
    return task_id


def get_task(task_id: str) -> Optional[ProcessingTask]:
    """Get task by ID"""
    return TASKS.get(task_id)


def get_task_status(task_id: str) -> Optional[dict]:
    """Get task status information"""
    task = TASKS.get(task_id)
    if not task:
        return None

    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "current_stage": task.current_stage.value if task.current_stage else None,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def get_task_segments(task_id: str) -> Optional[list[VideoSegment]]:
    """Get processed segments for a task"""
    task = TASKS.get(task_id)
    if not task or task.status != TaskStatus.COMPLETED:
        return None

    return task.segments


async def process_video_from_file(task_id: str, file_path: Path, language: str = "ru"):
    """
    Process video from uploaded file (runs in background)

    Args:
        task_id: Task identifier
        file_path: Path to uploaded video file
        language: Language for quizzes (ru, en, kk)

    Returns:
        Completed ProcessingTask
    """
    pipeline = VideoPipeline()
    return await pipeline.process_video(task_id, file_path, language=language)


async def process_video_from_url(
    task_id: str, url: str, language: str = "ru"
) -> ProcessingTask:
    """
    Process video from URL (YouTube, etc.)

    Args:
        task_id: Task identifier
        url: Video URL
        language: Language for quizzes (ru, en, kk)

    Returns:
        Completed ProcessingTask
    """
    task = TASKS.get(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    try:
        # Update status
        task.status = TaskStatus.DOWNLOADING
        task.progress = 5.0
        task.current_stage = ProcessingStage.DOWNLOAD
        task.updated_at = datetime.utcnow()
        logger.info(f"Downloading video from URL: {url}")

        # Download video
        download_dir = settings.TEMP_DIR / task_id
        video_path = download_youtube_video(url, download_dir)

        # Update database with downloaded video path
        file_size = video_path.stat().st_size if video_path.exists() else None
        from app.db.session import AsyncSessionLocal, get_redis
        from app.services.task_service import TaskService

        async with AsyncSessionLocal() as db:
            redis = await get_redis()
            task_service = TaskService(db, redis)
            await task_service.update_task_path(
                task_id=task_id,
                video_path=str(video_path),
                file_size=file_size,
                original_filename=video_path.name,
            )
            logger.info(f"Updated database with downloaded video path: {video_path}")

        # Process the downloaded video
        pipeline = VideoPipeline()
        return await pipeline.process_video(
            task_id, video_path, source_url=url, language=language
        )

    except Exception as e:
        logger.error(f"Failed to process video from URL: {e}")
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.updated_at = datetime.utcnow()
        await DBUpdater.set_failed(task_id, str(e))
        raise


def cleanup_old_tasks(max_age_seconds: int = 86400):
    """
    Clean up old completed/failed tasks

    Args:
        max_age_seconds: Maximum age in seconds (default: 24 hours)
    """
    now = datetime.utcnow()
    to_remove = []

    for task_id, task in TASKS.items():
        age = (now - task.updated_at).total_seconds()
        if age > max_age_seconds and task.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
        ]:
            to_remove.append(task_id)

            # Clean up associated files
            try:
                if task.video_path:
                    video_path = Path(task.video_path)
                    if video_path.exists():
                        cleanup_temp_files(video_path)

                if task.audio_path:
                    audio_path = Path(task.audio_path)
                    if audio_path.exists():
                        cleanup_temp_files(audio_path)
            except Exception as e:
                logger.warning(f"Error cleaning up files for task {task_id}: {e}")

    for task_id in to_remove:
        del TASKS[task_id]
        logger.info(f"Cleaned up old task {task_id}")

    logger.info(f"Cleanup completed: removed {len(to_remove)} tasks")
