# 🎓 AI Video Quiz Generator

> **Hackathon Project**: Automatic video topic segmentation with embedded AI-generated quizzes

Transform any educational video into an interactive learning experience. The system automatically analyzes video content (visual + audio), segments it by topic, and generates quizzes that pause the video until answered correctly.

---

## 🌟 Key Features

### Core Capabilities
- ✅ **Multi-Modal Analysis**: Processes both audio (speech) and visual (slides/diagrams) content
- ✅ **Automatic Segmentation**: Splits videos into logical topic-based chapters
- ✅ **AI Quiz Generation**: Creates 3-5 contextual questions per segment (multiple choice, true/false)
- ✅ **In-Video Quiz Blocking**: Pauses playback until correct answer (enforced learning)
- ✅ **Universal Compatibility**: Works with uploaded files AND online videos (YouTube, Coursera, etc.)

### Technical Highlights
- 🧠 **Open-Source AI Stack**: Whisper (ASR) + Qwen2-VL (Vision) + Qwen2.5 (Reasoning)
- 🎯 **8GB VRAM Optimized**: Sequential model loading for consumer GPUs
- 🌐 **Dual Interface**: Web app for file uploads + Browser extension for YouTube integration
- 🚀 **Production-Ready**: FastAPI backend with async processing + Docker support

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Video Input Handler                                 │  │
│  │  ├─ File Upload (Web)                                │  │
│  │  └─ URL Download (yt-dlp for YouTube/Coursera)      │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  AI Processing Pipeline (Sequential Loading)        │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │ 1. ASR: Faster-Whisper large-v3-turbo (int8)  │ │  │
│  │  │    → Timestamped transcript                    │ │  │
│  │  │    🔹 VRAM: ~3GB                               │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  │           ▼ (unload model, clear VRAM)              │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │ 2. Vision: Qwen2-VL-2B-Instruct (4bit)        │ │  │
│  │  │    → Slide analysis (titles, diagrams)        │ │  │
│  │  │    🔹 VRAM: ~2.5GB                            │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  │           ▼ (unload model, clear VRAM)              │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │ 3. Reasoning: Qwen2.5-7B-Instruct (Q4)        │ │  │
│  │  │    → Topic segmentation + Quiz generation     │ │  │
│  │  │    🔹 VRAM: ~5GB                              │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Results Storage (JSON)                              │  │
│  │  {segments: [{start, end, topic, quizzes}]}         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌──────────────────────┐       ┌──────────────────────┐
│   WEB FRONTEND       │       │ BROWSER EXTENSION    │
│   (React/HTML)       │       │ (Chrome/Firefox)     │
│                      │       │                      │
│ -  Upload videos      │       │ -  YouTube integration│
│ -  View segments      │       │ -  In-video overlays  │
│ -  Demo player        │       │ -  Playback blocking  │
└──────────────────────┘       └──────────────────────┘
```

---

## 🛠 Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **AI Models**:
  - `faster-whisper` (Systran) — Speech-to-Text
  - `Qwen2-VL-2B-Instruct` (Alibaba) — Visual Language Model
  - `Qwen2.5-7B-Instruct` (Alibaba) — Large Language Model
- **Video Processing**: `ffmpeg`, `yt-dlp`
- **Deployment**: Docker + Docker Compose

### Frontend
- **Web App**: React + Vite + Tailwind CSS
- **Extension**: Vanilla JS (Manifest V3)

### Infrastructure
- **GPU**: NVIDIA (CUDA 12.1+, 8GB VRAM minimum)
- **Storage**: Local filesystem (uploads + results as JSON)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- NVIDIA GPU with CUDA 12.1+ (8GB+ VRAM)
- ffmpeg installed
- [Ollama](https://ollama.com/) (for Qwen2.5 model)

### 1. Clone & Setup Environment

```bash
# Clone repository
git clone https://github.com/yourusername/video-quiz-ai.git
cd video-quiz-ai

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Download AI Models

