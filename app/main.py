import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log"),
    ],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting AI Video Quiz Generator API")
    logger.info("=" * 60)
    logger.info(f"Project: {settings.PROJECT_NAME}")
    logger.info(f"Models directory: {settings.MODELS_DIR}")
    logger.info(f"Upload directory: {settings.UPLOAD_DIR}")
    logger.info(f"Temp directory: {settings.TEMP_DIR}")
    logger.info(f"Max VRAM: {settings.MAX_VRAM_GB} GB")
    logger.info(f"Device: {settings.DEVICE}")
    logger.info("=" * 60)

    # Check CUDA availability
    import torch

    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        logger.info(
            f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB"
        )
    else:
        logger.warning("CUDA not available - models will run on CPU (slow!)")

    yield

    # Shutdown
    logger.info("Shutting down API")
    logger.info("Cleaning up resources...")

    # Clean up old tasks
    try:
        from app.services.pipeline import cleanup_old_tasks

        cleanup_old_tasks(max_age_seconds=settings.CLEANUP_TEMP_FILES_AFTER_SECONDS)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered video quiz generator using open-source models",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Video Quiz Generator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/video/health",
    }


@app.get("/health")
async def health():
    """Simple health check"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
