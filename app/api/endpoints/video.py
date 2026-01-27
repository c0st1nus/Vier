import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.db.models import TaskStatus as DBTaskStatus
from app.schemas.models import SegmentsResponse, TaskStatusResponse
from app.services.pipeline import get_task, get_task_segments, get_task_status
from app.services.storage_service import storage_service
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_video_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get current processing status of a video task

    - **task_id**: Task identifier from upload response
    - Returns current status, progress, and stage information
    """
    try:
        # Try to get from database first
        task_service = TaskService(db)
        db_task = await task_service.get_task(task_id)

        if db_task:
            # Return DB status
            return TaskStatusResponse(
                task_id=task_id,
                status=db_task.status.value,
                progress=db_task.progress or 0.0,
                current_stage=db_task.current_stage,
                error=db_task.error_message,
                created_at=db_task.created_at,
                updated_at=db_task.updated_at,
            )

        # Fallback to in-memory status
        status_info = get_task_status(task_id)

        if not status_info:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return TaskStatusResponse(**status_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/{task_id}/segments", response_model=SegmentsResponse)
async def get_video_segments(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get processed video segments with quizzes

    - **task_id**: Task identifier
    - Returns list of video segments with timestamps, summaries, and quiz questions
    - Only available after processing is completed
    """
    try:
        # Get from database
        task_service = TaskService(db)
        db_task = await task_service.get_task(task_id)

        if not db_task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if db_task.status != DBTaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed yet. Current status: {db_task.status.value}",
            )

        if not db_task.segments_json:
            raise HTTPException(
                status_code=404, detail="No segments found for this task"
            )

        # Parse segments from JSON
        from app.schemas.models import VideoSegment

        segments = [VideoSegment(**seg) for seg in db_task.segments_json]

        response = SegmentsResponse(
            task_id=task_id,
            segments=segments,
            total_duration=db_task.duration or 0.0,
            video_title=db_task.original_filename,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Segments retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Segments retrieval failed: {str(e)}"
        )


@router.get("/{task_id}/file")
async def get_video_file(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get the video file for a completed task

    - **task_id**: Task identifier
    - Returns video file (redirects to S3 signed URL or serves local file)
    """
    try:
        logger.info(f"Fetching video file for task: {task_id}")

        # Try to get from new Video model first
        from uuid import UUID

        from sqlalchemy import select

        from app.db.models import Video

        video_path = None
        try:
            task_uuid = UUID(task_id)
            result = await db.execute(select(Video).where(Video.task_id == task_uuid))
            video = result.scalar_one_or_none()
            if video:
                video_path = video.file_path
                logger.info(f"Found video in Video model: {video_path}")
        except (ValueError, Exception) as e:
            logger.debug(f"Not found in Video model or invalid UUID: {e}")

        # Fallback to old Task model
        if not video_path:
            task_service = TaskService(db)
            db_task = await task_service.get_task(task_id)
            if db_task:
                video_path = db_task.video_path
                logger.info(f"Found video in Task model: {video_path}")
            else:
                logger.error(f"Task not found in database: {task_id}")
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if not video_path:
            logger.error(f"No video path for task {task_id}")
            raise HTTPException(
                status_code=404, detail="Video file not found for this task"
            )

        # If S3 is enabled and path looks like S3 key
        if settings.S3_ENABLED and not video_path.startswith("/"):
            try:
                # Stream video from S3 through FastAPI
                logger.info(f"Streaming video from S3: {video_path}")

                # Detect media type from extension
                ext = Path(video_path).suffix.lower()
                media_type_map = {
                    ".mp4": "video/mp4",
                    ".avi": "video/x-msvideo",
                    ".mov": "video/quicktime",
                    ".mkv": "video/x-matroska",
                    ".webm": "video/webm",
                    ".flv": "video/x-flv",
                }
                media_type = media_type_map.get(ext, "video/mp4")

                # Get file from S3 and stream it
                async def stream_from_s3():
                    async for chunk in storage_service.stream_file(video_path):
                        yield chunk

                return StreamingResponse(
                    stream_from_s3(),
                    media_type=media_type,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "public, max-age=3600",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to stream from S3: {e}")
                # Fall back to local file if available

        # Local file serving
        local_path = Path(video_path)
        if not local_path.exists():
            # Try to find in uploads directory
            upload_files = list(settings.UPLOAD_DIR.glob(f"{task_id}_*"))
            if upload_files:
                local_path = upload_files[0]
            else:
                logger.error(f"Video file does not exist: {video_path}")
                raise HTTPException(status_code=404, detail="Video file not found")

        logger.info(f"Serving local video file: {local_path}")

        # Detect media type from extension
        ext = local_path.suffix.lower()
        media_type_map = {
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
            ".flv": "video/x-flv",
        }
        media_type = media_type_map.get(ext, "video/mp4")

        # Return video file with proper headers for streaming
        # Use ASCII-safe filename encoding for Content-Disposition
        from urllib.parse import quote

        encoded_filename = quote(local_path.name)

        return FileResponse(
            path=str(local_path),
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
                "Cache-Control": "public, max-age=3600",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video file retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Video file retrieval failed: {str(e)}"
        )


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a task and its associated data

    - **task_id**: Task identifier to delete
    """
    try:
        from app.services.pipeline import TASKS

        task_service = TaskService(db)
        success = await task_service.delete_task(task_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Also remove from memory
        if task_id in TASKS:
            del TASKS[task_id]

        logger.info(f"Task {task_id} deleted")

        return {"message": f"Task {task_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task deletion failed: {str(e)}")


@router.post("/{task_id}/share")
async def create_share_link(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Create a public share link for a task

    - **task_id**: Task identifier to share
    - Returns share token for public access
    """
    try:
        task_service = TaskService(db)
        share_token = await task_service.create_share_token(task_id)

        if not share_token:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        share_url = f"/shared/{share_token}"

        return {
            "share_token": share_token,
            "share_url": share_url,
            "message": "Share link created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Share link creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Share link creation failed: {str(e)}"
        )
