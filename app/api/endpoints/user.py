"""User profile and statistics endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import (
    UserHistoryResponse,
    UserProfileResponse,
    UserStatsResponse,
    UserTopicsResponse,
)
from app.services.user_stats_service import UserStatsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


def _service(db: AsyncSession) -> UserStatsService:
    """Helper to construct service."""
    return UserStatsService(db)


@router.get(
    "/profile", response_model=UserProfileResponse, status_code=status.HTTP_200_OK
)
async def get_user_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get user profile with aggregate stats.

    Returns:
    - videos watched
    - total questions answered
    - correct answers
    - accuracy percentage
    - current streak (placeholder)
    """
    try:
        service = _service(db)
        user_id = int(current_user.id)  # type: ignore[arg-type]
        profile = await service.get_profile(user_id)
        return profile.model_copy(update={"email": current_user.email})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile",
        )


@router.get("/stats", response_model=UserStatsResponse, status_code=status.HTTP_200_OK)
async def get_user_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit_topics: int = Query(10, ge=1, le=50, description="Max topics to return"),
):
    """Get detailed statistics including accuracy by topic and recent activity."""
    try:
        service = _service(db)
        user_id = int(current_user.id)  # type: ignore[arg-type]
        return await service.get_stats(user_id, limit_topics=limit_topics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user stats",
        )


@router.get(
    "/history", response_model=UserHistoryResponse, status_code=status.HTTP_200_OK
)
async def get_user_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """Get paginated video interaction history for the user."""
    try:
        service = _service(db)
        user_id = int(current_user.id)  # type: ignore[arg-type]
        return await service.get_history(user_id, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user history",
        )


@router.get(
    "/topics", response_model=UserTopicsResponse, status_code=status.HTTP_200_OK
)
async def get_user_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50, description="Max topics/keywords to return"),
):
    """Get top topics/keywords with accuracy for the user."""
    try:
        service = _service(db)
        user_id = int(current_user.id)  # type: ignore[arg-type]
        return await service.get_topics(user_id, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user topics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user topics",
        )