```bash
# Install Ollama and pull LLM model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b-instruct-q4_K_M

# Download Qwen2-VL model (auto-downloads on first run, or pre-download):
huggingface-cli download Qwen/Qwen2-VL-2B-Instruct --local-dir ./models/qwen2-vl-2b

# Faster-Whisper downloads automatically on first use
```

### 3. Run Backend

```bash
# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at http://16.171.11.38:
35
# API docs: http://16.171.11.38:2135/docs
```

### 4. Test API

```bash
# Upload a video
curl -X POST "http://16.171.11.38:2135/api/video/upload/file" \
  -F "file=@test_video.mp4"

# Response: {"task_id": "uuid-here", "status": "processing"}

# Check status
curl "http://16.171.11.38:2135/api/video/{task_id}/status"

# Get results
curl "http://16.171.11.38:2135/api/video/{task_id}/segments"
```

---

## 📁 Project Structure

```
video-quiz-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # Settings & configuration
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Main AI processing logic
│   │   ├── asr_service.py         # Whisper transcription
│   │   ├── vision_service.py      # Qwen2-VL visual analysis
│   │   └── llm_service.py         # Qwen2.5 segmentation + quiz gen
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── models.py              # Pydantic data models
│   └── utils/
│       ├── __init__.py
│       ├── video_utils.py         # ffmpeg helpers, yt-dlp
│       └── memory_utils.py        # VRAM management utilities
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── extension/
│   ├── manifest.json              # Chrome Extension config
│   ├── background.js              # Service worker
│   ├── content.js                 # Inject into video pages
│   ├── popup.html                 # Extension UI
│   └── overlay/
│       ├── quiz-overlay.html      # Quiz UI template
│       └── quiz-overlay.css
├── models/                        # Downloaded AI models cache
├── uploads/                       # Temporary video storage
├── results/                       # Processed segments (JSON)
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
└── PROMPT.md                      # AI agent instructions
```

---

## 🔌 API Documentation

### Endpoints

#### `POST /api/video/upload/file`
Upload a video file for processing.

**Request:**
```bash
Content-Type: multipart/form-data
Body: file (video file)
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Video uploaded successfully"
}
```

---

#### `POST /api/video/upload/url`
Process a video from URL (YouTube, Coursera, etc.).

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "downloading"
}
```

---

#### `GET /api/video/{task_id}/status`
Check processing progress.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "current_stage": "analyzing_visuals"
}
```

**Stages:**
- `downloading` → `transcribing` → `analyzing_visuals` → `generating_quizzes` → `completed`

---

#### `GET /api/video/{task_id}/segments`
Get final segmented results with quizzes.

**Response:**
```json
[
  {
    "start_time": "00:00:00",
    "end_time": "00:05:30",
    "topic_title": "Introduction to Neural Networks",
    "short_summary": "Overview of perceptrons, activation functions, and basic architecture.",
    "keywords": ["perceptron", "activation", "weights", "bias"],
    "quizzes": [
      {
        "question": "What is the main function of an activation function?",
        "options": [
          "Introduce non-linearity",
          "Store weights",
          "Calculate gradients",
          "Initialize parameters"
        ],
        "correct_index": 0,
        "type": "multiple_choice"
      },
      {
        "question": "A perceptron can solve XOR problem without hidden layers.",
        "options": ["True", "False"],
        "correct_index": 1,
        "type": "true_false"
      }
    ]
  },
  {
    "start_time": "00:05:30",
    "end_time": "00:12:15",
    "topic_title": "Backpropagation Algorithm",
    "short_summary": "Step-by-step explanation of gradient descent and chain rule.",
    "keywords": ["backpropagation", "gradient", "chain rule", "optimization"],
    "quizzes": [...]
  }
]
```

---

## 🎮 Usage Examples

### Scenario 1: Web App (File Upload)

1. Open http://16.171.11.38:2135 (or your deployed URL)
2. Drag & drop a lecture video (`.mp4`, `.mov`, `.avi`)
3. Wait for processing (progress bar shows current stage)
4. View results: timeline with segments, clickable to see quizzes
5. Play video in embedded player with quiz overlays

