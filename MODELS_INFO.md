# 📦 Installed Models Information

This document lists the AI models currently installed and configured for the AI Video Quiz Generator.

---

## ✅ Currently Installed Models

### 1. Whisper (ASR - Speech-to-Text)

**Model**: `mobiuslabsgmbh/faster-whisper-large-v3-turbo`
- **Location**: `models/whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/`
- **Size**: ~1.5GB (CTranslate2 optimized)
- **Purpose**: Audio transcription with timestamps
- **Features**:
  - Faster inference than standard Whisper
  - Optimized for GPU (CUDA)
  - Automatic language detection
  - Timestamp-accurate transcription
  - Voice Activity Detection (VAD)
- **Status**: ✅ **INSTALLED & READY**

**Configuration**:
```python
WHISPER_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
```

---

### 2. Qwen2-VL (Vision - Frame Analysis)

**Model**: `Qwen/Qwen2-VL-2B-Instruct`
- **Location**: `models/qwen2-vl-2b/`
- **Size**: ~5GB (2B parameters, float16)
- **Purpose**: Visual content analysis of video frames
- **Features**:
  - Frame-by-frame image understanding
  - Educational content detection
  - Text and diagram recognition
  - Key visual element extraction
  - Context-aware descriptions
- **Status**: ✅ **INSTALLED & READY**

**Configuration**:
```python
QWEN_MODEL_PATH = "/home/const/Projects/Vier/models/qwen2-vl-2b"
QWEN_MAX_PIXELS = 360 * 420  # Reduced for VRAM
QWEN_MIN_PIXELS = 224 * 224
```

**Model Files**:
- `model-00001-of-00002.safetensors` (3.7GB)
- `model-00002-of-00002.safetensors` (409MB)
- `config.json`, `tokenizer.json`, etc.

---

### 3. Qwen2.5 (LLM - Quiz Generation) via Ollama

**Model**: `qwen2.5:7b-instruct-q4_K_M`
- **Location**: Managed by Ollama (separate service)
- **Size**: ~4.7GB (7B parameters, Q4_K_M quantization)
- **Purpose**: Video segmentation and quiz question generation
- **Features**:
  - Intelligent topic segmentation
  - Context-aware question generation
  - Multiple-choice quiz creation
  - Answer explanations
  - JSON-structured output
  - Memory efficient (4-bit quantization)
- **Status**: ✅ **INSTALLED & READY** (via Ollama)

**Configuration**:
```python
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b-instruct-q4_K_M"
LLAMA_TEMPERATURE = 0.7
```

**Verification**:
```bash
ollama list
# Should show: qwen2.5:7b-instruct-q4_K_M
```

---

## 📊 Model Comparison

| Model | Type | Size | VRAM Usage | Purpose |
|-------|------|------|------------|---------|
| **Whisper Turbo** | ASR | ~1.5GB | 2-3GB | Audio → Text |
| **Qwen2-VL-2B** | Vision | ~5GB | 3-4GB | Frame Analysis |
| **Qwen2.5-7B** | LLM | ~4.7GB | Managed by Ollama | Quiz Generation |

**Total Storage**: ~11GB
**Peak VRAM**: ~4-5GB (models loaded sequentially)

---

## 🔄 Model Loading Strategy

To stay within the 8GB VRAM limit, models are loaded sequentially:

1. **Load Whisper** → Transcribe audio → **Unload**
2. **Load Qwen2-VL** → Analyze frames → **Unload**
3. **Connect to Ollama** → Generate quizzes → **Disconnect**

Each model is cleared from VRAM before loading the next one.

---

## 🚀 Model Performance

### Whisper Turbo (faster-whisper-large-v3-turbo)
- **Speed**: ~2-3x faster than standard Whisper Large-v3
- **Accuracy**: ~95% on clear audio
- **Languages**: 99 languages supported
- **Real-time Factor**: ~0.1-0.3 (processes 1 min of audio in 6-18 seconds)

### Qwen2-VL-2B
- **Speed**: ~2-5 seconds per frame
- **Context Length**: 32K tokens
- **Image Resolution**: Up to 360x420 (configurable)
- **Accuracy**: Good for educational content, diagrams, text

