#!/usr/bin/env python3
"""
AI Video Quiz Generator - Setup Test Script

This script tests that all dependencies are properly installed and configured.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all required packages can be imported"""
    print("Testing package imports...")

    try:
        import torch

        print(f"  ✓ PyTorch {torch.__version__}")
    except ImportError as e:
        print(f"  ✗ PyTorch import failed: {e}")
        return False

    try:
        import transformers

        print(f"  ✓ Transformers {transformers.__version__}")
    except ImportError as e:
        print(f"  ✗ Transformers import failed: {e}")
        return False

    try:
        import faster_whisper

        print(f"  ✓ Faster-Whisper")
    except ImportError as e:
        print(f"  ✗ Faster-Whisper import failed: {e}")
        return False

    try:
        import av

        print(f"  ✓ PyAV {av.__version__}")
    except ImportError as e:
        print(f"  ✗ PyAV import failed: {e}")
        return False

    try:
        import yt_dlp

        print(f"  ✓ yt-dlp {yt_dlp.version.__version__}")
    except ImportError as e:
        print(f"  ✗ yt-dlp import failed: {e}")
        return False

    try:
        import fastapi

        print(f"  ✓ FastAPI {fastapi.__version__}")
    except ImportError as e:
        print(f"  ✗ FastAPI import failed: {e}")
        return False

    try:
        import uvicorn

        print(f"  ✓ Uvicorn")
    except ImportError as e:
        print(f"  ✗ Uvicorn import failed: {e}")
        return False

    print("All packages imported successfully!\n")
    return True


def test_cuda():
    """Test CUDA availability"""
    print("Testing CUDA...")

    try:
        import torch

        if torch.cuda.is_available():
            print(f"  ✓ CUDA is available")
            print(f"  ✓ Device count: {torch.cuda.device_count()}")
            print(f"  ✓ Current device: {torch.cuda.current_device()}")
            print(f"  ✓ Device name: {torch.cuda.get_device_name(0)}")

            # Get memory info
            props = torch.cuda.get_device_properties(0)
            total_memory_gb = props.total_memory / 1e9
            print(f"  ✓ Total memory: {total_memory_gb:.2f} GB")

            if total_memory_gb < 6:
                print(
                    f"  ⚠ Warning: GPU has less than 6GB VRAM. Performance may be limited."
                )

            return True
        else:
            print(f"  ✗ CUDA is not available")
            print(f"  ⚠ Models will run on CPU (very slow!)")
            return False

    except Exception as e:
        print(f"  ✗ CUDA test failed: {e}")
        return False


def test_ffmpeg():
    """Test FFmpeg availability"""
    print("\nTesting FFmpeg...")

    import subprocess

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"  ✓ FFmpeg found: {version_line}")
            return True
        else:
            print(f"  ✗ FFmpeg returned error code {result.returncode}")
            return False

    except FileNotFoundError:
        print(f"  ✗ FFmpeg not found in PATH")
        print(f"  Install with: sudo apt install ffmpeg")
        return False
    except Exception as e:
        print(f"  ✗ FFmpeg test failed: {e}")
        return False


