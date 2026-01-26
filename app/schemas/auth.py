"""Authentication schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, description="User password (min 8 characters)"
    )


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Schema for user statistics."""

    videos_watched: int = Field(default=0, description="Total videos watched")
    questions_answered: int = Field(default=0, description="Total questions answered")
    correct_answers: int = Field(default=0, description="Total correct answers")
    accuracy: float = Field(default=0.0, description="Overall accuracy percentage")
    current_streak: int = Field(default=0, description="Current daily streak")


class UserProfile(BaseModel):
    """Schema for user profile with stats."""

    id: int
    email: str
    created_at: datetime
    stats: UserStats

    class Config:
        from_attributes = True
