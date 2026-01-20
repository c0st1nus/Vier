"""Task service for database operations and Redis caching."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Task, TaskStatus
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks in database and cache."""

    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def create_task(
        self,
        task_id: str,
        original_filename: str,
        video_path: str,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
    ) -> Task:
        """Create a new task in the database."""
        task = Task(
            id=task_id,
            original_filename=original_filename,
            video_path=video_path,
            file_size=file_size,
            file_hash=file_hash,
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # Cache task status in Redis
        if self.redis:
            await self._cache_task_status(task)

        logger.info(f"Created task {task_id} for file {original_filename}")
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        # Try cache first
        if self.redis:
            cached_status = await self._get_cached_task_status(task_id)
            if cached_status:
                logger.debug(f"Task {task_id} status from cache: {cached_status}")

        # Get from database
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if task and self.redis:
            # Update cache
            await self._cache_task_status(task)

        return task

    async def get_all_tasks(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        """Get all tasks with optional filtering."""
        query = select(Task).order_by(Task.created_at.desc())

        if status:
            query = query.where(Task.status == status)

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Task]:
        """Update task status and progress."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = status
        task.updated_at = datetime.utcnow()

        if progress is not None:
            task.progress = progress

        if current_stage is not None:
            task.current_stage = current_stage

        if error_message:
            task.error_message = error_message

        if status == TaskStatus.PROCESSING and not task.started_at:
            task.started_at = datetime.utcnow()

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.utcnow()
            task.progress = 100.0 if status == TaskStatus.COMPLETED else task.progress

        await self.db.commit()
        await self.db.refresh(task)

        # Update cache
        if self.redis:
            await self._cache_task_status(task)

        logger.info(f"Updated task {task_id} status to {status.value}")
        return task

    async def update_task_results(
        self,
        task_id: str,
        segments: list,
        duration: Optional[float] = None,
        video_metadata: Optional[dict] = None,
    ) -> Optional[Task]:
        """Update task with processing results."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.segments_json = segments
        task.total_segments = len(segments)
        task.total_quizzes = sum(len(seg.get("quizzes", [])) for seg in segments)
        task.updated_at = datetime.utcnow()

        if duration:
            task.duration = duration

        if video_metadata:
            task.width = video_metadata.get("width")
            task.height = video_metadata.get("height")
            task.fps = video_metadata.get("fps")

        await self.db.commit()
        await self.db.refresh(task)

        # Clear cache to force reload
        if self.redis:
            await self._invalidate_task_cache(task_id)

        logger.info(
            f"Updated task {task_id} results: {task.total_segments} segments, "
            f"{task.total_quizzes} quizzes"
        )
        return task

    async def update_task_path(
        self,
        task_id: str,
        video_path: str,
        file_size: Optional[int] = None,
        original_filename: Optional[str] = None,
    ) -> Optional[Task]:
        """Update task video path after download."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.video_path = video_path
        task.updated_at = datetime.utcnow()

        if file_size is not None:
            task.file_size = file_size

        if original_filename:
            task.original_filename = original_filename

        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Updated task {task_id} video path to {video_path}")
        return task

    async def update_video_title(
        self, task_id: str, video_title: str
    ) -> Optional[Task]:
        """Update video title."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.video_title = video_title
        task.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Updated task {task_id} video title to: {video_title}")
        return task

    async def find_duplicate_by_hash(self, file_hash: str) -> Optional[Task]:
        """Find completed task with same file hash."""
        result = await self.db.execute(
            select(Task)
            .where(Task.file_hash == file_hash)
            .where(Task.status == TaskStatus.COMPLETED)
            .order_by(Task.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_share_token(self, task_id: str) -> Optional[str]:
        """Create a share token for a task."""
        task = await self.get_task(task_id)
        if not task:
            return None

        if task.share_token:
            return task.share_token

        # Generate unique share token
        import uuid

        share_token = str(uuid.uuid4())[:16]

        task.share_token = share_token
        task.is_public = 1
        task.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Created share token for task {task_id}: {share_token}")
        return share_token

    async def get_task_by_share_token(self, share_token: str) -> Optional[Task]:
        """Get task by share token."""
        result = await self.db.execute(
            select(Task).where(Task.share_token == share_token)
        )
        return result.scalar_one_or_none()

    async def delete_task(self, task_id: str) -> bool:
        """Delete task and associated files."""
        task = await self.get_task(task_id)
        if not task:
            return False

        # Delete video file from S3 or local storage
        try:
            video_path = task.video_path

            # Check if it's an S3 key (doesn't start with /)
            if settings.S3_ENABLED and not video_path.startswith("/"):
                # Delete from S3
                await storage_service.delete_file(video_path)
                logger.info(f"Deleted video file from S3: {video_path}")
            else:
                # Delete local file
                local_path = Path(video_path)
                if local_path.exists():
                    local_path.unlink()
                    logger.info(f"Deleted local video file: {video_path}")
        except Exception as e:
            logger.error(f"Failed to delete video file: {e}")

        # Delete task from database
        await self.db.delete(task)
        await self.db.commit()

        # Clear cache
        if self.redis:
            await self._invalidate_task_cache(task_id)

        logger.info(f"Deleted task {task_id}")
        return True

    async def _cache_task_status(self, task: Task):
        """Cache task status in Redis."""
        try:
            cache_key = f"task_status:{task.id}"
            cache_data = {
                "status": task.status.value,
                "progress": task.progress,
                "current_stage": task.current_stage,
                "error_message": task.error_message,
            }
            await self.redis.setex(
                cache_key,
                settings.REDIS_CACHE_TTL,
                json.dumps(cache_data),
            )
        except Exception as e:
            logger.warning(f"Failed to cache task status: {e}")

    async def _get_cached_task_status(self, task_id: str) -> Optional[dict]:
        """Get cached task status from Redis."""
        try:
            cache_key = f"task_status:{task_id}"
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get cached task status: {e}")
        return None

    async def _invalidate_task_cache(self, task_id: str):
        """Invalidate task cache in Redis."""
        try:
            cache_key = f"task_status:{task_id}"
            await self.redis.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate task cache: {e}")
