"""User-related schemas for profile, stats, history, and topics."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(..., ge=1, description="Current page number (1-based)")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_items: int = Field(..., ge=0, description="Total items available")
    total_pages: int = Field(..., ge=1, description="Total number of pages")


class UserProfileResponse(BaseModel):
    """User profile with aggregate stats."""

    user_id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    videos_watched: int = Field(
        ..., ge=0, description="Number of videos interacted with"
    )
    total_questions_answered: int = Field(
        ..., ge=0, description="Total quiz questions answered"
    )
    total_correct_answers: int = Field(
        ..., ge=0, description="Total correct quiz answers"
    )
    accuracy: float = Field(
        ..., ge=0.0, le=100.0, description="Overall accuracy percentage"
    )
    current_streak: int = Field(
        ..., ge=0, description="Current daily streak (days in a row)"
    )
    created_at: datetime = Field(..., description="Account creation timestamp")


class TopicStats(BaseModel):
    """Aggregated accuracy per topic/keyword."""

    topic: str = Field(..., description="Topic or keyword")
    total_answered: int = Field(..., ge=0, description="Questions answered for topic")
    correct_answers: int = Field(..., ge=0, description="Correct answers for topic")
    accuracy: float = Field(
        ..., ge=0.0, le=100.0, description="Accuracy percentage for topic"
    )


class RecentActivityItem(BaseModel):
    """Recent activity entry for stats panel."""

    task_id: Optional[str] = Field(
        None, description="Task ID associated with the processed video"
    )
    title: Optional[str] = Field(None, description="Video title if available")
    watched_at: datetime = Field(..., description="When the video was interacted with")
    questions_answered: int = Field(..., ge=0, description="Questions answered")
    correct_answers: int = Field(..., ge=0, description="Correct answers")
    score_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Score percentage for this video"
    )


class UserStatsResponse(BaseModel):
    """Detailed user statistics."""

    total_videos_watched: int = Field(..., ge=0, description="Total videos watched")
    total_questions_answered: int = Field(
        ..., ge=0, description="Total quiz questions answered"
    )
    total_correct_answers: int = Field(
        ..., ge=0, description="Total correct quiz answers"
    )
    accuracy: float = Field(
        ..., ge=0.0, le=100.0, description="Overall accuracy percentage"
    )
    accuracy_by_topic: List[TopicStats] = Field(
        default_factory=list, description="Accuracy breakdown by topic/keyword"
    )
    recent_activity: List[RecentActivityItem] = Field(
        default_factory=list, description="Recent activity entries"
    )


class UserHistoryItem(BaseModel):
    """History record for a single video interaction."""

    task_id: Optional[str] = Field(
        None, description="Task ID associated with the processed video"
    )
    title: Optional[str] = Field(None, description="Video title if available")
    watched_at: datetime = Field(..., description="When the video was interacted with")
    questions_answered: int = Field(..., ge=0, description="Questions answered")
    correct_answers: int = Field(..., ge=0, description="Correct answers")
    score_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Score percentage for this video"
    )
    language: Optional[str] = Field(
        None, description="Language used for quiz generation (en, ru, kk)"
    )
    status: Optional[str] = Field(
        None, description="Processing status of the video, if applicable"
    )


class UserHistoryResponse(BaseModel):
    """Paginated user history response."""

    items: List[UserHistoryItem] = Field(
        default_factory=list, description="List of history items"
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class UserTopicsResponse(BaseModel):
    """Top topics/keywords aggregated for the user."""

    topics: List[TopicStats] = Field(
        default_factory=list, description="Aggregated topic statistics"
    )
