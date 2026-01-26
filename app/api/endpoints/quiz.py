"""Quiz endpoints for answer submission, status, review, and retake."""

import logging
from datetime import datetime
from typing import Annotated, List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.db.models import Quiz, Segment, User, UserAnswer
from app.db.session import get_db
from app.schemas.quiz import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizReviewResponse,
    SegmentAnswerStatus,
    UserStatsUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


async def _compute_user_stats(db: AsyncSession, user_id: int) -> UserStatsUpdate:
    """Aggregate user-wide stats."""
    total_stmt = select(func.count(UserAnswer.id)).where(UserAnswer.user_id == user_id)
    correct_stmt = (
        select(func.count(UserAnswer.id))
        .where(UserAnswer.user_id == user_id)
        .where(UserAnswer.is_correct.is_(True))
    )

    total = (await db.execute(total_stmt)).scalar_one() or 0
    correct = (await db.execute(correct_stmt)).scalar_one() or 0
    accuracy = round((correct / total) * 100, 2) if total else 0.0

    return UserStatsUpdate(
        total_answered=total,
        total_correct=correct,
        accuracy=accuracy,
    )


@router.post(
    "/{quiz_id}/answer",
    response_model=QuizAnswerResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_quiz_answer(
    quiz_id: int,
    request: QuizAnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Submit or update an answer to a quiz question.

    - Validates the quiz exists
    - Upserts the user's answer (allows retake by overwriting)
    - Returns correctness and updated user stats
    """
    # Fetch quiz and validate bounds
    quiz = (
        await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    ).scalar_one_or_none()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz {quiz_id} not found",
        )

    options_raw = quiz.options if isinstance(quiz.options, list) else []
    options = cast(List[str], list(options_raw))
    options_count = len(options)
    if request.selected_index >= options_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selected_index is out of range for quiz options",
        )

    is_correct = request.selected_index == quiz.correct_index

    # Upsert user answer
    existing_answer = (
        await db.execute(
            select(UserAnswer).where(
                UserAnswer.user_id == current_user.id,
                UserAnswer.quiz_id == quiz.id,
            )
        )
    ).scalar_one_or_none()

    now = datetime.utcnow()
    if existing_answer:
        await db.delete(existing_answer)
        await db.flush()

    user_id_val = cast(int, current_user.id)
    quiz_id_val = cast(int, quiz.id)
    segment_id_val = cast(int, quiz.segment_id)

    answer_obj = UserAnswer(
        user_id=user_id_val,
        quiz_id=quiz_id_val,
        segment_id=segment_id_val,
        selected_index=int(request.selected_index),
        is_correct=bool(is_correct),
        answered_at=now,
    )
    db.add(answer_obj)

    await db.commit()

    user_stats = await _compute_user_stats(db, user_id_val)
    correct_index_val = cast(int, quiz.correct_index)
    explanation_val = (
        cast(str, quiz.explanation) if quiz.explanation is not None else None
    )

    return QuizAnswerResponse(
        is_correct=is_correct,
        correct_index=correct_index_val,
        explanation=explanation_val,
        user_stats=user_stats,
    )


@router.get(
    "/segment/{segment_id}/status",
    response_model=SegmentAnswerStatus,
    status_code=status.HTTP_200_OK,
)
async def get_segment_status(
    segment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get answer progress for a segment for the current user.
    """
    segment = (
        await db.execute(
            select(Segment)
            .options(selectinload(Segment.quizzes))
            .where(Segment.id == segment_id)
        )
    ).scalar_one_or_none()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_id} not found",
        )

    quizzes = cast(List[Quiz], list(segment.quizzes or []))
    total_questions = len(quizzes)

    segment_db_id = cast(int, segment.id)
    segment_num = cast(int, segment.segment_id)
    user_id_val = cast(int, current_user.id)
    answered_stmt = select(func.count(UserAnswer.id)).where(
        UserAnswer.user_id == user_id_val,
        UserAnswer.segment_id == segment_db_id,
    )
    correct_stmt = select(func.count(UserAnswer.id)).where(
        UserAnswer.user_id == user_id_val,
        UserAnswer.segment_id == segment_db_id,
        UserAnswer.is_correct.is_(True),
    )

    answered_questions = (await db.execute(answered_stmt)).scalar_one() or 0
    correct_answers = (await db.execute(correct_stmt)).scalar_one() or 0
    score_percentage = (
        round((correct_answers / total_questions) * 100, 2) if total_questions else 0.0
    )
    is_complete = total_questions > 0 and answered_questions >= total_questions

    return SegmentAnswerStatus(
        segment_id=segment_num,
        total_questions=total_questions,
        answered_questions=answered_questions,
        correct_answers=correct_answers,
        is_complete=is_complete,
        score_percentage=score_percentage,
    )


@router.get(
    "/segment/{segment_id}/review",
    response_model=List[QuizReviewResponse],
    status_code=status.HTTP_200_OK,
)
async def review_segment_answers(
    segment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Review all answered quizzes for a segment with user's selections.
    """
    segment = (
        await db.execute(
            select(Segment)
            .options(selectinload(Segment.quizzes))
            .where(Segment.id == segment_id)
        )
    ).scalar_one_or_none()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_id} not found",
        )

    quizzes = cast(List[Quiz], list(segment.quizzes or []))
    quiz_ids = [cast(int, q.id) for q in quizzes]
    if not quiz_ids:
        return []

    user_id_val = cast(int, current_user.id)
    answers_rows = (
        (
            await db.execute(
                select(UserAnswer)
                .where(UserAnswer.user_id == user_id_val)
                .where(UserAnswer.quiz_id.in_(quiz_ids))
            )
        )
        .scalars()
        .all()
    )
    answers_by_quiz = {ans.quiz_id: ans for ans in answers_rows}

    reviews: List[QuizReviewResponse] = []
    for quiz in quizzes:
        ans = answers_by_quiz.get(quiz.id)
        if not ans:
            continue  # only include answered quizzes
        reviews.append(
            QuizReviewResponse(
                quiz_id=cast(int, quiz.id),
                question=cast(str, quiz.question),
                options=cast(
                    List[str],
                    list(quiz.options if isinstance(quiz.options, list) else []),
                ),
                user_answer=cast(int, ans.selected_index),
                correct_answer=cast(int, quiz.correct_index),
                is_correct=bool(ans.is_correct),
                answered_at=cast(datetime, ans.answered_at),
                explanation=cast(str, quiz.explanation)
                if quiz.explanation is not None
                else None,
            )
        )

    return reviews


@router.post(
    "/segment/{segment_id}/retake",
    status_code=status.HTTP_200_OK,
)
async def retake_segment(
    segment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete existing answers for the segment for the current user to allow retake.
    """
    segment = (
        await db.execute(select(Segment).where(Segment.id == segment_id))
    ).scalar_one_or_none()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_id} not found",
        )

    segment_db_id = cast(int, segment.id)
    user_id_val = cast(int, current_user.id)
    delete_stmt = (
        delete(UserAnswer)
        .where(UserAnswer.user_id == user_id_val)
        .where(UserAnswer.segment_id == segment_db_id)
    )
    await db.execute(delete_stmt)
    await db.commit()

    return {"message": "Segment answers cleared. You can retake the quiz now."}