### Qwen2.5-7B (via Ollama)
- **Speed**: ~20-50 tokens/second
- **Context Length**: 128K tokens
- **Quantization**: Q4_K_M (good balance of speed and quality)
- **Memory**: Efficiently managed by Ollama

---

## 🔧 Using Different Models

### To Change Whisper Model

If you want to use a different Whisper model:

```bash
# Option 1: Standard large-v3 (slower but slightly more accurate)
# Download with:
# pip install faster-whisper
# The model will auto-download on first use

# Option 2: Use a smaller model (faster, less accurate)
# Edit app/core/config.py:
WHISPER_MODEL = "medium"  # or "small", "base", "tiny"
```

### To Change Vision Model

If you want to use a different vision model:

```bash
# Download alternative (not recommended due to VRAM constraints)
# Larger models require more VRAM
```

### To Change LLM Model

If you want to use a different Ollama model:

```bash
# List available models
ollama list

# Pull a different model
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull mistral:7b-instruct

# Update app/core/config.py:
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_K_M"
```

---

## ⚙️ Model Configuration Files

### Whisper
- Config: `models/whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/.../config.json`
- Model: `models/whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/.../model.bin`

### Qwen2-VL
- Config: `models/qwen2-vl-2b/config.json`
- Tokenizer: `models/qwen2-vl-2b/tokenizer.json`
- Model: `models/qwen2-vl-2b/model-*.safetensors`

### Qwen2.5 (Ollama)
- Managed internally by Ollama
- Location: `~/.ollama/models/`
- Configuration: Via Ollama API

---

## 🧪 Testing Models

### Test Whisper
```python
from app.services.asr_service import ASRService
from pathlib import Path

asr = ASRService()
asr.load_model()
segments = asr.transcribe(Path("test_audio.wav"))
print(f"Transcribed {len(segments)} segments")
```

### Test Qwen2-VL
```python
from app.services.vision_service import VisionService
from pathlib import Path

vision = VisionService()
vision.load_model()
description = vision.analyze_frame(Path("test_frame.jpg"))
print(f"Description: {description}")
```

### Test Qwen2.5 (Ollama)
```python
from app.services.llm_service import LLMService

llm = LLMService()
llm.load_model()
response = llm.generate_text("What is machine learning?")
print(f"Response: {response}")
```

---

## 📝 Model Licenses

- **Whisper**: MIT License (OpenAI)
- **Qwen2-VL**: Apache 2.0 License (Alibaba Cloud)
- **Qwen2.5**: Apache 2.0 License (Alibaba Cloud)

All models are free to use for commercial and non-commercial purposes.

---

## 🔄 Model Updates

To update models to newer versions:

### Whisper
```bash
# Models auto-update via faster-whisper
# Or manually clear cache and re-download
rm -rf models/whisper/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo
```

### Qwen2-VL
```bash
# Download new version
huggingface-cli download Qwen/Qwen2-VL-2B-Instruct --local-dir models/qwen2-vl-2b-new
# Update config.py to point to new directory
```

### Qwen2.5
```bash
# Update via Ollama
ollama pull qwen2.5:7b-instruct-q4_K_M
# Ollama automatically uses the latest version
```

---

## 💡 Optimization Tips

1. **VRAM Management**:
   - Models are loaded sequentially to stay within 8GB VRAM
   - Use FP16 precision for all models
   - Clear cache between model loads

2. **Speed Optimization**:
   - Whisper Turbo is 2-3x faster than standard
   - Reduce frame extraction rate if needed
   - Use Q4 quantization for LLM (via Ollama)

3. **Quality vs Speed**:
   - Current settings balance quality and speed
   - For higher quality: use larger models (requires more VRAM)
   - For faster processing: use smaller models or reduce resolution

---

## ✅ Verification

To verify all models are working:

```bash
python test_setup.py
```

This will check:
- ✅ Whisper model accessibility
- ✅ Qwen2-VL model loading
- ✅ Ollama connectivity and model availability

---

**Last Updated**: 2024-01-18
**Configuration Version**: 1.0
**Status**: All models operational ✅