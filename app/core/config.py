from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with hardware constraints"""

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

    # Hardware constraints (CRITICAL - 8GB VRAM limit)
    MAX_VRAM_GB: float = 6.5  # Leave buffer for system
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "float16"  # Use FP16 for memory efficiency

    # Model paths and settings
    WHISPER_MODEL: str = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"

    QWEN_MODEL_PATH: str = str(BASE_DIR / "models" / "qwen2-vl-2b")
    QWEN_MAX_PIXELS: int = 360 * 420  # Reduced for VRAM
    QWEN_MIN_PIXELS: int = 224 * 224

    # Ollama settings (for LLM)
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
    LLAMA_MAX_LENGTH: int = 4096
    LLAMA_TEMPERATURE: float = 0.7

    # Video processing settings
    MAX_VIDEO_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_MINUTES: int = 60
    FRAME_EXTRACTION_FPS: float = 0.1  # 1 frame per 10 seconds
    MAX_FRAMES_PER_VIDEO: int = 100

    # Processing settings
    CHUNK_DURATION_SECONDS: int = 30  # Audio chunk size
    MIN_SEGMENT_DURATION: int = 30  # Minimum segment length
    MAX_SEGMENT_DURATION: int = 300  # Maximum segment length (5 min)

    # Quiz generation settings
    QUIZZES_PER_SEGMENT: int = 2
    QUIZ_OPTIONS_COUNT: int = 4

    # Task management
    TASK_TIMEOUT_SECONDS: int = 3600  # 1 hour max
    CLEANUP_TEMP_FILES_AFTER_SECONDS: int = 86400  # 24 hours

    # YouTube download settings
    YT_DLP_FORMAT: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    YT_DLP_MAX_FILESIZE: str = "500M"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Create necessary directories
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
