import asyncio
import base64
import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db, get_redis
from app.schemas.models import (
    TaskStatus,
    VideoUploadResponse,
    VideoURLRequest,
    VideoURLResponse,
)
from app.services.pipeline import (
    create_task,
    process_video_from_file,
    process_video_from_url,
)
from app.services.storage_service import storage_service
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/file", response_model=VideoUploadResponse)
async def upload_video_file(
    file: UploadFile = File(..., description="Video file to process"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video file for processing

    - **file**: Video file (mp4, avi, mov, etc.)
    - Returns task_id for tracking progress
    - Quizzes are generated in all three languages (ru, en, kk)
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Check file extension
        allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}",
            )

        # Save uploaded file first
        content = await file.read()

        # Calculate file hash for duplicate detection
        file_hash = hashlib.sha256(content).hexdigest()

        # Check for duplicates
        task_service = TaskService(db)
        existing_task = await task_service.find_duplicate_by_hash(file_hash)

        if existing_task:
            logger.info(
                f"Found duplicate file with hash {file_hash}, returning existing task {existing_task.id}"
            )
            return VideoUploadResponse(
                task_id=str(existing_task.id),
                status=TaskStatus.COMPLETED,
                message="This video has already been processed. Returning existing results.",
            )

        # Create task in memory
        task_id = create_task()

        # Save file locally first
        upload_path = settings.UPLOAD_DIR / f"{task_id}_{file.filename}"
        with open(upload_path, "wb") as f:
            f.write(content)

        logger.info(f"File uploaded locally: {upload_path} ({len(content)} bytes)")

        # Upload to S3 if enabled
        s3_key = None
        if settings.S3_ENABLED:
            try:
                s3_key = storage_service.get_object_key_for_task(task_id, file.filename)
                # Detect content type
                content_type_map = {
                    ".mp4": "video/mp4",
                    ".avi": "video/x-msvideo",
                    ".mov": "video/quicktime",
                    ".mkv": "video/x-matroska",
                    ".webm": "video/webm",
                    ".flv": "video/x-flv",
                }
                content_type = content_type_map.get(file_ext, "video/mp4")

                # Encode non-ASCII filename for S3 metadata
                encoded_filename = base64.b64encode(
                    file.filename.encode("utf-8")
                ).decode("ascii")

                await storage_service.upload_file(
                    upload_path,
                    s3_key,
                    content_type=content_type,
                    metadata={
                        "task_id": task_id,
                        "original_filename_base64": encoded_filename,
                    },
                )
                logger.info(f"File uploaded to S3: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to upload to S3: {e}")
                logger.warning("Continuing with local storage")

        # Create task in database
        redis = await get_redis()
        db_task_service = TaskService(db, redis)
        await db_task_service.create_task(
            task_id=task_id,
            original_filename=file.filename,
            video_path=s3_key if s3_key else str(upload_path),
            file_size=len(content),
            file_hash=file_hash,
        )

        # Start processing in background (non-blocking)
        asyncio.create_task(process_video_from_file(task_id, upload_path))

        return VideoUploadResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="Video upload successful. Processing started.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/url", response_model=VideoURLResponse)
async def upload_video_url(
    request: VideoURLRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a YouTube URL for processing

    - **video_url**: YouTube URL (e.g., https://www.youtube.com/watch?v=...)
    - Returns task_id for tracking progress
    - Quizzes are generated in all three languages (ru, en, kk)
    """
    try:
        url = str(request.url)
        logger.info(f"Received URL: {url}")

        # Sanitize URL - remove any shell escape characters
        url = url.replace("\\", "")

        # Basic validation
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL format. URL must start with http:// or https://",
            )

        # Create task in memory
        task_id = create_task(source_url=url)

        # Create task in database
        redis = await get_redis()
        task_service = TaskService(db, redis)
        await task_service.create_task(
            task_id=task_id,
            original_filename=f"youtube_{task_id[:8]}.mp4",
            video_path=f"temp/{task_id}/video.mp4",  # Will be updated after download
            file_size=None,
            file_hash=None,
        )

        # Start processing in background
        asyncio.create_task(process_video_from_url(task_id, url))

        return VideoURLResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL submission failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"URL processing failed: {str(e)}")
