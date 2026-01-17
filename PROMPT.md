# AI Agent Development Prompt

> **For Use With**: Cursor AI, Windsurf, ChatGPT, Claude, or any code-generation AI assistant

---

## 🎯 Project Context

You are tasked with building a **Video Topic Segmentation & AI Quiz Generator** system for an educational hackathon. The deadline is **January 27, 2026, 23:59**.

### Project Goal
Create an intelligent system that:
1. Processes educational videos (lectures, tutorials, podcasts)
2. Automatically segments them into logical topic-based chapters
3. Generates contextual quizzes for each segment
4. Embeds quizzes directly into video playback with enforcement (blocks progress until answered correctly)

### Submission Requirements
- GitHub repository with complete codebase
- REST API backend (FastAPI/Flask)
- Browser extension (Chrome/Firefox) with in-video quiz overlays
- README with setup instructions
- Demo video showing the system in action

---

## 🔒 Critical Constraints

### Hardware Limitations (MUST FOLLOW)
- **Primary Development Environment**: Laptop with 8GB VRAM (single NVIDIA GPU)
- **Production Environment**: AWS instance (g5.xlarge, 24GB VRAM) - available later in hackathon
- **VRAM Strategy**: Models MUST be loaded **sequentially** (one at a time), not concurrently
  ```python
  # CORRECT Pattern:
  model_a = load_model_a()
  result_a = model_a.process()
  del model_a
  torch.cuda.empty_cache()
  
  model_b = load_model_b()
  result_b = model_b.process()
  del model_b
  torch.cuda.empty_cache()
  
  # INCORRECT (will OOM on 8GB):
  model_a = load_model_a()  # 3GB
  model_b = load_model_b()  # 2.5GB
  model_c = load_model_c()  # 5GB  ← CRASH!
  ```

### Technology Restrictions
- ❌ **NO Paid APIs**: OpenAI, Anthropic, Google Gemini, etc. are forbidden
- ✅ **Only Open-Source Models**: Must run locally
- ✅ **Python-Only Stack**: Backend must be pure Python
- ✅ **Docker Optional**: Nice to have, but not mandatory for development

---

## 🛠 Mandated Tech Stack

### Backend Framework
- **FastAPI** (preferred) or Flask
- **Async Processing**: Use `BackgroundTasks` or Celery for long-running jobs
- **API Documentation**: Swagger/OpenAPI must be available at `/docs`

### AI Models (All Open-Source)

#### 1. Speech-to-Text (ASR)
**Model**: `faster-whisper` with `large-v3-turbo`
**Quantization**: `int8` (for 8GB VRAM) or `float16` (for 24GB+ VRAM)
**VRAM Usage**: ~3GB (int8)
**Task**: Convert audio track to timestamped transcript

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8")
segments, info = model.transcribe("video.mp4", beam_size=5)
```

#### 2. Visual Analysis (VLM)
**Model**: `Qwen/Qwen2-VL-2B-Instruct`
**Quantization**: `4bit` (bitsandbytes)
**VRAM Usage**: ~2.5GB
**Task**: Analyze video frames (slides, diagrams) to extract visual context

```python
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-2B-Instruct",
    torch_dtype=torch.float16,
    device_map="auto",
    load_in_4bit=True
)
```

#### 3. Reasoning & Generation (LLM)
**Model**: `Qwen/Qwen2.5-7B-Instruct`
**Format**: GGUF via Ollama (Q4_K_M quantization)
**VRAM Usage**: ~5GB
**Task**: Merge audio transcript + visual notes → Segment video by topic → Generate quizzes

```python
import ollama

