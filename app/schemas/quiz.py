"""Quiz schemas for answer submission and response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuizAnswerRequest(BaseModel):
    """Schema for submitting a quiz answer."""

    selected_index: int = Field(
        ..., ge=0, description="Index of selected option (0-based)"
    )


class QuizAnswerResponse(BaseModel):
    """Schema for quiz answer response."""

    is_correct: bool = Field(..., description="Whether the answer was correct")
    correct_index: int = Field(..., description="Index of the correct answer")
    explanation: Optional[str] = Field(None, description="Explanation if available")
    user_stats: "UserStatsUpdate" = Field(
        ..., description="Updated user statistics after this answer"
    )


class UserStatsUpdate(BaseModel):
    """Schema for updated user statistics."""

    total_answered: int = Field(..., description="Total questions answered")
    total_correct: int = Field(..., description="Total correct answers")
    accuracy: float = Field(..., description="Overall accuracy percentage")


class QuizRetakeRequest(BaseModel):
    """Schema for retaking a quiz segment."""

    segment_id: int = Field(..., description="Segment ID to retake")


class QuizReviewResponse(BaseModel):
    """Schema for reviewing answered quizzes."""

    quiz_id: int = Field(..., description="Quiz ID")
    question: str = Field(..., description="Question text")
    options: list[str] = Field(..., description="Answer options")
    user_answer: int = Field(..., description="User's selected answer index")
    correct_answer: int = Field(..., description="Correct answer index")
    is_correct: bool = Field(..., description="Whether user's answer was correct")
    answered_at: datetime = Field(..., description="When the answer was submitted")
    explanation: Optional[str] = Field(None, description="Explanation if available")


class SegmentAnswerStatus(BaseModel):
    """Schema for segment answer status."""

    segment_id: int = Field(..., description="Segment ID")
    total_questions: int = Field(..., description="Total questions in segment")
    answered_questions: int = Field(
        ..., description="Number of questions user has answered"
    )
    correct_answers: int = Field(..., description="Number of correct answers")
    is_complete: bool = Field(
        ..., description="Whether all questions have been answered"
    )
    score_percentage: float = Field(
        ..., description="Score percentage for this segment"
    )
