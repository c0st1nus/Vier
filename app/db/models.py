"""Database models for tasks and video metadata."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class TaskStatus(str, PyEnum):
    """Task status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    """Task model for video processing jobs."""

    __tablename__ = "tasks"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # File information
    original_filename = Column(String(512), nullable=False)
    video_title = Column(String(512), nullable=True)  # AI-generated video title
    language = Column(String(10), nullable=True, default="ru")  # Language: ru, en, kk
    video_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    file_hash = Column(
        String(64), nullable=True, index=True
    )  # SHA256 hash for duplicate detection

    # Video metadata
    duration = Column(Float, nullable=True)  # Duration in seconds
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)

    # Processing status
    status = Column(
        Enum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    progress = Column(Float, default=0.0)  # Progress percentage (0-100)
    current_stage = Column(String(128), nullable=True)  # Current processing stage
    error_message = Column(Text, nullable=True)

    # Processing results
    segments_json = Column(JSON, nullable=True)  # Full segments with quizzes
    total_segments = Column(Integer, nullable=True)
    total_quizzes = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # User information (for future auth)
    user_id = Column(String(128), nullable=True, index=True)

    # Sharing
    is_public = Column(Integer, default=0)  # 0=private, 1=public
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    def __repr__(self):
        return f"<Task {self.id} - {self.status.value} - {self.original_filename}>"

    def to_dict(self):
        """Convert task to dictionary."""
        return {
            "task_id": str(self.id),
            "original_filename": self.original_filename,
            "video_title": self.video_title,
            "language": self.language,
            "video_path": self.video_path,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "error_message": self.error_message,
            "segments": self.segments_json,
            "total_segments": self.total_segments,
            "total_quizzes": self.total_quizzes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "user_id": self.user_id,
            "is_public": bool(self.is_public),
            "share_token": self.share_token,
        }

    def to_summary(self):
        """Convert task to summary (without segments)."""
        return {
            "task_id": str(self.id),
            "original_filename": self.original_filename,
            "video_title": self.video_title,
            "language": self.language,
            "file_size": self.file_size,
            "duration": self.duration,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "total_segments": self.total_segments,
            "total_quizzes": self.total_quizzes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "is_public": bool(self.is_public),
        }
