"""Video endpoints for new architecture with Video, Segment, Quiz models."""

import asyncio
import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user_optional
from app.db.models import ProcessingStatus, User, Video
from app.db.session import get_db
from app.schemas.models import ProcessingTask, TaskStatus, VideoMetadata
from app.schemas.video import (
    SegmentsResponse,
    VideoCheckRequest,
    VideoCheckResponse,
    VideoUploadRequest,
    VideoUploadResponse,
)
from app.services.pipeline import TASKS, process_video_from_url
from app.utils.video_utils import normalize_youtube_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Video"])


@router.post("/check", response_model=VideoCheckResponse)
async def check_video(
    request: VideoCheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)] = None,
):
    """
    Check if video already exists in database (cached).

    - **url**: Video URL to check
    - **language**: Language for quiz generation (en, ru, kk)
    - Returns whether video exists and task_id if it does
    """
    try:
        normalized_url = normalize_youtube_url(str(request.url))
        # Query for existing video with same URL and language
        result = await db.execute(
            select(Video).where(
                Video.url == normalized_url, Video.language == request.language
            )
        )
        video = result.scalar_one_or_none()

        if video:
            return VideoCheckResponse(exists=True, task_id=str(video.task_id))
        else:
            return VideoCheckResponse(exists=False, task_id=None)

    except Exception as e:
        logger.error(f"Video check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video check failed: {str(e)}",
        )


@router.post("/upload/url", response_model=VideoUploadResponse)
async def upload_video_url(
    request: VideoUploadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)] = None,
):
    """
    Upload video by URL for processing.

    - **url**: Video URL (YouTube, etc.)
    - **language**: Language for quiz generation (en, ru, kk)
    - Returns task_id and cached status
    """
    try:
        normalized_url = normalize_youtube_url(str(request.url))
        # Check if video already exists
        result = await db.execute(
            select(Video).where(
                Video.url == normalized_url, Video.language == request.language
            )
        )
        existing_video = result.scalar_one_or_none()

        if existing_video:
            status_value = ProcessingStatus(existing_video.status)
            # Video already processed or processing
            if status_value == ProcessingStatus.COMPLETED:
                return VideoUploadResponse(
                    task_id=str(existing_video.task_id),
                    cached=True,
                    message="Video already processed. You can access segments immediately.",
                )
            elif status_value == ProcessingStatus.PROCESSING:
                task_id_str = str(existing_video.task_id)
                if task_id_str not in TASKS:
                    TASKS[task_id_str] = ProcessingTask(
                        task_id=task_id_str,
                        status=TaskStatus.PENDING,
                        video_path=None,
                        metadata=VideoMetadata(
                            duration=0.0,
                            fps=0.0,
                            width=0,
                            height=0,
                            format="unknown",
                            source_url=normalized_url,
                        ),
                    )
                    asyncio.create_task(
                        process_video_from_url(
                            task_id_str, normalized_url, request.language
                        )
                    )
                    logger.info(
                        f"Restarted processing for existing video {task_id_str} (PROCESSING in DB, missing in cache)"
                    )
                return VideoUploadResponse(
                    task_id=task_id_str,
                    cached=False,
                    message="Video is currently being processed. Connect via WebSocket for updates.",
                )
            elif status_value == ProcessingStatus.FAILED:
                # Retry failed video by creating new task
                logger.info(
                    f"Retrying failed video: {normalized_url} (language: {request.language})"
                )
                # Delete old failed video
                await db.delete(existing_video)
                await db.commit()
            else:
                # PENDING status
                task_id_str = str(existing_video.task_id)
                if task_id_str not in TASKS:
                    TASKS[task_id_str] = ProcessingTask(
                        task_id=task_id_str,
                        status=TaskStatus.PENDING,
                        video_path=None,
                        metadata=VideoMetadata(
                            duration=0.0,
                            fps=0.0,
                            width=0,
                            height=0,
                            format="unknown",
                            source_url=normalized_url,
                        ),
                    )
                    asyncio.create_task(
                        process_video_from_url(
                            task_id_str, normalized_url, request.language
                        )
                    )
                    logger.info(
                        f"Restarted processing for existing video {task_id_str} (PENDING in DB, missing in cache)"
                    )
                return VideoUploadResponse(
                    task_id=task_id_str,
                    cached=False,
                    message="Video processing will start soon. Connect via WebSocket for updates.",
                )

        # Create new video entry
        new_video = Video(
            url=normalized_url,
            language=request.language,
            status=ProcessingStatus.PENDING,
            user_id=current_user.id if current_user else None,
        )
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)

        logger.info(
            f"New video created: {new_video.task_id} - URL: {request.url} (language: {request.language})"
        )

        # Register in-memory task (pipeline cache) and start processing
        task_id_str = str(new_video.task_id)
        TASKS[task_id_str] = ProcessingTask(
            task_id=task_id_str,
            status=TaskStatus.PENDING,
            video_path=None,
            metadata=VideoMetadata(
                duration=0.0,
                fps=0.0,
                width=0,
                height=0,
                format="unknown",
                source_url=normalized_url,
            ),
        )

        asyncio.create_task(
            process_video_from_url(task_id_str, normalized_url, request.language)
        )

        return VideoUploadResponse(
            task_id=task_id_str,
            cached=False,
            message="Video added to processing queue. Connect via WebSocket for real-time updates.",
        )

    except Exception as e:
        logger.error(f"Video upload failed: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video upload failed: {str(e)}",
        )


