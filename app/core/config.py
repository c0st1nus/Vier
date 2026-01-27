import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import torch
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class HardwareProfile(str, Enum):
    """Hardware profile types"""

    AUTO = "auto"
    LAPTOP = "laptop"
    PRODUCTION = "production"
    CUSTOM = "custom"


def detect_vram() -> float:
    """Detect available VRAM in GB"""
    try:
        if torch.cuda.is_available():
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = vram_bytes / (1024**3)
            logger.info(f"Detected VRAM: {vram_gb:.2f} GB")
            return vram_gb
        else:
            logger.warning("CUDA not available, defaulting to CPU mode")
            return 0.0
    except Exception as e:
        logger.warning(f"Failed to detect VRAM: {e}")
        return 0.0


def auto_select_profile(vram_gb: float) -> HardwareProfile:
    """Automatically select profile based on available VRAM"""
    if vram_gb >= 20.0:
        logger.info(f"Auto-selected PRODUCTION profile ({vram_gb:.1f}GB VRAM)")
        return HardwareProfile.PRODUCTION
    elif vram_gb >= 6.0:
        logger.info(f"Auto-selected LAPTOP profile ({vram_gb:.1f}GB VRAM)")
        return HardwareProfile.LAPTOP
    else:
        logger.warning(
            f"Insufficient VRAM ({vram_gb:.1f}GB), using LAPTOP profile with reduced settings"
        )
        return HardwareProfile.LAPTOP


class BaseAppSettings(BaseSettings):
    """Base settings shared across all profiles"""

    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    MODELS_DIR: Path = BASE_DIR / "models"
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMP_DIR: Path = BASE_DIR / "temp"

    # API settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "AI Video Quiz Generator"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Authentication settings
    SECRET_KEY: str = "your-secret-key-change-in-production-please-use-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days

    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vier"
    DATABASE_ECHO: bool = False

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour

    # S3/MinIO settings
    S3_ENABLED: bool = True
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "vier-videos"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    S3_PUBLIC_URL: Optional[str] = None
    S3_SIGNED_URL_EXPIRY: int = 3600

    # Hardware profile selection
    HARDWARE_PROFILE: str = "auto"  # auto, laptop, production, custom

    # Task management
    TASK_TIMEOUT_SECONDS: int = 3600  # 1 hour max
    CLEANUP_TEMP_FILES_AFTER_SECONDS: int = 86400  # 24 hours

    # YouTube download settings
    YT_DLP_FORMAT: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    YT_DLP_MAX_FILESIZE: str = "500M"
    YT_DLP_COOKIES_FILE: Optional[str] = (
        None  # Path to YouTube cookies file (e.g., "youtube_cookies.txt")
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",  # Allow extra fields from .env
    )


class LaptopSettings(BaseAppSettings):
    """Settings optimized for laptop with 8GB VRAM (RTX 3070, 4060 Ti, etc.)"""

    # Hardware constraints
    MAX_VRAM_GB: float = 6.5  # Leave buffer for system
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "float16"
    USE_TORCH_COMPILE: bool = False  # Skip compilation for faster startup

    # Model loading strategy
    PRELOAD_ALL_MODELS: bool = False  # Load/unload models sequentially
    MODELS_STAY_IN_MEMORY: bool = False  # Unload after each stage

    # Whisper settings (memory-optimized)
    WHISPER_MODEL: str = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "int8"  # Use int8 for lower memory (~3GB)
    WHISPER_BATCH_SIZE: int = 1  # Process one at a time

    # Qwen2-VL settings (memory-optimized)
    QWEN_MODEL_PATH: str = "models/qwen2-vl-2b"
    QWEN_MAX_PIXELS: int = 360 * 420  # Reduced resolution
    QWEN_MIN_PIXELS: int = 224 * 224
    QWEN_BATCH_SIZE: int = 1  # Process one frame at a time
    QWEN_USE_FLASH_ATTENTION: bool = False  # May not be available
    QWEN_USE_TORCH_COMPILE: bool = False

    # Ollama/LLM settings
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"  # Quantized model (~5GB)
    LLAMA_MAX_LENGTH: int = 4096
    LLAMA_TEMPERATURE: float = 0.7
    USE_VLLM: bool = False  # Use Ollama instead

    # Video processing settings
    MAX_VIDEO_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_MINUTES: int = 60
    FRAME_EXTRACTION_FPS: float = 0.1  # 1 frame per 10 seconds
    MAX_FRAMES_PER_VIDEO: int = 100

    # Processing settings
    CHUNK_DURATION_SECONDS: int = 30
    MIN_SEGMENT_DURATION: int = 30
    MAX_SEGMENT_DURATION: int = 300

    # Quiz generation settings
    QUIZZES_PER_SEGMENT: int = 2
    SHORT_ANSWER_QUIZZES_PER_SEGMENT: int = 1
    QUIZ_OPTIONS_COUNT: int = 4
    QUIZ_BATCH_SIZE: int = 1  # Generate one quiz at a time


