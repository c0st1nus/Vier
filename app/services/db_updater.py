"""Database updater utility for syncing pipeline status with database."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.db.models import (
    ProcessingStatus as DBProcessingStatus,
)
from app.db.models import (
    Quiz,
    Segment,
    Video,
)
from app.db.models import (
    TaskStatus as DBTaskStatus,
)
from app.db.session import AsyncSessionLocal, get_redis
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class DBUpdater:
    """Utility class for updating task status in database from pipeline."""

    @staticmethod
    async def update_status(
        task_id: str,
        status: str,
        progress: Optional[float] = None,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update task status in database."""
        try:
            async with AsyncSessionLocal() as db:
                redis = await get_redis()
                task_service = TaskService(db, redis)

                # Map pipeline status to DB status
                status_map = {
                    "pending": DBTaskStatus.PENDING,
                    "processing": DBTaskStatus.PROCESSING,
                    "completed": DBTaskStatus.COMPLETED,
                    "failed": DBTaskStatus.FAILED,
                }

                db_status = status_map.get(status, DBTaskStatus.PROCESSING)

                await task_service.update_task_status(
                    task_id=task_id,
                    status=db_status,
                    progress=progress,
                    current_stage=current_stage,
                    error_message=error_message,
                )

                try:
                    task_uuid = UUID(task_id)
                except Exception:
                    task_uuid = task_id
                try:
                    video_result = await db.execute(
                        select(Video).where(Video.task_id == task_uuid)
                    )
                    video = video_result.scalar_one_or_none()
                    if video:
                        video_status_map = {
                            DBTaskStatus.PENDING: DBProcessingStatus.PENDING,
                            DBTaskStatus.PROCESSING: DBProcessingStatus.PROCESSING,
                            DBTaskStatus.COMPLETED: DBProcessingStatus.COMPLETED,
                            DBTaskStatus.FAILED: DBProcessingStatus.FAILED,
                        }
                        video.status = video_status_map.get(
                            db_status, video.status or DBProcessingStatus.PROCESSING
                        )
                        if progress is not None:
                            video.progress = progress
                        if current_stage is not None:
                            video.current_stage = current_stage
                        if error_message:
                            video.error_message = error_message
                        if (
                            video.status == DBProcessingStatus.PROCESSING
                            and not video.started_at
                        ):
                            video.started_at = datetime.utcnow()
                        if video.status in (
                            DBProcessingStatus.COMPLETED,
                            DBProcessingStatus.FAILED,
                        ):
                            video.completed_at = datetime.utcnow()
                        await db.commit()
                        await db.refresh(video)
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        f"Failed to update video {task_id} status in database: {e}"
                    )

                logger.debug(f"Updated task {task_id} status to {status} in database")

        except Exception as e:
            logger.error(f"Failed to update task {task_id} status in database: {e}")

    @staticmethod
    async def update_results(
        task_id: str,
        segments: list,
        duration: Optional[float] = None,
        video_metadata: Optional[dict] = None,
    ):
        """Update task results in database."""
        try:
            async with AsyncSessionLocal() as db:
                redis = await get_redis()
                task_service = TaskService(db, redis)

                await task_service.update_task_results(
                    task_id=task_id,
                    segments=segments,
                    duration=duration,
                    video_metadata=video_metadata,
                )

                try:
                    task_uuid = UUID(task_id)
                except Exception:
                    task_uuid = task_id
                try:
                    video_result = await db.execute(
                        select(Video).where(Video.task_id == task_uuid)
                    )
                    video = video_result.scalar_one_or_none()
                    if video:
                        video.status = DBProcessingStatus.COMPLETED
                        video.progress = 100.0
                        video.current_stage = "Completed"
                        if duration:
                            video.duration = duration
                        if video_metadata:
                            video.width = video_metadata.get("width")
                            video.height = video_metadata.get("height")
                            video.fps = video_metadata.get("fps")
                        video.completed_at = datetime.utcnow()

                        # Replace existing segments/quizzes with new ones without lazy loads
                        result = await db.execute(
                            select(Segment).where(Segment.video_id == video.id)
                        )
                        existing_segments = list(result.scalars().all())
                        for seg in existing_segments:
                            await db.delete(seg)
                        if existing_segments:
                            await db.flush()

                        for idx, seg in enumerate(segments or [], start=1):
                            translations = seg.get("translations") or {}
                            ru_tr = translations.get("ru", {})
                            topic_title = seg.get("topic_title") or ru_tr.get(
                                "topic_title"
                            )
                            short_summary = seg.get("short_summary") or ru_tr.get(
                                "short_summary"
                            )
                            keywords = seg.get("keywords")

                            segment_obj = Segment(
                                video_id=video.id,
                                segment_id=seg.get("segment_id") or idx,
                                start_time=int(seg.get("start_time") or 0),
                                end_time=int(seg.get("end_time") or 0),
                                topic_title=topic_title,
                                short_summary=short_summary,
                                keywords=keywords,
                            )

                            quizzes = seg.get("quizzes") or []
                            for quiz in quizzes:
                                q_translations = quiz.get("translations") or {}
                                ru_q = q_translations.get("ru", {})
                                question = quiz.get("question") or ru_q.get("question")
                                options = (
                                    quiz.get("options") or ru_q.get("options") or []
                                )
                                explanation = (
                                    quiz.get("explanation")
                                    or ru_q.get("explanation")
                                    or None
                                )
                                segment_obj.quizzes.append(
                                    Quiz(
                                        question=question,
                                        options=list(options),
                                        correct_index=int(
                                            quiz.get("correct_index") or 0
                                        ),
                                        explanation=explanation,
                                        language=quiz.get("language") or "ru",
                                    )
                                )

                            db.add(segment_obj)

                        await db.commit()
                        await db.refresh(video)
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        f"Failed to update video {task_id} results in database: {e}"
                    )

                logger.info(
                    f"Updated task {task_id} results in database: {len(segments)} segments"
                )

        except Exception as e:
            logger.error(f"Failed to update task {task_id} results in database: {e}")

    @staticmethod
    async def set_processing_started(task_id: str):
        """Mark task as started processing."""
        await DBUpdater.update_status(
            task_id, "processing", progress=0.0, current_stage="Starting"
        )

    @staticmethod
    async def set_stage_progress(task_id: str, stage: str, progress: float):
        """Update task progress for a specific stage."""
        await DBUpdater.update_status(
            task_id, "processing", progress=progress, current_stage=stage
        )
        logger.debug(f"Task {task_id} - {stage}: {progress}%")

    @staticmethod
    async def set_completed(
        task_id: str,
        segments: list,
        duration: Optional[float] = None,
        video_metadata: Optional[dict] = None,
    ):
        """Mark task as completed with results."""
        # Update status first
        await DBUpdater.update_status(
            task_id, "completed", progress=100.0, current_stage="Completed"
        )

        # Then update results
        await DBUpdater.update_results(
            task_id=task_id,
            segments=segments,
            duration=duration,
            video_metadata=video_metadata,
        )

        logger.info(f"Task {task_id} marked as completed in database")

    @staticmethod
    async def set_failed(task_id: str, error_message: str):
        """Mark task as failed with error message."""
        await DBUpdater.update_status(
            task_id,
            "failed",
            progress=0.0,
            current_stage="Failed",
            error_message=error_message,
        )
        logger.error(f"Task {task_id} marked as failed in database: {error_message}")

    @staticmethod
    async def update_video_title(task_id: str, video_title: str):
        """Update video title in database."""
        try:
            async with AsyncSessionLocal() as db:
                redis = await get_redis()
                task_service = TaskService(db, redis)
                await task_service.update_video_title(task_id, video_title)

                try:
                    task_uuid = UUID(task_id)
                except Exception:
                    task_uuid = task_id
                try:
                    video_result = await db.execute(
                        select(Video).where(Video.task_id == task_uuid)
                    )
                    video = video_result.scalar_one_or_none()
                    if video:
                        video.title = video_title
                        await db.commit()
                        await db.refresh(video)
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        f"Failed to update video title for task {task_id}: {e}"
                    )

                logger.info(f"Updated video title for task {task_id}: {video_title}")
        except Exception as e:
            logger.error(f"Failed to update video title for task {task_id}: {e}")

    @staticmethod
    async def get_task_from_db(task_id: str):
        """Get task from database."""
        try:
            async with AsyncSessionLocal() as db:
                redis = await get_redis()
                task_service = TaskService(db, redis)
                return await task_service.get_task(task_id)
        except Exception as e:
            logger.error(f"Failed to get task {task_id} from database: {e}")
            return None