response = ollama.generate(
    model="qwen2.5:7b-instruct-q4_K_M",
    prompt=combined_prompt
)
```

### Supporting Tools
- **Video Processing**: `ffmpeg-python` (extract frames + audio)
- **Video Downloading**: `yt-dlp` (for YouTube/Coursera URLs from browser extension)
- **Data Validation**: `pydantic` v2 with strict schemas

---

## 📐 System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                      │
│  ┌───────────────────────────────────────────────┐ │
│  │  Endpoint: POST /api/video/upload/file        │ │
│  │  Endpoint: POST /api/video/upload/url         │ │
│  └───────────────────────────────────────────────┘ │
│                      ▼                              │
│  ┌───────────────────────────────────────────────┐ │
│  │  services/pipeline.py                         │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │ Step 1: ASR (Whisper)                   │ │ │
│  │  │  ├─ Extract audio (ffmpeg)              │ │ │
│  │  │  ├─ Transcribe with timestamps          │ │ │
│  │  │  └─ UNLOAD MODEL                        │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │ Step 2: Vision (Qwen2-VL)               │ │ │
│  │  │  ├─ Extract frames (1 per 45s)          │ │ │
│  │  │  ├─ Analyze slides/diagrams             │ │ │
│  │  │  └─ UNLOAD MODEL                        │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │ Step 3: Reasoning (Qwen2.5 via Ollama) │ │ │
│  │  │  ├─ Combine transcript + visual notes   │ │ │
│  │  │  ├─ Segment by topic                    │ │ │
│  │  │  └─ Generate quizzes (JSON)             │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────┘ │
│                      ▼                              │
│  ┌───────────────────────────────────────────────┐ │
│  │  Save to: results/{task_id}.json             │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Data Flow

```
User uploads video → FastAPI receives → Generate task_id → Save to uploads/

Background Task starts:
  1. ffmpeg extracts audio → video.wav
  2. Whisper transcribes → transcript.json (with timestamps)
  3. ffmpeg extracts frames → frame_0000.jpg, frame_0045.jpg, ...
  4. Qwen2-VL analyzes frames → visual_notes.json
  5. Qwen2.5 processes:
     Input: transcript + visual_notes
     Output: segments.json [
       {
         start_time, end_time, topic_title, summary, keywords,
         quizzes: [
           {question, options, correct_index, type}
         ]
       }
     ]
  6. Save to results/{task_id}.json

Frontend/Extension polls: GET /api/video/{task_id}/status
When completed: GET /api/video/{task_id}/segments
```

---

## 📋 Implementation Checklist

### Phase 1: Backend Core (Days 1-2)

#### File Structure Setup
```
app/
├── main.py
├── api/
│   └── routes.py
├── core/
│   └── config.py
├── services/
│   ├── pipeline.py
│   ├── asr_service.py
│   ├── vision_service.py
│   └── llm_service.py
├── schemas/
│   └── models.py
└── utils/
    ├── video_utils.py
    └── memory_utils.py
```

#### Tasks
- [ ] Create FastAPI app with CORS middleware
- [ ] Implement file upload endpoint with size validation (max 500MB)
- [ ] Implement URL upload endpoint using `yt-dlp`
- [ ] Create background task for processing
- [ ] Implement status tracking (in-memory dict or SQLite)
- [ ] Create Pydantic schemas for API responses

#### Key Code Patterns

**Memory Management Utility** (`utils/memory_utils.py`):
```python
import torch
import gc

def clear_vram():
    """Aggressively free VRAM between model loadings"""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()

def unload_model(model):
    """Safely unload model from memory"""
    del model
    clear_vram()