def test_ollama():
    """Test Ollama availability"""
    print("\nTesting Ollama...")

    import requests

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get("name") for m in models]

            print(f"  ✓ Ollama is running")
            print(f"  ✓ Available models: {len(models)}")

            # Check for qwen2.5 model
            if any("qwen2.5" in name for name in model_names):
                print(f"  ✓ qwen2.5 model found")
                return True
            else:
                print(f"  ⚠ qwen2.5 model not found")
                print(f"  Run: ollama pull qwen2.5:7b-instruct-q4_K_M")
                return False

        else:
            print(f"  ✗ Ollama returned status {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"  ✗ Cannot connect to Ollama at http://localhost:11434")
        print(f"  Start Ollama with: ollama serve")
        return False
    except Exception as e:
        print(f"  ✗ Ollama test failed: {e}")
        return False


def test_app_imports():
    """Test that app modules can be imported"""
    print("\nTesting app modules...")

    try:
        from app.core.config import settings

        print(f"  ✓ Config module")
        print(f"    - Models dir: {settings.MODELS_DIR}")
        print(f"    - Max VRAM: {settings.MAX_VRAM_GB} GB")
    except Exception as e:
        print(f"  ✗ Config import failed: {e}")
        return False

    try:
        from app.schemas.models import Quiz, TaskStatus, VideoSegment

        print(f"  ✓ Schemas module")
    except Exception as e:
        print(f"  ✗ Schemas import failed: {e}")
        return False

    try:
        from app.utils.video_utils import clear_vram, get_vram_usage

        print(f"  ✓ Utils module")
    except Exception as e:
        print(f"  ✗ Utils import failed: {e}")
        return False

    try:
        from app.services.asr_service import ASRService
        from app.services.llm_service import LLMService
        from app.services.vision_service import VisionService

        print(f"  ✓ Services module")
    except Exception as e:
        print(f"  ✗ Services import failed: {e}")
        return False

    try:
        from app.api.routes import router

        print(f"  ✓ API routes module")
    except Exception as e:
        print(f"  ✗ API routes import failed: {e}")
        return False

    try:
        from app.main import app

        print(f"  ✓ Main app module")
    except Exception as e:
        print(f"  ✗ Main app import failed: {e}")
        return False

    print("All app modules imported successfully!\n")
    return True


def test_directories():
    """Test that required directories exist"""
    print("Testing directories...")

    from app.core.config import settings

    directories = [
        settings.MODELS_DIR,
        settings.UPLOAD_DIR,
        settings.TEMP_DIR,
    ]

    all_exist = True
    for directory in directories:
        if directory.exists():
            print(f"  ✓ {directory}")
        else:
            print(f"  ✗ {directory} (will be created on startup)")
            all_exist = False

    return all_exist


def test_vram_management():
    """Test VRAM management functions"""
    print("\nTesting VRAM management...")

    try:
        import torch

        from app.utils.video_utils import clear_vram, get_vram_usage

        if not torch.cuda.is_available():
            print("  ⚠ Skipping VRAM tests (CUDA not available)")
            return True

        allocated, reserved = get_vram_usage()
        print(
            f"  ✓ Current VRAM: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
        )

        clear_vram()
        print(f"  ✓ VRAM cleared")

        allocated, reserved = get_vram_usage()
        print(
            f"  ✓ After clear: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
        )

        return True

    except Exception as e:
        print(f"  ✗ VRAM test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("AI Video Quiz Generator - Setup Test")
    print("=" * 70)
    print()

    results = {}

    results["imports"] = test_imports()
    results["cuda"] = test_cuda()
    results["ffmpeg"] = test_ffmpeg()
    results["ollama"] = test_ollama()
    results["app_imports"] = test_app_imports()
    results["directories"] = test_directories()
    results["vram"] = test_vram_management()

    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    print()

    all_critical_passed = results["imports"] and results["app_imports"]

    if all_critical_passed:
        print("✓ All critical tests passed!")
        print()
        print("Next steps:")
        print("  1. Start the server: python run.py")
        print("  2. Open browser: http://localhost:8000/docs")
        print("  3. Test with a video file or YouTube URL")

        if not results["cuda"]:
            print()
            print("⚠ WARNING: CUDA not available. Models will run on CPU.")
            print("  This will be VERY slow. Consider using a GPU-enabled system.")

        if not results["ffmpeg"]:
            print()
            print("⚠ WARNING: FFmpeg not found.")
            print("  Install with: sudo apt install ffmpeg")

        if not results["ollama"]:
            print()
            print("⚠ WARNING: Ollama not available.")
            print("  Install: curl -fsSL https://ollama.com/install.sh | sh")
            print("  Start: ollama serve")
            print("  Pull model: ollama pull qwen2.5:7b-instruct-q4_K_M")

        return 0
    else:
        print("✗ Some critical tests failed!")
        print()
        print("Please fix the issues above before running the server.")
        print("Run: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