### Scenario 2: Browser Extension (YouTube)

1. Install extension from Chrome Web Store (or load unpacked)
2. Navigate to a YouTube educational video
3. Click extension icon → "Analyze This Video"
4. Extension sends URL to backend
5. After processing, quizzes automatically appear during playback
6. Video pauses at end of each segment until quiz is answered correctly

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/
```

### Test with Sample Video
```bash
# Download a test lecture
yt-dlp -f "best[height<=720]" -o test_video.mp4 "https://www.youtube.com/watch?v=aircAruvnKk"

# Process it
curl -X POST "http://16.171.11.38:2135/api/video/upload/file" \
  -F "file=@test_video.mp4"
```

---

## 🐳 Docker Deployment

### Build and Run

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

### Environment Variables

Create `.env` file:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Model Settings
WHISPER_MODEL=large-v3-turbo
WHISPER_DEVICE=cuda
QWEN_VL_MODEL=Qwen/Qwen2-VL-2B-Instruct
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M

# Limits
MAX_VIDEO_SIZE=524288000  # 500MB
MAX_VIDEO_DURATION=3600   # 1 hour

# Storage
UPLOAD_DIR=/app/uploads
RESULTS_DIR=/app/results
```

---

## 🔧 Configuration

### VRAM Optimization

**For 8GB VRAM (default):**
```python
# app/core/config.py
WHISPER_COMPUTE_TYPE = "int8"       # ~3GB
QWEN_VL_QUANTIZATION = "4bit"       # ~2.5GB
OLLAMA_MODEL = "q4_K_M"             # ~5GB (loaded last)
```

**For 16GB+ VRAM (better quality):**
```python
WHISPER_COMPUTE_TYPE = "float16"    # ~6GB
QWEN_VL_QUANTIZATION = "8bit"       # ~4GB
OLLAMA_MODEL = "q8_0"               # ~7GB
```

### Video Processing Settings

```python
# app/core/config.py
FRAME_SAMPLE_RATE = 45              # Extract 1 frame every 45 seconds
QUIZ_COUNT_PER_SEGMENT = 4          # Number of questions per segment
MIN_SEGMENT_DURATION = 120          # Minimum 2 minutes per segment
MAX_SEGMENT_DURATION = 600          # Maximum 10 minutes per segment
```

---

## 📊 Performance Benchmarks

| Video Length | Processing Time (8GB VRAM) | Processing Time (24GB VRAM) |
|--------------|----------------------------|------------------------------|
| 10 minutes   | ~4-6 minutes               | ~2-3 minutes                 |
| 30 minutes   | ~12-18 minutes             | ~6-9 minutes                 |
| 60 minutes   | ~25-35 minutes             | ~12-18 minutes               |

**Hardware Tested:**
- 8GB: RTX 3070 Laptop, RTX 4060 Ti
- 24GB: RTX 3090, RTX 4090, A10G (AWS g5.xlarge)

---

## 🐛 Troubleshooting

### CUDA Out of Memory
```bash
# Reduce batch sizes in services/
# Or switch to CPU for Whisper:
WHISPER_DEVICE=cpu
```

### yt-dlp Download Fails
```bash
# Update yt-dlp
pip install --upgrade yt-dlp

# Or use specific format
yt-dlp -f "best[height<=720]" <url>
```

### Ollama Connection Error
```bash
# Start Ollama service
ollama serve

# Verify model is loaded
ollama list
```

---

## 🤝 Contributing

This is a hackathon project (deadline: January 27, 2026, 23:59), but contributions are welcome for post-hackathon improvements!

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run linting
black app/
flake8 app/

# Run tests
pytest tests/ -v
```

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🙏 Acknowledgments

- **Alibaba Cloud**: Qwen2-VL and Qwen2.5 models
- **Systran**: Faster-Whisper implementation
- **OpenAI**: Original Whisper model architecture
- **Hackathon Organizers**: For the challenge inspiration