```

**Config with Environment Variables** (`core/config.py`):
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Paths
    UPLOAD_DIR: str = "uploads"
    RESULTS_DIR: str = "results"
    MODELS_DIR: str = "models"
    
    # Model Settings
    WHISPER_MODEL: str = "large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "int8"  # "float16" for 24GB VRAM
    
    QWEN_VL_MODEL: str = "Qwen/Qwen2-VL-2B-Instruct"
    QWEN_VL_QUANTIZATION: str = "4bit"
    
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"
    OLLAMA_API: str = "http://localhost:11434"
    
    # Video Processing
    FRAME_SAMPLE_RATE: int = 45  # seconds
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024
    MAX_VIDEO_DURATION: int = 3600  # 1 hour
    
    # Quiz Generation
    QUIZ_COUNT_PER_SEGMENT: int = 4
    MIN_SEGMENT_DURATION: int = 120  # 2 minutes
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Phase 2: AI Pipeline (Days 2-3)

#### ASR Service (`services/asr_service.py`)
```python
from faster_whisper import WhisperModel
from app.core.config import settings
from app.utils.memory_utils import unload_model
import logging

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self):
        self.model = None
    
    def transcribe(self, audio_path: str) -> list[dict]:
        """
        Transcribe audio to text with timestamps
        
        Returns:
            [{"start": 0.0, "end": 5.3, "text": "Hello world"}, ...]
        """
        try:
            # Load model only when needed
            logger.info("Loading Whisper model...")
            self.model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE
            )
            
            logger.info("Starting transcription...")
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                word_timestamps=True
            )
            
            # Convert to list
            transcript = []
            for segment in segments:
                transcript.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
            
            logger.info(f"Transcription complete: {len(transcript)} segments")
            return transcript
            
        finally:
            # CRITICAL: Always unload model
            if self.model:
                unload_model(self.model)
                self.model = None
                logger.info("Whisper model unloaded")
```

#### Vision Service (`services/vision_service.py`)
```python
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch
from app.core.config import settings
from app.utils.memory_utils import unload_model
import logging

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.model = None
        self.processor = None
    
    def analyze_frames(self, frame_paths: list[str]) -> list[dict]:
        """
        Analyze video frames for visual content
        
        Args:
            frame_paths: List of image file paths
            
        Returns:
            [{"time": 45, "description": "Slide shows neural network diagram"}, ...]
        """
        try:
            logger.info("Loading Qwen2-VL model...")
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                settings.QWEN_VL_MODEL,
                torch_dtype=torch.float16,
                device_map="auto",
                load_in_4bit=(settings.QWEN_VL_QUANTIZATION == "4bit")
            )
            self.processor = AutoProcessor.from_pretrained(settings.QWEN_VL_MODEL)
            
            visual_notes = []
            for i, frame_path in enumerate(frame_paths):
                time_sec = i * settings.FRAME_SAMPLE_RATE
                
                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "image", "image": frame_path},
                        {"type": "text", "text": "Describe any slides, diagrams, or text visible. Focus on educational content."}
                    ]
                }]
                
                text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = self.processor(
                    text=[text],
                    images=[frame_path],
                    return_tensors="pt"
                ).to("cuda")
                
                output_ids = self.model.generate(**inputs, max_new_tokens=256)
                description = self.processor.batch_decode(
                    output_ids,
                    skip_special_tokens=True
                )
                
                visual_notes.append({
                    "time": time_sec,
                    "description": description
                })
                
                logger.info(f"Analyzed frame {i+1}/{len(frame_paths)}")
            
            return visual_notes
            
        finally:
            if self.model:
                unload_model(self.model)
                self.model = None
            if self.processor:
                del self.processor
                self.processor = None
            logger.info("Qwen2-VL model unloaded")
