"""User statistics aggregation service."""

from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Segment, UserAnswer, Video
from app.schemas.user import (
    PaginationMeta,
    RecentActivityItem,
    TopicStats,
    UserHistoryItem,
    UserHistoryResponse,
    UserProfileResponse,
    UserStatsResponse,
    UserTopicsResponse,
)


def _safe_accuracy(total: int, correct: int) -> float:
    """Return accuracy percentage with zero-division protection."""
    if total <= 0:
        return 0.0
    return round((correct / total) * 100.0, 2)


class UserStatsService:
    """Service for computing user profiles, stats, history, and topics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    # Profile
    # ------------------------------------------------------------------ #
    async def get_profile(self, user_id: int) -> UserProfileResponse:
        """Return high-level profile aggregates."""
        total_questions_stmt = select(func.count(UserAnswer.id)).where(
            UserAnswer.user_id == user_id
        )
        total_correct_stmt = select(
            func.count(UserAnswer.id).filter(UserAnswer.is_correct.is_(True))
        ).where(UserAnswer.user_id == user_id)

        videos_watched_stmt = (
            select(func.count(func.distinct(Segment.video_id)))
            .join(UserAnswer, UserAnswer.segment_id == Segment.id)
            .where(UserAnswer.user_id == user_id)
        )

        total_questions = (await self.db.execute(total_questions_stmt)).scalar_one()
        total_correct = (await self.db.execute(total_correct_stmt)).scalar_one()
        videos_watched = (await self.db.execute(videos_watched_stmt)).scalar_one()

        accuracy = _safe_accuracy(total_questions, total_correct)

        user_created_stmt = select(func.min(UserAnswer.answered_at)).where(
            UserAnswer.user_id == user_id
        )
        created_at = (await self.db.execute(user_created_stmt)).scalar_one_or_none()
        profile_created_at = created_at or datetime.utcnow()

        # Streaks are not yet stored; return 0 as placeholder.
        current_streak = 0

        return UserProfileResponse(
            user_id=user_id,
            email="",  # email not fetched here; caller can enrich if needed
            videos_watched=videos_watched or 0,
            total_questions_answered=total_questions or 0,
            total_correct_answers=total_correct or 0,
            accuracy=accuracy,
            current_streak=current_streak,
            created_at=profile_created_at,
        )

    # ------------------------------------------------------------------ #
    # Detailed stats
    # ------------------------------------------------------------------ #
    async def get_stats(
        self, user_id: int, limit_topics: int = 10
    ) -> UserStatsResponse:
        """Return detailed stats with accuracy by topic and recent activity."""
        total_questions, total_correct = await self._totals(user_id)
        accuracy = _safe_accuracy(total_questions, total_correct)

        topics = await self._topics(user_id, limit=limit_topics)
        recent_activity = await self._recent_activity(user_id, limit=10)

        total_videos_stmt = (
            select(func.count(func.distinct(Segment.video_id)))
            .join(UserAnswer, UserAnswer.segment_id == Segment.id)
            .where(UserAnswer.user_id == user_id)
        )
        total_videos = (await self.db.execute(total_videos_stmt)).scalar_one() or 0

        return UserStatsResponse(
            total_videos_watched=total_videos,
            total_questions_answered=total_questions,
            total_correct_answers=total_correct,
            accuracy=accuracy,
            accuracy_by_topic=topics,
            recent_activity=recent_activity,
        )

    # ------------------------------------------------------------------ #
    # History (paginated)
    # ------------------------------------------------------------------ #
    async def get_history(
        self, user_id: int, page: int = 1, page_size: int = 10
    ) -> UserHistoryResponse:
        """Return paginated history of videos the user interacted with."""
        offset = (page - 1) * page_size

        base_query = (
            select(
                Video.task_id,
                Video.title,
                Video.language,
                Video.status,
                func.max(UserAnswer.answered_at).label("watched_at"),
                func.count(UserAnswer.id).label("answered"),
                func.count(UserAnswer.id)
                .filter(UserAnswer.is_correct.is_(True))
                .label("correct"),
            )
            .join(Segment, Segment.id == UserAnswer.segment_id)
            .join(Video, Video.id == Segment.video_id)
            .where(UserAnswer.user_id == user_id)
            .group_by(Video.id)
            .order_by(func.max(UserAnswer.answered_at).desc())
        )

        total_items_stmt = select(func.count()).select_from(base_query.subquery())
        total_items = (await self.db.execute(total_items_stmt)).scalar_one() or 0
        total_pages = max(1, math.ceil(total_items / page_size))

        paginated_stmt = base_query.limit(page_size).offset(offset)
        rows = (await self.db.execute(paginated_stmt)).all()

        items: List[UserHistoryItem] = []
        for row in rows:
            score = _safe_accuracy(row.answered, row.correct)
            items.append(
                UserHistoryItem(
                    task_id=str(row.task_id) if row.task_id else None,
                    title=row.title,
                    watched_at=row.watched_at,
                    questions_answered=row.answered,
                    correct_answers=row.correct,
                    score_percentage=score,
                    language=row.language,
                    status=row.status.value if row.status else None,
                )
            )

        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

        return UserHistoryResponse(items=items, pagination=pagination)

    # ------------------------------------------------------------------ #
    # Topics
    # ------------------------------------------------------------------ #
    async def get_topics(self, user_id: int, limit: int = 10) -> UserTopicsResponse:
        """Return top topics/keywords aggregated from segment keywords."""
        topics = await self._topics(user_id, limit=limit)
        return UserTopicsResponse(topics=topics)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _totals(self, user_id: int) -> Tuple[int, int]:
        """Return (total_answered, total_correct)."""
        total_stmt = select(func.count(UserAnswer.id)).where(
            UserAnswer.user_id == user_id
        )
        correct_stmt = select(
            func.count(UserAnswer.id).filter(UserAnswer.is_correct.is_(True))
        ).where(UserAnswer.user_id == user_id)

        total = (await self.db.execute(total_stmt)).scalar_one() or 0
        correct = (await self.db.execute(correct_stmt)).scalar_one() or 0
        return total, correct

    async def _topics(self, user_id: int, limit: int) -> List[TopicStats]:
        """Aggregate accuracy per topic/keyword."""
        # Unnest keywords array to aggregate by individual keyword
        topic_query = (
            select(
                func.unnest(Segment.keywords).label("topic"),
                func.count(UserAnswer.id).label("answered"),
                func.count(UserAnswer.id)
                .filter(UserAnswer.is_correct.is_(True))
                .label("correct"),
            )
            .join(UserAnswer, UserAnswer.segment_id == Segment.id)
            .where(UserAnswer.user_id == user_id)
            .group_by("topic")
            .order_by(func.count(UserAnswer.id).desc())
            .limit(limit)
        )

        rows = (await self.db.execute(topic_query)).all()
        topics: List[TopicStats] = []
        for row in rows:
            accuracy = _safe_accuracy(row.answered, row.correct)
            topics.append(
                TopicStats(
                    topic=row.topic,
                    total_answered=row.answered,
                    correct_answers=row.correct,
                    accuracy=accuracy,
                )
            )
        return topics

    async def _recent_activity(
        self, user_id: int, limit: int
    ) -> List[RecentActivityItem]:
        """Return recent activity entries."""
        recent_query = (
            select(
                Video.task_id,
                Video.title,
                func.max(UserAnswer.answered_at).label("watched_at"),
                func.count(UserAnswer.id).label("answered"),
                func.count(UserAnswer.id)
                .filter(UserAnswer.is_correct.is_(True))
                .label("correct"),
            )
            .join(Segment, Segment.id == UserAnswer.segment_id)
            .join(Video, Video.id == Segment.video_id)
            .where(UserAnswer.user_id == user_id)
            .group_by(Video.id)
            .order_by(func.max(UserAnswer.answered_at).desc())
            .limit(limit)
        )

        rows = (await self.db.execute(recent_query)).all()
        items: List[RecentActivityItem] = []
        for row in rows:
            items.append(
                RecentActivityItem(
                    task_id=str(row.task_id) if row.task_id else None,
                    title=row.title,
                    watched_at=row.watched_at,
                    questions_answered=row.answered,
                    correct_answers=row.correct,
                    score_percentage=_safe_accuracy(row.answered, row.correct),
                )
            )
        return items
