import gc
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

import av
import torch
import yt_dlp

from app.core.config import settings
from app.schemas.models import VideoMetadata

logger = logging.getLogger(__name__)


def clear_vram():
    """Clear GPU VRAM cache"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
        logger.info("VRAM cache cleared")


def get_vram_usage() -> tuple[float, float]:
    """Get current VRAM usage in GB"""
    if not torch.cuda.is_available():
        return 0.0, 0.0

    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    return allocated, reserved


def check_vram_available(required_gb: float = 2.0) -> bool:
    """Check if enough VRAM is available"""
    if not torch.cuda.is_available():
        return False

    allocated, reserved = get_vram_usage()
    available = settings.MAX_VRAM_GB - allocated
    return available >= required_gb


def unload_model(model: Any) -> None:
    """Safely unload a model and free VRAM"""
    if model is not None:
        del model
        clear_vram()
        logger.info("Model unloaded and VRAM freed")


def download_youtube_video(url: str, output_path: Path) -> Path:
    """
    Download video from YouTube URL using yt-dlp

    Args:
        url: YouTube video URL
        output_path: Directory to save video

    Returns:
        Path to downloaded video file

    Raises:
        Exception: If download fails
    """
    output_path.mkdir(parents=True, exist_ok=True)
    output_template = str(output_path / "%(id)s.%(ext)s")

    ydl_opts: dict[str, Any] = {
        "format": settings.YT_DLP_FORMAT,
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading video from: {url}")
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", "video") if info else "video"
            ext = info.get("ext", "mp4") if info else "mp4"
            video_path = output_path / f"{video_id}.{ext}"

            if not video_path.exists():
                raise FileNotFoundError(f"Downloaded file not found: {video_path}")

            logger.info(f"Video downloaded successfully: {video_path}")
            return video_path

    except Exception as e:
        logger.error(f"Failed to download video: {e}")
        raise Exception(f"Video download failed: {str(e)}")


def get_video_metadata(video_path: Path) -> VideoMetadata:
    """
    Extract video metadata using PyAV

    Args:
        video_path: Path to video file

    Returns:
        VideoMetadata object
    """
    try:
        container = av.open(str(video_path))
        video_stream = container.streams.video[0]

        duration = container.duration if container.duration else 0
        fps_rate = video_stream.average_rate if video_stream.average_rate else 30

        metadata = VideoMetadata(
            duration=float(duration / av.time_base) if duration else 0.0,
            fps=float(fps_rate),
            width=video_stream.width or 0,
            height=video_stream.height or 0,
            format=container.format.name if container.format else "unknown",
        )

        container.close()
        logger.info(f"Video metadata extracted: {metadata.duration}s")
        return metadata

    except Exception as e:
        logger.error(f"Failed to extract video metadata: {e}")
        raise Exception(f"Metadata extraction failed: {str(e)}")


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """
    Extract audio from video using ffmpeg

    Args:
        video_path: Path to video file
        output_path: Output audio file path

    Returns:
        Path to extracted audio file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",  # No video
        "-acodec",
        "pcm_s16le",  # PCM 16-bit
        "-ar",
        "16000",  # 16kHz sample rate
        "-ac",
        "1",  # Mono
        "-y",  # Overwrite
        str(output_path),
    ]

    try:
        logger.info(f"Extracting audio from: {video_path}")
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
        logger.info(f"Audio extracted successfully: {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("Audio extraction timed out")
        raise Exception("Audio extraction timeout (10 minutes)")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr}")
        raise Exception(f"Audio extraction failed: {e.stderr}")


def extract_frames(
    video_path: Path, output_dir: Path, fps: Optional[float] = None
) -> list[Path]:
    """
    Extract frames from video at specified FPS

    Args:
        video_path: Path to video file
        output_dir: Directory to save frames
        fps: Frames per second to extract (default from settings)

    Returns:
        List of paths to extracted frame images
    """
    if fps is None:
        fps = settings.FRAME_EXTRACTION_FPS

    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = []

    try:
        container = av.open(str(video_path))
        video_stream = container.streams.video[0]

        # Calculate frame interval
        avg_rate = video_stream.average_rate if video_stream.average_rate else 30
        video_fps = float(avg_rate)
        frame_interval = int(video_fps / fps) if fps < video_fps else 1

        logger.info(f"Extracting frames at {fps} FPS (interval: {frame_interval})")

        frame_count = 0
        extracted_count = 0

        for frame in container.decode(video=0):
            if frame_count % frame_interval == 0:
                if extracted_count >= settings.MAX_FRAMES_PER_VIDEO:
                    logger.warning(
                        f"Reached max frame limit: {settings.MAX_FRAMES_PER_VIDEO}"
                    )
                    break

                # Convert to PIL Image
                img = frame.to_image()

                # Save frame
                pts = frame.pts if frame.pts else 0
                time_base = video_stream.time_base if video_stream.time_base else 1
                timestamp = float(pts * time_base)
                frame_filename = f"frame_{timestamp:.2f}s.jpg"
                frame_path = output_dir / frame_filename

                img.save(frame_path, "JPEG", quality=85)
                frame_paths.append(frame_path)
                extracted_count += 1

            frame_count += 1

        container.close()
        logger.info(f"Extracted {extracted_count} frames to {output_dir}")
        return frame_paths

    except Exception as e:
        logger.error(f"Failed to extract frames: {e}")
        raise Exception(f"Frame extraction failed: {str(e)}")


def validate_video_file(file_path: Path) -> bool:
    """
    Validate video file size and format

    Args:
        file_path: Path to video file

    Returns:
        True if valid, raises exception otherwise
    """
    # Check file exists
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    # Check file size
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.MAX_VIDEO_SIZE_MB:
        raise ValueError(
            f"Video file too large: {file_size_mb:.2f}MB (max: {settings.MAX_VIDEO_SIZE_MB}MB)"
        )

    # Check video can be opened
    try:
        container = av.open(str(file_path))
        if not container.streams.video:
            raise ValueError("No video stream found in file")

        # Check duration
        duration = container.duration if container.duration else 0
        duration_minutes = duration / av.time_base / 60 if duration else 0
        if duration_minutes > settings.MAX_VIDEO_DURATION_MINUTES:
            raise ValueError(
                f"Video too long: {duration_minutes:.1f} minutes (max: {settings.MAX_VIDEO_DURATION_MINUTES} minutes)"
            )

        container.close()
        return True

    except Exception as e:
        raise ValueError(f"Invalid video file: {str(e)}")


def cleanup_temp_files(*paths: Path):
    """
    Clean up temporary files and directories

    Args:
        *paths: Variable number of paths to delete
    """
    for path in paths:
        try:
            if path.exists():
                if path.is_file():
                    path.unlink()
                    logger.info(f"Deleted file: {path}")
                elif path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")