```

#### LLM Service (`services/llm_service.py`)
```python
import ollama
import json
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def segment_and_generate_quizzes(
        self,
        transcript: list[dict],
        visual_notes: list[dict]
    ) -> list[dict]:
        """
        Combine audio + visual data to create topic segments with quizzes
        
        Returns:
            [
              {
                "start_time": "00:00:00",
                "end_time": "00:05:30",
                "topic_title": "...",
                "short_summary": "...",
                "keywords": [...],
                "quizzes": [...]
              }
            ]
        """
        logger.info("Generating segments and quizzes with LLM...")
        
        # Format input data
        transcript_text = "\n".join([
            f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}"
            for seg in transcript
        ])
        
        visual_text = "\n".join([
            f"[{note['time']}s] Visual: {note['description']}"
            for note in visual_notes
        ])
        
        prompt = f"""You are an educational AI assistant. Analyze the following lecture content and segment it into logical topics.

TRANSCRIPT:
{transcript_text}

VISUAL NOTES:
{visual_text}

TASK:
1. Divide the lecture into 3-7 topic-based segments
2. Each segment should be 2-10 minutes long
3. For each segment, generate:
   - Topic title (concise, max 60 chars)
   - Short summary (2-3 sentences)
   - 3-5 keywords
   - {settings.QUIZ_COUNT_PER_SEGMENT} quiz questions (mix of multiple choice and true/false)

OUTPUT FORMAT (valid JSON):
[
  {{
    "start_time": "HH:MM:SS",
    "end_time": "HH:MM:SS",
    "topic_title": "string",
    "short_summary": "string",
    "keywords": ["string"],
    "quizzes": [
      {{
        "question": "string",
        "options": ["option1", "option2", "option3", "option4"],
        "correct_index": 0,
        "type": "multiple_choice"
      }},
      {{
        "question": "string",
        "options": ["True", "False"],
        "correct_index": 1,
        "type": "true_false"
      }}
    ]
  }}
]

Generate ONLY valid JSON, no additional text."""

        try:
            response = ollama.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                options={
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            )
            
            # Parse JSON response
            segments = json.loads(response['response'])
            logger.info(f"Generated {len(segments)} segments")
            return segments
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
```

#### Main Pipeline (`services/pipeline.py`)
```python
from app.services.asr_service import ASRService
from app.services.vision_service import VisionService
from app.services.llm_service import LLMService
from app.utils.video_utils import extract_audio, extract_frames
from app.utils.memory_utils import clear_vram
import json
import logging

logger = logging.getLogger(__name__)

async def process_video(task_id: str, video_path: str, status_tracker: dict):
    """
    Main processing pipeline - runs in background
    
    Args:
        task_id: Unique task identifier
        video_path: Path to video file
        status_tracker: Shared dict for status updates
    """
    try:
        # Update status helper
        def update_status(stage: str, progress: int):
            status_tracker[task_id] = {
                "status": "processing",
                "current_stage": stage,
                "progress": progress
            }
        
        # Step 1: Extract audio
        update_status("extracting_audio", 5)
        audio_path = extract_audio(video_path, task_id)
        
        # Step 2: Transcribe (Whisper)
        update_status("transcribing", 10)
        asr = ASRService()
        transcript = asr.transcribe(audio_path)
        clear_vram()  # Ensure clean slate
        
        # Step 3: Extract frames
        update_status("extracting_frames", 40)
        frame_paths = extract_frames(video_path, task_id)
        
        # Step 4: Analyze visuals (Qwen2-VL)
        update_status("analyzing_visuals", 50)
        vision = VisionService()
        visual_notes = vision.analyze_frames(frame_paths)
        clear_vram()
        
        # Step 5: Generate segments + quizzes (Qwen2.5)
        update_status("generating_quizzes", 80)
        llm = LLMService()
        segments = llm.segment_and_generate_quizzes(transcript, visual_notes)
        
        # Step 6: Save results
        update_status("saving_results", 95)
        result_path = f"results/{task_id}.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, indent=2, ensure_ascii=False)
        
        # Complete
        status_tracker[task_id] = {
            "status": "completed",
            "current_stage": "done",
            "progress": 100
        }
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        status_tracker[task_id] = {
            "status": "failed",
            "current_stage": "error",
            "progress": 0,
            "error": str(e)
        }
```

### Phase 3: Web Frontend (Days 4-5)

#### Technology Choice
**Option A (Recommended)**: React + Vite + Tailwind CSS
- Fast setup with `npm create vite@latest`
- Modern component architecture
- Easy styling with Tailwind

**Option B (If Time-Constrained)**: Vanilla HTML + JavaScript
- Single `index.html` file
- Fetch API for backend calls
- CSS for styling

#### Key Pages
1. **Upload Page**: Drag-and-drop or file picker
2. **Processing Page**: Real-time progress updates (polling `/status`)
3. **Results Page**: Timeline visualization + embedded video player with quiz overlays

### Phase 4: Browser Extension (Days 5-6)

#### Manifest V3 Structure
```json
{
  "manifest_version": 3,
  "name": "AI Video Quiz Generator",
  "version": "1.0.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["*://*.youtube.com/*", "<all_urls>"],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["*://*.youtube.com/*", "*://*"],
      "js": ["content.js"],
      "css": ["overlay.css"]
    }
  ],
  "action": {
    "default_popup": "popup.html"
  }
}
```

#### Key Features
- Detect `<video>` elements on page
- Inject "Analyze" button
- Send video URL to backend
- Overlay quiz UI at specified timestamps
- Block `video.currentTime` changes until correct answer

---

## 🎨 Code Style Guidelines

### Python
- Use type hints everywhere
- Follow PEP 8
- Add docstrings to all functions
- Use `loguru` for logging
- Handle exceptions gracefully

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Error Handling Pattern
```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail=str(e))
finally:
    cleanup_resources()
