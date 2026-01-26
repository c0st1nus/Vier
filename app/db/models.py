"""Database models for video processing, authentication, and quiz system."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class ProcessingStatus(str, PyEnum):
    """Processing status enum for videos."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, PyEnum):
    """Task status enum for legacy Task model."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# AUTHENTICATION MODELS
# ============================================================================


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    answers = relationship(
        "UserAnswer", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.id} - {self.email}>"


class RefreshToken(Base):
    """Refresh token model for JWT authentication."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken {self.id} - User {self.user_id}>"


# ============================================================================
# VIDEO PROCESSING MODELS
# ============================================================================


class Task(Base):
    """Legacy Task model used by TaskService."""

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    original_filename = Column(String(512), nullable=False)
    video_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    status = Column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True
    )
    progress = Column(Float, nullable=True, default=0.0)
    current_stage = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    segments_json = Column(JSON, nullable=True)
    total_segments = Column(Integer, nullable=True)
    total_quizzes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    user_id = Column(String(128), nullable=True, index=True)
    is_public = Column(Integer, nullable=True, default=0)
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    def __repr__(self):
        return f"<Task {self.id} - {self.original_filename} - {self.status.value}>"


class Video(Base):
    """Video model for caching processed videos."""

    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("url", "language", name="uq_video_url_language"),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False, index=True)
    language = Column(String(5), nullable=False, index=True)  # "en", "ru", "kk"
    task_id = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )

    # Video metadata
    title = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    file_path = Column(String(1024), nullable=True)  # Path to downloaded video file

    # Processing status
    status = Column(
        Enum(ProcessingStatus),
        nullable=False,
        default=ProcessingStatus.PENDING,
        index=True,
    )
    progress = Column(Float, default=0.0)  # Progress percentage (0-100)
    current_stage = Column(String(128), nullable=True)  # Current processing stage
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # User who initiated processing (optional for anonymous)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    segments = relationship(
        "Segment",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="Segment.segment_id",
    )

    def __repr__(self):
        return (
            f"<Video {self.id} - {self.title} ({self.language}) - {self.status.value}>"
        )

    def to_dict(self, include_segments=False):
        """Convert video to dictionary."""
        result = {
            "task_id": str(self.task_id),
            "url": self.url,
            "language": self.language,
            "title": self.title,
            "duration": self.duration,
            "status": self.status.value,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat()
            if self.processed_at
            else None,
            "total_segments": len(self.segments) if self.segments else 0,
        }
        if include_segments and self.segments:
            result["segments"] = [seg.to_dict() for seg in self.segments]
        return result


class Segment(Base):
    """Segment model for video segments."""

    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("video_id", "segment_id", name="uq_segment_video_segment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(
        Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id = Column(
        Integer, nullable=False
    )  # Sequential segment number (1, 2, 3...)
    start_time = Column(Integer, nullable=False)  # Start time in seconds
    end_time = Column(Integer, nullable=False)  # End time in seconds
    topic_title = Column(String(500), nullable=True)
    short_summary = Column(Text, nullable=True)
    keywords = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="segments")
    quizzes = relationship(
        "Quiz", back_populates="segment", cascade="all, delete-orphan"
    )
    answers = relationship("UserAnswer", back_populates="segment")

    def __repr__(self):
        return (
            f"<Segment {self.id} - Video {self.video_id} - Segment #{self.segment_id}>"
        )

    def to_dict(self, include_quizzes=True):
        """Convert segment to dictionary."""
        result = {
            "id": self.id,
            "segment_id": self.segment_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "topic_title": self.topic_title,
            "short_summary": self.short_summary,
            "keywords": self.keywords,
        }
        if include_quizzes:
            result["quizzes"] = (
                [quiz.to_dict() for quiz in self.quizzes] if self.quizzes else []
            )
        return result


class Quiz(Base):
    """Quiz model for questions."""

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(
        Integer,
        ForeignKey("segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question = Column(Text, nullable=False)
    options = Column(
        JSON, nullable=False
    )  # ["Option A", "Option B", "Option C", "Option D"]
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)  # Optional explanation
    language = Column(String(5), nullable=False)  # "en", "ru", "kk"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    segment = relationship("Segment", back_populates="quizzes")
    answers = relationship(
        "UserAnswer", back_populates="quiz", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Quiz {self.id} - Segment {self.segment_id}>"

    def to_dict(self, include_correct=False):
        """Convert quiz to dictionary."""
        result = {
            "id": self.id,
            "question": self.question,
            "options": self.options,
            "type": "multiple_choice",
        }
        if include_correct:
            result["correct_index"] = self.correct_index
            if self.explanation:
                result["explanation"] = self.explanation
        return result


class UserAnswer(Base):
    """User answer model for tracking quiz responses."""

    __tablename__ = "user_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "quiz_id", name="uq_user_answer_user_quiz"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id = Column(
        Integer, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False
    )
    selected_index = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="answers")
    quiz = relationship("Quiz", back_populates="answers")
    segment = relationship("Segment", back_populates="answers")

    def __repr__(self):
        return f"<UserAnswer {self.id} - User {self.user_id} - Quiz {self.quiz_id} - {'✓' if self.is_correct else '✗'}>"
