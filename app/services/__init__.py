"""
Services module for AI Video Quiz Generator

Contains:
- ASRService: Speech-to-text transcription using faster-whisper
- VisionService: Frame analysis using Qwen2-VL
- LLMService: Quiz generation and segmentation using Llama
- AuthService: Authentication and JWT token management
"""

from app.services.asr_service import ASRService
from app.services.auth_service import AuthService, auth_service
from app.services.llm_service import LLMService
from app.services.vision_service import VisionService

# TODO: Update pipeline to use new Video model
# from app.services.pipeline import (
#     VideoPipeline,
#     create_task,
#     get_task,
#     get_task_segments,
#     get_task_status,
#     process_video_from_file,
#     process_video_from_url,
# )

__all__ = [
    "ASRService",
    "VisionService",
    "LLMService",
    "AuthService",
    "auth_service",
    # "VideoPipeline",
    # "create_task",
    # "get_task",
    # "get_task_status",
    # "get_task_segments",
    # "process_video_from_file",
    # "process_video_from_url",
]
