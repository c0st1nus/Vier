import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.models import (
    SegmentsResponse,
    TaskStatusResponse,
    VideoUploadResponse,
    VideoURLRequest,
    VideoURLResponse,
)
from app.services.pipeline import (
    create_task,
    get_task,
    get_task_segments,
    get_task_status,
    process_video_from_file,
    process_video_from_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])


@router.post("/upload/file", response_model=VideoUploadResponse)
async def upload_video_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to process"),
):
    """
    Upload a video file for processing

    - **file**: Video file (mp4, avi, mov, etc.)
    - Returns task_id for tracking progress
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

        # Create task
        task_id = create_task()

        # Save uploaded file
        upload_path = settings.UPLOAD_DIR / f"{task_id}_{file.filename}"
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"File uploaded: {upload_path} ({len(content)} bytes)")

        # Start processing in background
        background_tasks.add_task(process_video_from_file, task_id, upload_path)

        return VideoUploadResponse(
            task_id=task_id,
            status="pending",
            message=f"Video upload successful. Processing started.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/url", response_model=VideoURLResponse)
async def upload_video_url(background_tasks: BackgroundTasks, request: VideoURLRequest):
    """
    Submit a video URL (YouTube, etc.) for processing

    - **url**: Video URL (YouTube or direct video link)
    - Returns task_id for tracking progress
    """
    try:
        url = str(request.url)
        logger.info(f"Received URL: {url}")

        # Create task
        task_id = create_task(source_url=url)

        # Start processing in background
        background_tasks.add_task(process_video_from_url, task_id, url)

        return VideoURLResponse(
            task_id=task_id,
            status="pending",
        )

    except Exception as e:
        logger.error(f"URL submission failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"URL processing failed: {str(e)}")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_video_status(task_id: str):
    """
    Get current processing status of a video task

    - **task_id**: Task identifier from upload response
    - Returns current status, progress, and stage information
    """
    try:
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
async def get_video_segments(task_id: str):
    """
    Get processed video segments with quizzes

    - **task_id**: Task identifier
    - Returns list of video segments with timestamps, summaries, and quiz questions
    - Only available after processing is completed
    """
    try:
        task = get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if task.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed yet. Current status: {task.status}",
            )

        segments = get_task_segments(task_id)

        if not segments:
            raise HTTPException(
                status_code=404, detail="No segments found for this task"
            )

        response = SegmentsResponse(
            task_id=task_id,
            segments=segments,
            total_duration=task.metadata.duration if task.metadata else 0.0,
            video_title=task.metadata.title if task.metadata else None,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Segments retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Segments retrieval failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint

    - Returns API status and configuration
    """
    import torch

    return {
        "status": "healthy",
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count()
        if torch.cuda.is_available()
        else 0,
        "models_dir": str(settings.MODELS_DIR),
        "max_vram_gb": settings.MAX_VRAM_GB,
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    Delete a task and its associated data

    - **task_id**: Task identifier to delete
    """
    try:
        from app.services.pipeline import TASKS
        from app.utils.video_utils import cleanup_temp_files

        task = TASKS.get(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Clean up files
        if task.video_path:
            cleanup_temp_files(Path(task.video_path))
        if task.audio_path:
            cleanup_temp_files(Path(task.audio_path))

        # Remove task
        del TASKS[task_id]

        logger.info(f"Task {task_id} deleted")

        return {"message": f"Task {task_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task deletion failed: {str(e)}")
