import logging
import os
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

from app.core.config import settings
from app.schemas.models import TranscriptionSegment
from app.utils.video_utils import clear_vram, get_vram_usage

logger = logging.getLogger(__name__)


class ASRService:
    """Automatic Speech Recognition service using faster-whisper"""

    def __init__(self):
        self.model: Optional[WhisperModel] = None
        self.model_loaded = False

    def load_model(self):
        """Load Whisper model with memory optimization"""
        if self.model_loaded:
            logger.info("Whisper model already loaded")
            return

        try:
            logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
            allocated, reserved = get_vram_usage()
            logger.info(
                f"VRAM before loading: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
            )

            # Set HuggingFace cache to models directory for whisper
            os.environ["HF_HOME"] = str(settings.MODELS_DIR / "whisper")
            os.environ["HF_HUB_CACHE"] = str(settings.MODELS_DIR / "whisper")

            # Use the model specified in settings
            model_name = settings.WHISPER_MODEL

            self.model = WhisperModel(
                model_name,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
                download_root=str(settings.MODELS_DIR / "whisper"),
            )

            self.model_loaded = True
            allocated, reserved = get_vram_usage()
            logger.info("Whisper model loaded successfully")
            logger.info(
                f"VRAM after loading: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
            )

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model_loaded = False
            raise Exception(f"ASR model loading failed: {str(e)}")

    def unload_model(self):
        """Unload model and free VRAM"""
        if self.model is not None:
            del self.model
            self.model = None
            self.model_loaded = False

            # Only clear VRAM if not keeping models in memory
            if not settings.MODELS_STAY_IN_MEMORY:
                clear_vram()

            logger.info("Whisper model unloaded")

    def transcribe(
        self, audio_path: Path, language: Optional[str] = None, task: str = "transcribe"
    ) -> List[TranscriptionSegment]:
        """
        Transcribe audio file to text

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'es'). Auto-detect if None
            task: 'transcribe' or 'translate' (to English)

        Returns:
            List of TranscriptionSegment objects with timestamps

        Raises:
            Exception: If transcription fails
        """
        if not self.model_loaded:
            self.load_model()

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if self.model is None:
            raise Exception("Whisper model not loaded")

        try:
            logger.info(f"Starting transcription: {audio_path}")
            logger.info(f"Language: {language or 'auto-detect'}, Task: {task}")
            logger.info(f"Batch size: {settings.WHISPER_BATCH_SIZE}")

            # Transcribe with faster-whisper (with batching)
            # Note: batch_size parameter requires faster-whisper >= 0.9.0
            transcribe_kwargs = {
                "language": language,
                "task": task,
                "beam_size": 5,
                "best_of": 5,
                "temperature": 0.0,
                "vad_filter": True,
                "vad_parameters": {
                    "min_silence_duration_ms": 500,
                    "threshold": 0.5,
                },
            }

            # Try with batch_size first (newer versions of faster-whisper)
            if (
                hasattr(settings, "WHISPER_BATCH_SIZE")
                and settings.WHISPER_BATCH_SIZE > 1
            ):
                transcribe_kwargs["batch_size"] = settings.WHISPER_BATCH_SIZE

            try:
                segments, info = self.model.transcribe(
                    str(audio_path), **transcribe_kwargs
                )
            except TypeError as e:
                if "batch_size" in str(e):
                    # batch_size not supported, retry without it
                    logger.warning(
                        "batch_size parameter not supported in this version of faster-whisper, retrying without it"
                    )
                    transcribe_kwargs.pop("batch_size", None)
                    segments, info = self.model.transcribe(
                        str(audio_path), **transcribe_kwargs
                    )
                else:
                    raise

            # Log detected language
            logger.info(
                f"Detected language: {info.language} (probability: {info.language_probability:.2f})"
            )

            # Convert to TranscriptionSegment objects
            transcription_segments = []
            total_text = ""

            for segment in segments:
                trans_segment = TranscriptionSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=segment.avg_logprob
                    if hasattr(segment, "avg_logprob")
                    else None,
                )
                transcription_segments.append(trans_segment)
                total_text += segment.text.strip() + " "

                logger.debug(
                    f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text.strip()}"
                )

            logger.info(
                f"Transcription completed: {len(transcription_segments)} segments, "
                f"{len(total_text)} characters"
            )

            return transcription_segments

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise Exception(f"ASR transcription failed: {str(e)}")

        finally:
            # Free VRAM after transcription only if not keeping models in memory
            if not settings.MODELS_STAY_IN_MEMORY:
                clear_vram()

    def get_full_transcript(self, segments: List[TranscriptionSegment]) -> str:
        """
        Combine all segments into full transcript

        Args:
            segments: List of transcription segments

        Returns:
            Full transcript text
        """
        return " ".join(segment.text for segment in segments)

    def get_transcript_for_timerange(
        self, segments: List[TranscriptionSegment], start_time: float, end_time: float
    ) -> str:
        """
        Get transcript text for a specific time range

        Args:
            segments: List of transcription segments
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Transcript text within the time range
        """
        text_parts = []

        for segment in segments:
            # Check if segment overlaps with time range
            if segment.end >= start_time and segment.start <= end_time:
                text_parts.append(segment.text)

        return " ".join(text_parts)
