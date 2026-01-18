#!/usr/bin/env python3
"""
AI Video Quiz Generator - Startup Script

This script starts the FastAPI server with proper configuration.
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def check_requirements():
    """Check if all required dependencies are installed"""
    try:
        import av
        import faster_whisper
        import torch
        import transformers
        import yt_dlp

        logger.info("✓ All required packages are installed")

        # Check CUDA
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"✓ CUDA available: {device_name}")
            logger.info(f"✓ GPU Memory: {total_memory:.2f} GB")
        else:
            logger.warning("⚠ CUDA not available - models will run on CPU (very slow!)")

        return True

    except ImportError as e:
        logger.error(f"✗ Missing required package: {e}")
        logger.error("Please run: pip install -r requirements.txt")
        return False


def check_directories():
    """Ensure all required directories exist"""
    dirs = [
        settings.MODELS_DIR,
        settings.UPLOAD_DIR,
        settings.TEMP_DIR,
    ]

    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Directory ready: {directory}")

    return True


def main():
    """Main entry point"""
    logger.info("=" * 70)
    logger.info("AI Video Quiz Generator - Starting Server")
    logger.info("=" * 70)

    # Check requirements
    if not check_requirements():
        sys.exit(1)

    # Check directories
    if not check_directories():
        sys.exit(1)

    # Display configuration
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Host: {settings.HOST}")
    logger.info(f"  Port: {settings.PORT}")
    logger.info(f"  Debug: {settings.DEBUG}")
    logger.info(f"  Max VRAM: {settings.MAX_VRAM_GB} GB")
    logger.info(f"  Models Dir: {settings.MODELS_DIR}")
    logger.info("")
    logger.info("=" * 70)
    logger.info("Starting server...")
    logger.info(
        f"API Docs will be available at: http://{settings.HOST}:{settings.PORT}/docs"
    )
    logger.info("=" * 70)
    logger.info("")

    # Start server
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info",
            access_log=True,
        )
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