class ProductionSettings(BaseAppSettings):
    """Settings optimized for production server with 40GB VRAM (L40S, A100, etc.)"""

    # Hardware constraints
    MAX_VRAM_GB: float = 38.0  # Leave buffer for system
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "bfloat16"  # Better than float16 for newer GPUs
    USE_TORCH_COMPILE: bool = True  # Enable compilation for speed

    # Model loading strategy
    PRELOAD_ALL_MODELS: bool = True  # Keep all models in memory
    MODELS_STAY_IN_MEMORY: bool = True  # Never unload

    # Whisper settings (high quality)
    WHISPER_MODEL: str = "large-v3"  # Full large-v3 model
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"  # Full precision (~6GB)
    WHISPER_BATCH_SIZE: int = 16  # Batch processing for speed

    # Qwen2-VL settings (optimized)
    QWEN_MODEL_PATH: str = "models/qwen2-vl-2b"
    QWEN_MAX_PIXELS: int = 720 * 840  # Higher resolution
    QWEN_MIN_PIXELS: int = 224 * 224
    QWEN_BATCH_SIZE: int = 8  # Batch process frames
    QWEN_USE_FLASH_ATTENTION: bool = True  # Enable Flash Attention 2
    QWEN_USE_TORCH_COMPILE: bool = True  # Compile for speed

    # vLLM settings (replaces Ollama for speed)
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b-instruct-q4_K_M"  # Larger model
    LLAMA_MAX_LENGTH: int = 8192  # Longer context
    LLAMA_TEMPERATURE: float = 0.7

    # vLLM configuration (if enabled)
    USE_VLLM: bool = False  # Set to True to use vLLM instead of Ollama
    VLLM_MODEL: str = "Qwen/Qwen2.5-14B-Instruct"  # Can use 14B model
    VLLM_TENSOR_PARALLEL_SIZE: int = 1
    VLLM_GPU_MEMORY_UTILIZATION: float = 0.3  # ~12GB for LLM
    VLLM_MAX_MODEL_LEN: int = 8192
    VLLM_DTYPE: str = "float16"

    # Video processing settings (more aggressive)
    MAX_VIDEO_SIZE_MB: int = 1000  # Allow larger videos
    MAX_VIDEO_DURATION_MINUTES: int = 120  # Up to 2 hours
    FRAME_EXTRACTION_FPS: float = 0.2  # 1 frame per 5 seconds (more frames)
    MAX_FRAMES_PER_VIDEO: int = 200  # More frames for better analysis

    # Processing settings
    CHUNK_DURATION_SECONDS: int = 30
    MIN_SEGMENT_DURATION: int = 30
    MAX_SEGMENT_DURATION: int = 300

    # Quiz generation settings
    QUIZZES_PER_SEGMENT: int = 3  # More quizzes per segment
    SHORT_ANSWER_QUIZZES_PER_SEGMENT: int = 1
    QUIZ_OPTIONS_COUNT: int = 4
    QUIZ_BATCH_SIZE: int = 5  # Batch generate quizzes