```

---

## ✅ Definition of Done

A feature/component is considered complete when:
1. Code is written and follows style guidelines
2. No errors/warnings in IDE
3. Manual testing passes (can upload video → get results)
4. Memory management is verified (VRAM doesn't exceed 8GB)
5. Code is committed to git with clear message

---

## 🚨 Common Pitfalls to Avoid

1. **Loading All Models Simultaneously**: Will crash on 8GB VRAM
2. **Forgetting to Unload Models**: Memory leaks will slow down processing
3. **Not Handling Long Videos**: Add duration limits in config
4. **Hardcoding Paths**: Use `settings` object everywhere
5. **Blocking API Endpoints**: Always use `BackgroundTasks` for processing
6. **Not Validating Uploads**: Check file type, size, duration before processing
7. **Ignoring Error Cases**: Add proper try/except blocks
8. **Spending Too Much Time on One Task**: Prioritize tasks based on importance
9. **Writing FUCKING .md files**: Don't write `CHANGELOG.md`, `FEATURE_*.md` and other `.md` files (Except `README.md`)

---

## 📝 Daily Progress Checkpoints

### End of Day 1
- [ ] FastAPI server running
- [ ] Can upload file via `/upload/file`
- [ ] File saved to `uploads/` directory
- [ ] Status endpoint returns mock data

### End of Day 2
- [ ] ASR service extracts transcript with timestamps
- [ ] Vision service analyzes at least 1 frame
- [ ] LLM service generates at least 1 segment with quiz
- [ ] Full pipeline runs end-to-end (even if slow)

### End of Day 3
- [ ] Pipeline optimized with sequential loading
- [ ] VRAM usage stays under 8GB throughout
- [ ] Results saved as clean JSON
- [ ] API returns proper segment data

### End of Day 4
- [ ] Web frontend can upload videos
- [ ] Progress bar shows real-time updates
- [ ] Results page displays segments

### End of Day 5
- [ ] Frontend has embedded video player
- [ ] Quizzes appear as overlays
- [ ] Browser extension detects YouTube videos

### End of Day 6
- [ ] Extension sends URLs to backend
- [ ] Extension injects quiz overlays
- [ ] Playback blocking logic works

### End of Day 7
- [ ] All components integrated
- [ ] Docker setup working
- [ ] README finalized
- [ ] Demo video recorded

---

## 🎬 Final Deliverable Checklist

- [ ] GitHub repository is public
- [ ] README.md has clear setup instructions
- [ ] requirements.txt is complete and accurate
- [ ] Backend API has Swagger docs at `/docs`
- [ ] Browser extension installable (packaged as .zip)
- [ ] Demo video (3-5 minutes) uploaded to YouTube
- [ ] All code is commented
- [ ] No hardcoded credentials or API keys in repo
- [ ] .gitignore excludes uploads/, results/, models/, venv/

---

## 💡 Optimization Tips (For AWS Later)

When migrating to 24GB VRAM instance:
1. Change `WHISPER_COMPUTE_TYPE` to `"float16"`
2. Change `QWEN_VL_QUANTIZATION` to `"8bit"`
3. Remove `del model` and `clear_vram()` calls
4. Load all 3 models at startup (persistent in memory)
5. Use batching for frame analysis (process multiple frames at once)
6. Consider adding Redis/PostgreSQL for task queue

**Expected Performance Gain**: 3-5x faster processing