@router.get("/{task_id}/segments", response_model=SegmentsResponse)
async def get_video_segments(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)] = None,
):
    """
    Get all segments for a video.

    - **task_id**: Task ID from upload response
    - Returns video status and all available segments with quizzes
    """
    try:
        # Parse task_id as UUID
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid task_id format. Must be a valid UUID.",
            )

        # Query video with segments and quizzes eagerly loaded
        from app.db.models import Segment

        result = await db.execute(
            select(Video)
            .where(Video.task_id == task_uuid)
            .options(selectinload(Video.segments).selectinload(Segment.quizzes))
        )
        video = result.scalar_one_or_none()

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with task_id {task_id} not found",
            )

        # Build response
        segments_data = []
        if video.segments:
            for segment in video.segments:
                # Get quizzes for this segment
                quizzes_data = []
                if segment.quizzes:
                    for quiz in segment.quizzes:
                        # Don't include correct_index in response (user shouldn't see it until they answer)
                        quizzes_data.append(quiz.to_dict(include_correct=False))

                # Add segment with quizzes
                segment_dict = segment.to_dict(include_quizzes=False)
                segment_dict["quizzes"] = quizzes_data
                segments_data.append(segment_dict)

        return SegmentsResponse(
            task_id=task_id,
            status=video.status.value,
            total_segments=len(video.segments) if video.segments else None,
            segments=segments_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get segments: {str(e)}",
        )


@router.get("/{task_id}/status")
async def get_video_status(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get current processing status of a video.

    - **task_id**: Task ID from upload response
    - Returns status, progress, and current stage
    """
    try:
        # Parse task_id as UUID
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid task_id format. Must be a valid UUID.",
            )

        # Query video
        result = await db.execute(select(Video).where(Video.task_id == task_uuid))
        video = result.scalar_one_or_none()

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with task_id {task_id} not found",
            )

        created_at = video.created_at
        started_at = video.started_at
        completed_at = video.completed_at

        return {
            "task_id": task_id,
            "status": video.status.value,
            "progress": video.progress,
            "current_stage": video.current_stage,
            "error_message": video.error_message,
            "created_at": created_at.isoformat() if created_at is not None else None,
            "started_at": started_at.isoformat() if started_at is not None else None,
            "completed_at": completed_at.isoformat()
            if completed_at is not None
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video status: {str(e)}",
        )