class CustomSettings(BaseAppSettings):
    """Custom settings - all configurable via environment variables"""

    # Hardware constraints
    MAX_VRAM_GB: float = 6.5
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "float16"
    USE_TORCH_COMPILE: bool = False

    # Model loading strategy
    PRELOAD_ALL_MODELS: bool = False
    MODELS_STAY_IN_MEMORY: bool = False

    # Whisper settings
    WHISPER_MODEL: str = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_BATCH_SIZE: int = 1

    # Qwen2-VL settings
    QWEN_MODEL_PATH: str = "models/qwen2-vl-2b"
    QWEN_MAX_PIXELS: int = 360 * 420
    QWEN_MIN_PIXELS: int = 224 * 224
    QWEN_BATCH_SIZE: int = 1
    QWEN_USE_FLASH_ATTENTION: bool = False
    QWEN_USE_TORCH_COMPILE: bool = False

    # Ollama/LLM settings
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
    LLAMA_MAX_LENGTH: int = 4096
    LLAMA_TEMPERATURE: float = 0.7
    USE_VLLM: bool = False

    # vLLM (optional)
    VLLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    VLLM_TENSOR_PARALLEL_SIZE: int = 1
    VLLM_GPU_MEMORY_UTILIZATION: float = 0.25
    VLLM_MAX_MODEL_LEN: int = 4096
    VLLM_DTYPE: str = "float16"

    # Video processing settings
    MAX_VIDEO_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_MINUTES: int = 60
    FRAME_EXTRACTION_FPS: float = 0.1
    MAX_FRAMES_PER_VIDEO: int = 100

    # Processing settings
    CHUNK_DURATION_SECONDS: int = 30
    MIN_SEGMENT_DURATION: int = 30
    MAX_SEGMENT_DURATION: int = 300

    # Quiz generation settings
    QUIZZES_PER_SEGMENT: int = 2
    SHORT_ANSWER_QUIZZES_PER_SEGMENT: int = 1
    QUIZ_OPTIONS_COUNT: int = 4
    QUIZ_BATCH_SIZE: int = 1


def get_settings() -> Union[LaptopSettings, ProductionSettings, CustomSettings]:
    """
    Get settings based on HARDWARE_PROFILE environment variable

    Returns:
        Appropriate settings instance based on profile
    """
    # Load base settings to get profile choice
    base = BaseAppSettings()
    profile_str = base.HARDWARE_PROFILE.lower()

    # Parse profile
    try:
        profile = HardwareProfile(profile_str)
    except ValueError:
        logger.warning(
            f"Invalid HARDWARE_PROFILE '{profile_str}', defaulting to 'auto'"
        )
        profile = HardwareProfile.AUTO

    # Auto-detect if needed
    if profile == HardwareProfile.AUTO:
        vram = detect_vram()
        profile = auto_select_profile(vram)

    # Load appropriate settings
    if profile == HardwareProfile.LAPTOP:
        logger.info("🏠 Loading LAPTOP profile (8GB VRAM optimized)")
        return LaptopSettings()
    elif profile == HardwareProfile.PRODUCTION:
        logger.info("🚀 Loading PRODUCTION profile (40GB VRAM optimized)")
        return ProductionSettings()
    elif profile == HardwareProfile.CUSTOM:
        logger.info("🔧 Loading CUSTOM profile (from .env)")
        return CustomSettings()
    else:
        logger.warning(f"Unknown profile {profile}, defaulting to LAPTOP")
        return LaptopSettings()


# Global settings instance
settings = get_settings()

# Log active configuration
logger.info("Active configuration:")
logger.info(f"  - VRAM limit: {settings.MAX_VRAM_GB}GB")
logger.info(f"  - Torch dtype: {settings.TORCH_DTYPE}")
logger.info(f"  - Preload models: {settings.PRELOAD_ALL_MODELS}")
logger.info(f"  - Whisper: {settings.WHISPER_MODEL} ({settings.WHISPER_COMPUTE_TYPE})")
logger.info(f"  - Whisper batch size: {settings.WHISPER_BATCH_SIZE}")
logger.info(f"  - Qwen batch size: {settings.QWEN_BATCH_SIZE}")
logger.info(f"  - Flash Attention: {settings.QWEN_USE_FLASH_ATTENTION}")
logger.info(f"  - Torch compile: {settings.USE_TORCH_COMPILE}")
logger.info(f"  - Use vLLM: {settings.USE_VLLM}")

# Create necessary directories
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
