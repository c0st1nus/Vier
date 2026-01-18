# 🚀 Quick Start Guide

This guide will help you get the AI Video Quiz Generator up and running quickly.

## Prerequisites

- **Python 3.10+**
- **CUDA-capable GPU** with at least 8GB VRAM (NVIDIA GPU)
- **CUDA Toolkit 12.1** or compatible
- **FFmpeg** (for video processing)
- **Ollama** (for LLM inference)
- **~15GB disk space** for models

## Step 1: Environment Setup

```bash
# Clone the repository (if not already done)
cd /home/const/Projects/Vier

# Create virtual environment (if not already done)
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Install System Dependencies

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### Install Ollama
```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve &

# Pull the required model
ollama pull qwen2.5:7b-instruct-q4_K_M
```

### Verify FFmpeg
```bash
ffmpeg -version
```

## Step 3: Download AI Models

The models will be downloaded automatically on first use, but you can pre-download them:

```bash
# Create models directory
mkdir -p models

# Download Whisper model (will download on first transcription)
# Download Qwen2-VL model (will download on first frame analysis)
# Download Llama 3.2 model (will download on first quiz generation)
```

**Note:** 
- Whisper and Qwen2-VL models will be cached in the `models/` directory (~8GB)
- The LLM model runs via Ollama (separate service, ~5GB)

## Step 4: Configuration

Create a `.env` file (optional - defaults work fine):

```bash
cp .env.example .env
```

Edit `.env` if needed:
```bash
# Main settings to adjust
MAX_VRAM_GB=6.5          # Adjust based on your GPU
DEBUG=False              # Set to True for detailed logs
PORT=8000                # API port
```

## Step 5: Start the Server

```bash
# Simple start
python run.py

# OR using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

You should see:
```
✓ All required packages are installed
✓ CUDA available: NVIDIA GeForce RTX 3080
✓ GPU Memory: 10.00 GB
...
Starting server...
API Docs will be available at: http://0.0.0.0:8000/docs
```

## Step 6: Test the API

### Option A: Using the Interactive Docs

1. Open browser: http://localhost:8000/docs
2. Try the health check endpoint: `GET /api/video/health`
3. Upload a video using `POST /api/video/upload/file`

### Option B: Using cURL

#### Health Check
```bash
curl http://localhost:8000/api/video/health
```

#### Upload Video File
```bash
curl -X POST "http://localhost:8000/api/video/upload/file" \
  -F "file=@/path/to/your/video.mp4"
```

Response:
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Video upload successful. Processing started."
}
```

#### Check Status
```bash
curl http://localhost:8000/api/video/123e4567-e89b-12d3-a456-426614174000/status
```

Response:
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "transcribing",
  "progress": 45.0,
  "current_stage": "transcription",
  "message": "Transcribing audio..."
}
```

#### Get Results (when complete)
```bash
curl http://localhost:8000/api/video/123e4567-e89b-12d3-a456-426614174000/segments
```

### Option C: Using Python

```python
import requests

# Upload video
with open("video.mp4", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/video/upload/file",
        files={"file": f}
    )
    task_id = response.json()["task_id"]

# Check status
status = requests.get(
    f"http://localhost:8000/api/video/{task_id}/status"
).json()
print(f"Status: {status['status']} - {status['progress']}%")

# Get segments (when completed)
segments = requests.get(
    f"http://localhost:8000/api/video/{task_id}/segments"
).json()
print(f"Found {len(segments['segments'])} segments")
```

## Step 7: Process a YouTube Video

```bash
curl -X POST "http://localhost:8000/api/video/upload/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## Understanding the Processing Pipeline

1. **Upload** (5 seconds) - File is saved
2. **Download** (10-60 seconds) - For YouTube URLs
3. **Audio Extraction** (10-30 seconds) - FFmpeg extracts audio
4. **Transcription** (1-5 minutes) - Whisper transcribes speech
5. **Frame Analysis** (2-10 minutes) - Qwen2-VL analyzes key frames
6. **Quiz Generation** (1-3 minutes) - Llama generates quizzes
7. **Complete** - Results ready!

**Total Time:** ~5-20 minutes depending on video length and GPU speed

## Expected Output Format

```json
{
  "task_id": "abc-123",
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 45.5,
      "topic_title": "Introduction to Neural Networks",
      "short_summary": "Overview of neural network basics...",
      "keywords": ["neural networks", "deep learning", "neurons"],
      "quizzes": [
        {
          "question": "What is a neural network?",
          "options": [
            "A biological brain",
            "A computational model inspired by biological neurons",
            "A type of database",
            "A programming language"
          ],
          "correct_index": 1,
          "type": "multiple_choice",
          "explanation": "Neural networks are computational models..."
        }
      ]
    }
  ],
  "total_duration": 180.5,
  "video_title": "Neural Networks Explained"
}
```

## Troubleshooting

### Ollama Not Running
```bash
# Start Ollama service
ollama serve

# In another terminal, check it's working
ollama list
```

### CUDA Out of Memory
```bash
# Reduce VRAM usage in .env
MAX_VRAM_GB=5.0
FRAME_EXTRACTION_FPS=0.05  # Extract fewer frames
MAX_FRAMES_PER_VIDEO=50
```

### FFmpeg Not Found
```bash
# Install FFmpeg
sudo apt install ffmpeg  # Ubuntu/Debian
sudo pacman -S ffmpeg    # Arch Linux
brew install ffmpeg      # macOS
```

### Models Download Slowly
The first run will download models. Be patient!
```
Downloading Whisper large-v3: ~3GB
Downloading Qwen2-VL-2B: ~5GB
Ollama model (qwen2.5:7b): ~5GB (via ollama pull)
```

### Port Already in Use
```bash
# Change port in .env
PORT=8001

# Or kill the process using port 8000
lsof -ti:8000 | xargs kill -9
```

## Performance Tips

1. **Use shorter videos** for testing (1-3 minutes)
2. **Close other GPU applications** (browsers, games, etc.)
3. **Keep Ollama running** in the background
4. **Monitor VRAM usage:**
   ```bash
   watch -n 1 nvidia-smi
   ```
5. **Process one video at a time** (models require significant VRAM)

## Next Steps

- ✅ Test with a short video (1-2 minutes)
- ✅ Check the API documentation at `/docs`
- ✅ Monitor logs in `app.log`
- ✅ Try different video types (educational, tutorials, etc.)
- ✅ Build a frontend or browser extension using the API

## Project Structure Reference

```
Vier/
├── app/
│   ├── main.py              # FastAPI application
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── core/
│   │   └── config.py        # Configuration
│   ├── schemas/
│   │   └── models.py        # Pydantic models
│   ├── services/
│   │   ├── asr_service.py   # Whisper ASR
│   │   ├── vision_service.py # Qwen2-VL vision
│   │   ├── llm_service.py   # Llama LLM
│   │   └── pipeline.py      # Main pipeline
│   └── utils/
│       └── video_utils.py   # Video utilities
├── models/                  # Downloaded models (auto-created)
├── uploads/                 # Uploaded videos
├── temp/                    # Temporary processing files
├── run.py                   # Startup script
├── requirements.txt         # Python dependencies
└── .env                     # Configuration (create from .env.example)
```

## Support

- Check `app.log` for detailed error messages
- Monitor GPU usage with `nvidia-smi`
- Review API documentation at http://localhost:8000/docs

Happy generating! 🎓✨
