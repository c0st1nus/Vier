import logging

from fastapi import APIRouter

from app.api.endpoints import auth, general, quiz, user, video, video_new, websocket

# from app.api.endpoints import upload  # TODO: Update to use new Video model

logger = logging.getLogger(__name__)

# Create main API router
router = APIRouter(prefix="/api")

# Include sub-routers
router.include_router(auth.router)  # /api/auth/register, /api/auth/login, etc.
router.include_router(
    video_new.router
)  # /api/video/upload/url, /api/video/{task_id}/segments
router.include_router(quiz.router)  # /api/quiz/{quiz_id}/answer, etc.
router.include_router(user.router)  # /api/user/profile, /api/user/stats, etc.
router.include_router(websocket.router)  # /api/video/ws/{task_id}
router.include_router(video.router)  # /api/video/{task_id}/file
# TODO: Update upload router to use new Video model
# router.include_router(upload.router)  # /api/upload/file, /api/upload/url
router.include_router(
    general.router
)  # /api/health, /api/history (commented out old endpoints)

logger.info("API routes initialized")
