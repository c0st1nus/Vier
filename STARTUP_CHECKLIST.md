# 🚀 Startup Checklist

This checklist ensures all dependencies and services are properly configured before running the AI Video Quiz Generator.

## ✅ Pre-Flight Checklist

### 1. System Requirements

- [ ] Python 3.10 or higher installed
- [ ] NVIDIA GPU with 8GB+ VRAM
- [ ] CUDA 12.1+ installed
- [ ] ~15GB free disk space

### 2. Required Software

#### FFmpeg
```bash
# Check if installed
ffmpeg -version

# If not installed (Ubuntu/Debian):
sudo apt update && sudo apt install ffmpeg

# If not installed (macOS):
brew install ffmpeg
```

#### Ollama
```bash
# Check if installed
ollama --version

# If not installed:
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# Pull required model (in another terminal)
ollama pull qwen2.5:7b-instruct-q4_K_M

# Verify
ollama list
# Should show: qwen2.5:7b-instruct-q4_K_M
```

### 3. Python Environment

```bash
# Navigate to project
cd /home/const/Projects/Vier

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version
# Should be: Python 3.10.x or higher

# Install/update dependencies
pip install -r requirements.txt
```

### 4. AI Models

#### Check Models Directory
```bash
ls -la models/

# Should contain:
# - models--Systran--faster-whisper-large-v3/  (~3GB)
# - qwen2-vl-2b/                               (~5GB)
```

#### If Models Missing:
- **Whisper**: Will auto-download on first transcription
- **Qwen2-VL**: Download manually:
  ```bash
  huggingface-cli download Qwen/Qwen2-VL-2B-Instruct --local-dir models/qwen2-vl-2b
  ```
- **LLM**: Runs via Ollama (separate service)

### 5. Configuration

```bash
# Copy example config (optional)
cp .env.example .env

# Edit if needed
nano .env

# Key settings:
# - MAX_VRAM_GB=6.5
# - OLLAMA_URL=http://localhost:11434
# - OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
```

### 6. Directory Structure

```bash
# Create required directories (auto-created on startup)
mkdir -p models uploads temp

# Verify
ls -ld models uploads temp
```

## 🧪 Verification Tests

### Run Full Test Suite
```bash
python test_setup.py
```

Expected output:
```
✓ All packages imported successfully!
✓ CUDA is available
✓ FFmpeg found
✓ Ollama is running
✓ qwen2.5 model found
✓ All app modules imported successfully!
```

### Individual Checks

#### 1. CUDA Test
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
# Should print: CUDA: True
```

#### 2. Ollama Test
```bash
curl http://localhost:11434/api/tags
# Should return JSON with models list
```

#### 3. Import Test
```bash
python -c "from app.main import app; print('✓ App imports OK')"
```

## 🎬 Start the Server

### Method 1: Using Startup Script (Recommended)
```bash
python run.py
```

### Method 2: Direct Uvicorn
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Expected Startup Output
```
======================================================================
AI Video Quiz Generator - Starting Server
======================================================================
✓ All required packages are installed
✓ CUDA available: NVIDIA GeForce RTX 4060 Laptop GPU
✓ GPU Memory: 8.19 GB
✓ Directory ready: /home/const/Projects/Vier/models
✓ Directory ready: /home/const/Projects/Vier/uploads
✓ Directory ready: /home/const/Projects/Vier/temp

Configuration:
  Host: 0.0.0.0
  Port: 8000
  Debug: False
  Max VRAM: 6.5 GB
  Models Dir: /home/const/Projects/Vier/models

======================================================================
Starting server...
API Docs will be available at: http://0.0.0.0:8000/docs
======================================================================

INFO:     Started server process [14328]
INFO:     Waiting for application startup.
INFO:     CUDA available: NVIDIA GeForce RTX 4060 Laptop GPU
INFO:     CUDA memory: 8.19 GB
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## ✅ Post-Startup Verification

### 1. Health Check
```bash
curl http://localhost:8000/api/video/health
```

Expected response:
```json
{
  "status": "healthy",
  "cuda_available": true,
  "cuda_device_count": 1,
  "models_dir": "/home/const/Projects/Vier/models",
  "max_vram_gb": 6.5
}
```

### 2. API Documentation
Open in browser:
```
http://localhost:8000/docs
```

Should see interactive Swagger UI with all endpoints.

### 3. Test Upload
```bash
# With test script
python test_api.py

# Or with example client
python example_client.py path/to/test_video.mp4
```

## 🚨 Common Issues & Solutions

### Issue: "Connection refused" when starting
**Solution:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Kill existing process: `kill -9 <PID>`
- Or change port in `.env`: `PORT=8001`

### Issue: "Ollama connection failed"
**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve

# In another terminal, verify
ollama list
```

### Issue: "CUDA not available"
**Solution:**
- Verify GPU: `nvidia-smi`
- Check CUDA: `nvcc --version`
- Reinstall PyTorch with CUDA support
- Server will still work on CPU (but very slow)

### Issue: "FFmpeg not found"
**Solution:**
```bash
# Install FFmpeg
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS

# Verify
ffmpeg -version
```

### Issue: "Models not found"
**Solution:**
- Models auto-download on first use
- Whisper: ~3GB download on first transcription
- Qwen2-VL: Check `models/qwen2-vl-2b/` exists
- LLM: Ensure `ollama pull qwen2.5:7b-instruct-q4_K_M` completed

### Issue: "CUDA Out of Memory"
**Solution:**
```bash
# Reduce VRAM usage in .env
MAX_VRAM_GB=5.0
FRAME_EXTRACTION_FPS=0.05
MAX_FRAMES_PER_VIDEO=50

# Close other GPU applications
# Check GPU usage: nvidia-smi
```

## 📊 Service Status Monitor

### Real-time GPU Monitor
```bash
watch -n 1 nvidia-smi
```

### Check Ollama Status
```bash
curl http://localhost:11434/api/tags | python -m json.tool
```

### Check API Status
```bash
curl http://localhost:8000/health
```

### View Server Logs
```bash
tail -f app.log
```

## 🎯 Quick Start Commands (Copy-Paste)

```bash
# 1. Ensure Ollama is running
ollama serve &

# 2. Activate environment
cd /home/const/Projects/Vier
source .venv/bin/activate

# 3. Run tests
python test_setup.py

# 4. Start server
python run.py

# 5. In another terminal, test API
curl http://localhost:8000/api/video/health

# 6. Open browser
xdg-open http://localhost:8000/docs  # Linux
open http://localhost:8000/docs       # macOS
```

## ✨ You're Ready!

If all checks pass:
- ✅ Server is running on http://localhost:8000
- ✅ API docs available at http://localhost:8000/docs
- ✅ Ready to process videos!

### Next Steps:
1. Upload a test video via `/docs` interface
2. Monitor progress with status endpoint
3. Retrieve quiz results when complete
4. Integrate into your application

---

**For troubleshooting, check:**
- Server logs: `app.log`
- GPU status: `nvidia-smi`
- Ollama status: `ollama list`
- API health: `curl http://localhost:8000/api/video/health`
