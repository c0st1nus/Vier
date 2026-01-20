"""Database updater utility for syncing pipeline status with database."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.db.models import TaskStatus as DBTaskStatus
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
