import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db

# from app.db.models import TaskStatus as DBTaskStatus  # OLD - commented out
# from app.services.task_service import TaskService  # OLD - commented out

logger = logging.getLogger(__name__)

router = APIRouter(tags=["general"])


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


# TODO: Update this endpoint to use new Video model
# @router.get("/history")
# async def get_task_history(
#     limit: int = 100,
#     offset: int = 0,
#     status: Optional[str] = None,
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Get history of all processed videos
#
#     - **limit**: Maximum number of tasks to return (default: 100)
#     - **offset**: Offset for pagination (default: 0)
#     - **status**: Filter by status (pending, processing, completed, failed)
#     - Returns list of tasks with metadata
#     """
#     try:
#         task_service = TaskService(db)
#
#         # Convert status string to enum if provided
#         status_filter = None
#         if status:
#             try:
#                 status_filter = DBTaskStatus(status)
#             except ValueError:
#                 raise HTTPException(
#                     status_code=400,
#                     detail=f"Invalid status: {status}. Must be one of: pending, processing, completed, failed",
#                 )
#
#         tasks = await task_service.get_all_tasks(
#             limit=limit, offset=offset, status=status_filter
#         )

#         return {
#             "tasks": [task.to_summary() for task in tasks],
#             "total": len(tasks),
#             "limit": limit,
#             "offset": offset,
#         }
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"History retrieval failed: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=500, detail=f"History retrieval failed: {str(e)}"
#         )


# TODO: Update this endpoint to use new Video model
# @router.get("/shared/{share_token}")
# async def get_shared_task(share_token: str, db: AsyncSession = Depends(get_db)):
#     """
#     Get task details by share token (public access)
#
#     - **share_token**: Share token from share link
#     - Returns task details and segments
#     """
#     try:
#         task_service = TaskService(db)
#         task = await task_service.get_task_by_share_token(share_token)
#
#         if not task:
#             raise HTTPException(status_code=404, detail="Shared video not found")
#
#         if not task.is_public:
#             raise HTTPException(
#                 status_code=403, detail="This video is not publicly shared"
#             )
#
#         return task.to_dict()
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Shared task retrieval failed: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=500, detail=f"Shared task retrieval failed: {str(e)}"
#         )
