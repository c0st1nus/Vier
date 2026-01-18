import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.core.config import settings
from app.schemas.models import (
    ProcessingStage,
    ProcessingTask,
    TaskStatus,
    VideoMetadata,
    VideoSegment,
)
from app.services.asr_service import ASRService
from app.services.llm_service import LLMService
from app.services.vision_service import VisionService
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

# Global task storage (in production, use Redis or database)
TASKS: Dict[str, ProcessingTask] = {}


class VideoPipeline:
    """Main pipeline for processing videos and generating quizzes"""

    def __init__(self):
        self.asr_service = ASRService()
        self.vision_service = VisionService()
        self.llm_service = LLMService()

    async def process_video(
        self, task_id: str, video_path: Path, source_url: Optional[str] = None
    ) -> ProcessingTask:
        """
        Main video processing pipeline

        Args:
            task_id: Unique task identifier
            video_path: Path to video file
            source_url: Optional source URL (for YouTube videos)

        Returns:
            Completed ProcessingTask
        """
        task = TASKS.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        try:
            logger.info(f"Starting pipeline for task {task_id}")

            # Stage 1: Validate video
            self._update_task_status(
                task_id,
                TaskStatus.PENDING,
                0.0,
                ProcessingStage.DOWNLOAD,
                "Validating video file",
            )
            validate_video_file(video_path)
            task.video_path = str(video_path)

            # Stage 2: Extract metadata
            self._update_task_status(
                task_id, TaskStatus.EXTRACTING_AUDIO, 10.0, None, "Extracting metadata"
            )
            metadata = get_video_metadata(video_path)
            task.metadata = metadata
            logger.info(f"Video duration: {metadata.duration:.2f}s")

            # Stage 3: Extract audio
            self._update_task_status(
                task_id,
                TaskStatus.EXTRACTING_AUDIO,
                15.0,
                ProcessingStage.AUDIO_EXTRACTION,
                "Extracting audio track",
            )
            audio_path = settings.TEMP_DIR / f"{task_id}_audio.wav"
            extract_audio(video_path, audio_path)
            task.audio_path = str(audio_path)
            logger.info(f"Audio extracted: {audio_path}")

            # Stage 4: Transcribe audio
            self._update_task_status(
                task_id,
                TaskStatus.TRANSCRIBING,
                25.0,
                ProcessingStage.TRANSCRIPTION,
                "Transcribing audio (this may take a few minutes)",
            )
            try:
                transcription = self.asr_service.transcribe(audio_path)
                task.transcription = transcription
                logger.info(f"Transcription completed: {len(transcription)} segments")
            finally:
                # Unload ASR model to free VRAM
                self.asr_service.unload_model()
                clear_vram()

            # Stage 5: Extract and analyze frames
            self._update_task_status(
                task_id,
                TaskStatus.ANALYZING_FRAMES,
                50.0,
                ProcessingStage.FRAME_ANALYSIS,
                "Analyzing video frames",
            )
            frames_dir = settings.TEMP_DIR / f"{task_id}_frames"
            frame_paths = extract_frames(video_path, frames_dir)
            logger.info(f"Extracted {len(frame_paths)} frames")

            try:
                frame_analyses = self.vision_service.analyze_frames(frame_paths)
                task.frame_analyses = frame_analyses
                logger.info(f"Frame analysis completed: {len(frame_analyses)} frames")
            finally:
                # Unload vision model to free VRAM
                self.vision_service.unload_model()
                clear_vram()

            # Stage 6: Segment video and generate quizzes
            self._update_task_status(
                task_id,
                TaskStatus.GENERATING_QUIZZES,
                70.0,
                ProcessingStage.SEGMENTATION,
                "Segmenting content and generating quizzes",
            )
            try:
                segments = self.llm_service.segment_and_generate_quizzes(
                    transcription, frame_analyses, metadata.duration
                )
                task.segments = segments
                logger.info(f"Generated {len(segments)} segments with quizzes")
            finally:
                # Unload LLM model to free VRAM
                self.llm_service.unload_model()
                clear_vram()

            # Stage 7: Finalization
            self._update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                100.0,
                ProcessingStage.FINALIZATION,
                "Processing completed successfully",
            )

            # Cleanup temporary files
            logger.info("Cleaning up temporary files")
            cleanup_temp_files(audio_path, frames_dir)

            logger.info(f"Pipeline completed successfully for task {task_id}")
            return task

        except Exception as e:
            logger.error(f"Pipeline failed for task {task_id}: {e}", exc_info=True)
            self._update_task_status(
                task_id, TaskStatus.FAILED, task.progress, None, f"Error: {str(e)}"
            )
            task.error = str(e)
            raise

        finally:
            # Ensure all models are unloaded
            try:
                self.asr_service.unload_model()
                self.vision_service.unload_model()
                self.llm_service.unload_model()
                clear_vram()
            except Exception as e:
                logger.warning(f"Error during model cleanup: {e}")

    def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float,
        stage: Optional[ProcessingStage],
        message: Optional[str] = None,
    ):
        """Update task status in storage"""
        task = TASKS.get(task_id)
        if task:
            task.status = status
            task.progress = progress
            if stage:
                task.current_stage = stage
            if message:
                logger.info(f"Task {task_id}: {message}")
            task.updated_at = datetime.utcnow()


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


async def process_video_from_file(task_id: str, file_path: Path) -> ProcessingTask:
    """
    Process video from uploaded file

    Args:
        task_id: Task identifier
        file_path: Path to uploaded video file

    Returns:
        Completed ProcessingTask
    """
    pipeline = VideoPipeline()
    return await pipeline.process_video(task_id, file_path)


async def process_video_from_url(task_id: str, url: str) -> ProcessingTask:
    """
    Process video from URL (YouTube, etc.)

    Args:
        task_id: Task identifier
        url: Video URL

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

        # Process the downloaded video
        pipeline = VideoPipeline()
        return await pipeline.process_video(task_id, video_path, source_url=url)

    except Exception as e:
        logger.error(f"Failed to process video from URL: {e}")
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.updated_at = datetime.utcnow()
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
