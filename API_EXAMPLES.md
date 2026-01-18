# 🔌 API Examples & Integration Guide

Complete examples for integrating with the AI Video Quiz Generator API.

## Table of Contents

- [Quick Start](#quick-start)
- [Python Examples](#python-examples)
- [JavaScript Examples](#javascript-examples)
- [cURL Examples](#curl-examples)
- [Browser Extension Integration](#browser-extension-integration)
- [Web App Integration](#web-app-integration)
- [Error Handling](#error-handling)
- [Rate Limiting & Best Practices](#rate-limiting--best-practices)

---

## Quick Start

### Base URL
```
http://localhost:8000
```

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information |
| `GET` | `/health` | Health check |
| `GET` | `/api/video/health` | Detailed health check |
| `POST` | `/api/video/upload/file` | Upload video file |
| `POST` | `/api/video/upload/url` | Submit YouTube URL |
| `GET` | `/api/video/{task_id}/status` | Check processing status |
| `GET` | `/api/video/{task_id}/segments` | Get quiz results |
| `DELETE` | `/api/video/{task_id}` | Delete task |

---

## Python Examples

### Example 1: Upload and Process Video File

```python
import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def upload_and_process_video(video_path: str):
    """Upload video file and wait for processing to complete"""
    
    # Upload video
    with open(video_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/api/video/upload/file",
            files={"file": f}
        )
    
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        return None
    
    data = response.json()
    task_id = data["task_id"]
    print(f"✓ Video uploaded. Task ID: {task_id}")
    
    # Poll status until complete
    while True:
        status_response = requests.get(
            f"{BASE_URL}/api/video/{task_id}/status"
        )
        status_data = status_response.json()
        
        status = status_data["status"]
        progress = status_data["progress"]
        
        print(f"Status: {status} - Progress: {progress:.1f}%")
        
        if status == "completed":
            print("✓ Processing completed!")
            break
        elif status == "failed":
            print(f"✗ Processing failed: {status_data.get('error')}")
            return None
        
        time.sleep(5)  # Wait 5 seconds before checking again
    
    # Get results
    segments_response = requests.get(
        f"{BASE_URL}/api/video/{task_id}/segments"
    )
    segments_data = segments_response.json()
    
    print(f"\n✓ Generated {len(segments_data['segments'])} segments")
    
    for i, segment in enumerate(segments_data['segments'], 1):
        print(f"\nSegment {i}: {segment['topic_title']}")
        print(f"  Time: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s")
        print(f"  Quizzes: {len(segment['quizzes'])}")
    
    return segments_data

# Usage
if __name__ == "__main__":
    result = upload_and_process_video("path/to/video.mp4")
```

### Example 2: Process YouTube Video

```python
import requests
import time

BASE_URL = "http://localhost:8000"

def process_youtube_video(youtube_url: str):
    """Process YouTube video and get quizzes"""
    
    # Submit URL
    response = requests.post(
        f"{BASE_URL}/api/video/upload/url",
        json={"url": youtube_url}
    )
    
    if response.status_code != 200:
        print(f"Failed: {response.text}")
        return None
    
    data = response.json()
    task_id = data["task_id"]
    print(f"✓ URL submitted. Task ID: {task_id}")
    
    # Monitor progress
    while True:
        status = requests.get(
            f"{BASE_URL}/api/video/{task_id}/status"
        ).json()
        
        print(f"[{status['progress']:.0f}%] {status['status']}", end='\r')
        
        if status["status"] == "completed":
            break
        elif status["status"] == "failed":
            print(f"\n✗ Failed: {status.get('error')}")
            return None
        
        time.sleep(10)
    
    # Get segments
    segments = requests.get(
        f"{BASE_URL}/api/video/{task_id}/segments"
    ).json()
    
    print(f"\n✓ Done! {len(segments['segments'])} segments generated")
    return segments

# Usage
segments = process_youtube_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

### Example 3: Async Python with aiohttp

```python
import asyncio
import aiohttp
from pathlib import Path

BASE_URL = "http://localhost:8000"

async def upload_video_async(session, video_path: str):
    """Upload video asynchronously"""
    
    data = aiohttp.FormData()
    data.add_field('file',
                   open(video_path, 'rb'),
                   filename=Path(video_path).name,
                   content_type='video/mp4')
    
    async with session.post(f"{BASE_URL}/api/video/upload/file", data=data) as resp:
        return await resp.json()

async def check_status_async(session, task_id: str):
    """Check status asynchronously"""
    async with session.get(f"{BASE_URL}/api/video/{task_id}/status") as resp:
        return await resp.json()

async def get_segments_async(session, task_id: str):
    """Get segments asynchronously"""
    async with session.get(f"{BASE_URL}/api/video/{task_id}/segments") as resp:
        return await resp.json()

async def process_video_complete(video_path: str):
    """Complete async workflow"""
    
    async with aiohttp.ClientSession() as session:
        # Upload
        result = await upload_video_async(session, video_path)
        task_id = result["task_id"]
        print(f"Task ID: {task_id}")
        
        # Poll status
        while True:
            status = await check_status_async(session, task_id)
            print(f"Progress: {status['progress']:.0f}%")
            
            if status["status"] == "completed":
                break
            elif status["status"] == "failed":
                print(f"Failed: {status.get('error')}")
                return None
            
            await asyncio.sleep(5)
        
        # Get results
        segments = await get_segments_async(session, task_id)
        return segments

# Usage
asyncio.run(process_video_complete("video.mp4"))
```

---

## JavaScript Examples

### Example 1: Browser Upload with Progress

```javascript
const BASE_URL = "http://localhost:8000";

async function uploadVideo(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${BASE_URL}/api/video/upload/file`, {
        method: 'POST',
        body: formData
    });
    
    const data = await response.json();
    return data.task_id;
}

async function pollStatus(taskId, onProgress) {
    while (true) {
        const response = await fetch(`${BASE_URL}/api/video/${taskId}/status`);
        const status = await response.json();
        
        onProgress(status);
        
        if (status.status === 'completed') {
            return true;
        } else if (status.status === 'failed') {
            throw new Error(status.error || 'Processing failed');
        }
        
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
}

async function getSegments(taskId) {
    const response = await fetch(`${BASE_URL}/api/video/${taskId}/segments`);
    return await response.json();
}

// Usage
async function processVideo(videoFile) {
    try {
        // Upload
        console.log('Uploading...');
        const taskId = await uploadVideo(videoFile);
        console.log(`Task ID: ${taskId}`);
        
        // Monitor
        await pollStatus(taskId, (status) => {
            console.log(`${status.status}: ${status.progress}%`);
            // Update UI progress bar here
        });
        
        // Get results
        const segments = await getSegments(taskId);
        console.log(`Got ${segments.segments.length} segments`);
        
        return segments;
        
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

// In HTML
document.getElementById('videoInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) {
        const segments = await processVideo(file);
        displayQuizzes(segments);
    }
});
```

### Example 2: React Hook

```javascript
import { useState, useEffect } from 'react';

const BASE_URL = "http://localhost:8000";

function useVideoProcessor() {
    const [taskId, setTaskId] = useState(null);
    const [status, setStatus] = useState(null);
    const [segments, setSegments] = useState(null);
    const [error, setError] = useState(null);
    
    const uploadVideo = async (file) => {
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`${BASE_URL}/api/video/upload/file`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            setTaskId(data.task_id);
            
        } catch (err) {
            setError(err.message);
        }
    };
    
    useEffect(() => {
        if (!taskId) return;
        
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`${BASE_URL}/api/video/${taskId}/status`);
                const statusData = await response.json();
                
                setStatus(statusData);
                
                if (statusData.status === 'completed') {
                    clearInterval(pollInterval);
                    
                    const segResponse = await fetch(`${BASE_URL}/api/video/${taskId}/segments`);
                    const segData = await segResponse.json();
                    setSegments(segData);
                    
                } else if (statusData.status === 'failed') {
                    clearInterval(pollInterval);
                    setError(statusData.error);
                }
                
            } catch (err) {
                setError(err.message);
                clearInterval(pollInterval);
            }
        }, 5000);
        
        return () => clearInterval(pollInterval);
    }, [taskId]);
    
    return { uploadVideo, status, segments, error };
}

// Usage in component
function VideoUploader() {
    const { uploadVideo, status, segments, error } = useVideoProcessor();
    
    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file) uploadVideo(file);
    };
    
    return (
        <div>
            <input type="file" accept="video/*" onChange={handleFileChange} />
            
            {status && (
                <div>
                    <p>Status: {status.status}</p>
                    <progress value={status.progress} max="100" />
                </div>
            )}
            
            {segments && (
                <div>
                    {segments.segments.map((seg, i) => (
                        <div key={i}>
                            <h3>{seg.topic_title}</h3>
                            {seg.quizzes.map((quiz, j) => (
                                <Quiz key={j} data={quiz} />
                            ))}
                        </div>
                    ))}
                </div>
            )}
            
            {error && <p style={{color: 'red'}}>{error}</p>}
        </div>
    );
}
```

---

## cURL Examples

### Upload Video File

```bash
curl -X POST "http://localhost:8000/api/video/upload/file" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/video.mp4"
```

### Submit YouTube URL

```bash
curl -X POST "http://localhost:8000/api/video/upload/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### Check Status

```bash
curl "http://localhost:8000/api/video/{task_id}/status"
```

### Get Segments

```bash
curl "http://localhost:8000/api/video/{task_id}/segments" | jq '.'
```

### Health Check

```bash
curl "http://localhost:8000/api/video/health"
```

---

## Browser Extension Integration

### Background Script (service_worker.js)

```javascript
// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'processVideo') {
        processYouTubeVideo(request.url)
            .then(segments => sendResponse({ success: true, segments }))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // Keep channel open for async response
    }
});

async function processYouTubeVideo(url) {
    const BASE_URL = "http://localhost:8000";
    
    // Submit URL
    const uploadResponse = await fetch(`${BASE_URL}/api/video/upload/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    
    const { task_id } = await uploadResponse.json();
    
    // Poll for completion
    while (true) {
        const statusResponse = await fetch(`${BASE_URL}/api/video/${task_id}/status`);
        const status = await statusResponse.json();
        
        // Update badge with progress
        chrome.action.setBadgeText({ text: `${Math.round(status.progress)}%` });
        
        if (status.status === 'completed') {
            break;
        } else if (status.status === 'failed') {
            throw new Error(status.error);
        }
        
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
    
    // Get segments
    const segmentsResponse = await fetch(`${BASE_URL}/api/video/${task_id}/segments`);
    const segments = await segmentsResponse.json();
    
    chrome.action.setBadgeText({ text: '✓' });
    return segments;
}
```

### Content Script (content.js)

```javascript
// Detect YouTube video page
if (window.location.hostname === 'www.youtube.com') {
    addQuizButton();
}

function addQuizButton() {
    const button = document.createElement('button');
    button.textContent = 'Generate Quizzes';
    button.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        padding: 10px 20px;
        background: #ff0000;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    `;
    
    button.addEventListener('click', () => {
        const videoUrl = window.location.href;
        button.textContent = 'Processing...';
        button.disabled = true;
        
        chrome.runtime.sendMessage(
            { action: 'processVideo', url: videoUrl },
            (response) => {
                if (response.success) {
                    displayQuizzes(response.segments);
                } else {
                    alert('Error: ' + response.error);
                }
                button.textContent = 'Generate Quizzes';
                button.disabled = false;
            }
        );
    });
    
    document.body.appendChild(button);
}

function displayQuizzes(segments) {
    // Create overlay with quizzes
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.9);
        z-index: 10000;
        overflow: auto;
        padding: 20px;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        max-width: 800px;
        margin: 0 auto;
        background: white;
        padding: 20px;
        border-radius: 10px;
    `;
    
    content.innerHTML = `
        <h2>Video Quizzes</h2>
        ${segments.segments.map((seg, i) => `
            <div style="margin: 20px 0; padding: 15px; border: 1px solid #ddd;">
                <h3>${seg.topic_title}</h3>
                <p><em>${seg.start_time.toFixed(1)}s - ${seg.end_time.toFixed(1)}s</em></p>
                <p>${seg.short_summary}</p>
                ${seg.quizzes.map((quiz, j) => `
                    <div style="margin: 15px 0; padding: 10px; background: #f5f5f5;">
                        <p><strong>Q${j+1}: ${quiz.question}</strong></p>
                        <ul>
                            ${quiz.options.map((opt, k) => `
                                <li style="color: ${k === quiz.correct_index ? 'green' : 'black'}">
                                    ${opt} ${k === quiz.correct_index ? '✓' : ''}
                                </li>
                            `).join('')}
                        </ul>
                        ${quiz.explanation ? `<p><em>${quiz.explanation}</em></p>` : ''}
                    </div>
                `).join('')}
            </div>
        `).join('')}
        <button onclick="this.parentElement.parentElement.remove()">Close</button>
    `;
    
    overlay.appendChild(content);
    document.body.appendChild(overlay);
}
```

---

## Error Handling

### Python Error Handling

```python
import requests
from requests.exceptions import RequestException

def safe_api_call(url, **kwargs):
    """Make API call with proper error handling"""
    try:
        response = requests.request(**kwargs, url=url, timeout=30)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        print("Request timed out")
        return None
        
    except requests.exceptions.ConnectionError:
        print("Could not connect to API")
        return None
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code}")
        print(f"Details: {e.response.text}")
        return None
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# Usage
result = safe_api_call(
    f"{BASE_URL}/api/video/upload/file",
    method='POST',
    files={'file': open('video.mp4', 'rb')}
)
```

### JavaScript Error Handling

```javascript
async function safeApiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            signal: AbortSignal.timeout(30000) // 30 second timeout
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('Request timed out');
        } else if (error.name === 'TypeError') {
            console.error('Network error');
        } else {
            console.error('API error:', error.message);
        }
        throw error;
    }
}
```

---

## Rate Limiting & Best Practices

### Best Practices

1. **Poll Interval**: Use 5-10 second intervals when checking status
2. **Timeout**: Set reasonable timeouts (30s for uploads, 10s for status checks)
3. **File Size**: Check file size before uploading (max 500MB)
4. **One at a Time**: Process one video at a time to avoid VRAM exhaustion
5. **Clean Up**: Delete completed tasks when no longer needed
6. **Cache Results**: Store segments locally to avoid re-processing

### Example with Rate Limiting

```python
import time
from functools import wraps

def rate_limit(min_interval=1.0):
    """Decorator to rate limit API calls"""
    last_call = [0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(min_interval=5.0)
def check_status(task_id):
    """Check status with rate limiting"""
    response = requests.get(f"{BASE_URL}/api/video/{task_id}/status")
    return response.json()
```

---

## Complete Integration Example

### Full-Featured Video Processor Class

```python
import requests
import time
from typing import Optional, Dict, Any, Callable

class VideoQuizAPI:
    """Complete API client for Video Quiz Generator"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = self.session.get(f"{self.base_url}/api/video/health")
        return response.json()
    
    def upload_file(self, video_path: str) -> str:
        """Upload video file and return task ID"""
        with open(video_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/video/upload/file",
                files={'file': f}
            )
        response.raise_for_status()
        return response.json()['task_id']
    
    def upload_url(self, url: str) -> str:
        """Submit URL and return task ID"""
        response = self.session.post(
            f"{self.base_url}/api/video/upload/url",
            json={'url': url}
        )
        response.raise_for_status()
        return response.json()['task_id']
    
    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status"""
        response = self.session.get(
            f"{self.base_url}/api/video/{task_id}/status"
        )
        return response.json()
    
    def get_segments(self, task_id: str) -> Dict[str, Any]:
        """Get processed segments"""
        response = self.session.get(
            f"{self.base_url}/api/video/{task_id}/segments"
        )
        return response.json()
    
    def delete_task(self, task_id: str) -> None:
        """Delete task"""
        self.session.delete(f"{self.base_url}/api/video/{task_id}")
    
    def process_and_wait(
        self,
        video_path: Optional[str] = None,
        url: Optional[str] = None,
        poll_interval: int = 5,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Process video and wait for completion
        
        Args:
            video_path: Path to video file
            url: Video URL
            poll_interval: Seconds between status checks
            progress_callback: Function called with status updates
            
        Returns:
            Segments dictionary
        """
        # Upload
        if video_path:
            task_id = self.upload_file(video_path)
        elif url:
            task_id = self.upload_url(url)
        else:
            raise ValueError("Provide either video_path or url")
        
        # Poll
        while True:
            status = self.get_status(task_id)
            
            if progress_callback:
                progress_callback(status)
            
            if status['status'] == 'completed':
                break
            elif status['status'] == 'failed':
                raise Exception(f"Processing failed: {status.get('error')}")
            
            time.sleep(poll_interval)
        
        # Get results
        return self.get_segments(task_id)

# Usage
api = VideoQuizAPI()

# Check health
print(api.health_check())

# Process video with progress
def show_progress(status):
    print(f"[{status['progress']:.0f}%] {status['status']}")

segments = api.process_and_wait(
    video_path="video.mp4",
    progress_callback=show_progress
)

print(f"Generated {len(segments['segments'])} segments!")
```

---

For more examples, see the interactive API documentation at `http://localhost:8000/docs`
