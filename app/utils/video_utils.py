import gc
import logging
import re
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


def normalize_youtube_url(url: str) -> str:
    """
    Normalize various YouTube URL formats (watch, shorts, youtu.be, embed) to a canonical watch URL.
    """
    # Extract 11-char video id from known patterns
    patterns = [
        r"(?:v=)([\w-]{11})",  # watch?v=
        r"youtu\.be/([\w-]{11})",  # youtu.be/ID
        r"youtube\.com/embed/([\w-]{11})",  # embed/ID
        r"youtube\.com/shorts/([\w-]{11})",  # shorts/ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            vid = match.group(1)
            normalized = f"https://www.youtube.com/watch?v={vid}"
            logger.info(f"Normalized URL: {normalized}")
            return normalized
    return url


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
    # Sanitize URL - remove shell escape characters
    url = url.replace("\\", "")
    logger.info(f"Sanitized URL: {url}")

    # Normalize URL to strip playlist/index params and keep only video id
    url = normalize_youtube_url(url)

    # Check for cookies file
    cookies_file = None
    has_cookies_file = False

    if settings.YT_DLP_COOKIES_FILE:
        cookies_file = Path(settings.YT_DLP_COOKIES_FILE)
        if not cookies_file.is_absolute():
            cookies_file = settings.BASE_DIR / settings.YT_DLP_COOKIES_FILE
    else:
        # Default location
        cookies_file = settings.BASE_DIR / "youtube_cookies.txt"

    if cookies_file and cookies_file.exists():
        has_cookies_file = True
        logger.info(f"Using cookies file: {cookies_file}")

    # Validate YouTube URL
    youtube_patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
    ]

    is_youtube_url = any(re.match(pattern, url) for pattern in youtube_patterns)

    if not is_youtube_url:
        logger.warning(f"URL does not appear to be a valid YouTube video URL: {url}")

    output_path.mkdir(parents=True, exist_ok=True)
    output_template = str(output_path / "%(id)s.%(ext)s")

    ydl_opts: dict[str, Any] = {
        "format": settings.YT_DLP_FORMAT,
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
        "noplaylist": True,  # Don't download playlists
        "retries": 5,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "http_chunk_size": 10 * 1024 * 1024,
        # Anti-bot detection options: prefer non-web clients to avoid SABR
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv_embedded"],
                "player_skip": ["webpage", "configs"],
            }
        },
        # Additional headers to appear more like a real browser
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
    }

    # Add cookies if available
    if has_cookies_file:
        ydl_opts["cookiefile"] = str(cookies_file)

    def _download_with_opts(opts: dict[str, Any]) -> Path:
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore
            logger.info(f"Downloading video from: {url}")

            # Try to extract info first without downloading to validate
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("No video information retrieved from URL")

                if info.get("_type") == "playlist":
                    raise ValueError(
                        "URL points to a playlist, not a single video. Please provide a direct video URL."
                    )

                logger.info(
                    f"Video info extracted: {info.get('title', 'Unknown title')}"
                )
            except Exception as e:
                logger.warning(f"Could not extract video info without download: {e}")

            # Now download the video
            info = ydl.extract_info(url, download=True)

            if not info:
                raise ValueError("No video information retrieved from URL")

            if info.get("_type") == "playlist":
                raise ValueError(
                    "URL points to a playlist, not a single video. Please provide a direct video URL."
                )

            video_id = info.get("id")
            if not video_id:
                raise ValueError("Could not extract video ID from URL")

            ext = info.get("ext", "mp4")
            video_path = output_path / f"{video_id}.{ext}"

            if not video_path.exists():
                video_files = (
                    list(output_path.glob("*.mp4"))
                    + list(output_path.glob("*.webm"))
                    + list(output_path.glob("*.mkv"))
                )
                if video_files:
                    video_path = video_files[0]
                    logger.info(f"Found downloaded video: {video_path}")
                else:
                    raise FileNotFoundError(f"Downloaded file not found: {video_path}")

            if video_path.stat().st_size < 1024:  # Less than 1KB
                raise ValueError(
                    f"Downloaded file is too small ({video_path.stat().st_size} bytes), likely not a valid video"
                )

            logger.info(
                f"Video downloaded successfully: {video_path} ({video_path.stat().st_size / (1024 * 1024):.2f} MB)"
            )
            return video_path

    try:
        return _download_with_opts(ydl_opts)

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"yt-dlp download error: {error_msg}")

        # Fallback: retry without cookies using android/tv_embedded clients
        fallback_opts = dict(ydl_opts)
        fallback_opts.pop("cookiefile", None)
        fallback_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android", "tv_embedded"],
                "player_skip": ["webpage", "configs"],
            }
        }
        try:
            logger.info(
                "Retrying download without cookies using android/tv_embedded clients"
            )
            return _download_with_opts(fallback_opts)
        except yt_dlp.utils.DownloadError as e2:
            error_msg = str(e2)
            logger.error(f"yt-dlp fallback download error: {error_msg}")

            if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
                raise Exception(
                    f"YouTube bot detection triggered. Please:\n"
                    f"1. Export cookies from your browser using a browser extension\n"
                    f"2. Save cookies as 'youtube_cookies.txt' in the project root\n"
                    f"3. Or install 'yt-dlp[default]' for better browser integration\n"
                    f"Original error: {error_msg}"
                )
            raise Exception(f"Video download failed: {error_msg}")
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
