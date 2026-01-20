import logging

from fastapi import APIRouter

from app.api.endpoints import general, upload, video

logger = logging.getLogger(__name__)

# Create main API router
router = APIRouter(prefix="/api")

# Include sub-routers
router.include_router(upload.router)  # /api/upload/file, /api/upload/url
router.include_router(video.router)  # /api/video/{task_id}/...
router.include_router(general.router)  # /api/health, /api/history, /api/shared/{token}

logger.info("API routes initialized")
