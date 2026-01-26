"""Video schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class VideoUploadRequest(BaseModel):
    """Schema for video upload request (URL)."""

    url: str = Field(..., description="Video URL (YouTube, etc.)")
    language: str = Field(
        default="en",
        description="Language for quiz generation (en, ru, kk)",
        pattern="^(en|ru|kk)$",
    )


class VideoUploadResponse(BaseModel):
    """Schema for video upload response."""

    task_id: str = Field(..., description="Task ID for tracking processing")
    cached: bool = Field(
        default=False, description="Whether video was already processed"
    )
    message: Optional[str] = Field(None, description="Additional information")


class VideoCheckRequest(BaseModel):
    """Schema for checking if video is already processed."""

    url: str = Field(..., description="Video URL to check")
    language: str = Field(
        default="en",
        description="Language to check (en, ru, kk)",
        pattern="^(en|ru|kk)$",
    )


class VideoCheckResponse(BaseModel):
    """Schema for video check response."""

    exists: bool = Field(..., description="Whether video exists in database")
    task_id: Optional[str] = Field(None, description="Task ID if video exists")


class QuizSchema(BaseModel):
    """Schema for a single quiz question."""

    id: int = Field(..., description="Quiz ID")
    question: str = Field(..., description="Question text")
    options: List[str] = Field(..., description="Answer options")
    type: str = Field(default="multiple_choice", description="Question type")
    correct_index: Optional[int] = Field(
        None, description="Correct answer index (only in review mode)"
    )
    explanation: Optional[str] = Field(
        None, description="Explanation for correct answer"
    )


class SegmentSchema(BaseModel):
    """Schema for video segment with quizzes."""

    id: int = Field(..., description="Database ID for the segment")
    segment_id: int = Field(..., description="Sequential segment number")
    start_time: int = Field(..., description="Start time in seconds")
    end_time: int = Field(..., description="End time in seconds")
    topic_title: Optional[str] = Field(None, description="Segment topic/title")
    short_summary: Optional[str] = Field(None, description="Brief summary of segment")
    keywords: Optional[List[str]] = Field(None, description="Key topics covered")
    quizzes: List[QuizSchema] = Field(
        default_factory=list, description="Quiz questions"
    )


class SegmentsResponse(BaseModel):
    """Schema for segments response."""

    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Processing status")
    total_segments: Optional[int] = Field(None, description="Total number of segments")
    segments: List[SegmentSchema] = Field(
        default_factory=list, description="Available segments"
    )


# WebSocket Event Schemas


class WSConnectedEvent(BaseModel):
    """WebSocket connected event."""

    event: str = Field(default="connected", description="Event type")
    task_id: str = Field(..., description="Task ID")
    message: str = Field(default="WebSocket connection established")


class WSSegmentReadyEvent(BaseModel):
    """WebSocket segment ready event."""

    event: str = Field(default="segment_ready", description="Event type")
    segment: SegmentSchema = Field(..., description="Ready segment with quizzes")


class WSProgressEvent(BaseModel):
    """WebSocket progress event."""

    event: str = Field(default="progress", description="Event type")
    progress: float = Field(..., description="Progress percentage (0-100)")
    current_stage: str = Field(..., description="Current processing stage")


class WSCompletedEvent(BaseModel):
    """WebSocket completed event."""

    event: str = Field(default="completed", description="Event type")
    total_segments: int = Field(..., description="Total segments processed")
    message: str = Field(default="Video processing completed")


class WSErrorEvent(BaseModel):
    """WebSocket error event."""

    event: str = Field(default="error", description="Event type")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")
