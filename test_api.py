#!/usr/bin/env python3
"""
Simple API Test Script

Tests the API with a small sample request to verify everything works.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import requests


def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check endpoint...")

    try:
        response = requests.get("http://localhost:8000/api/video/health", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print("✓ Health check passed")
            print(f"  CUDA available: {data.get('cuda_available', False)}")
            print(f"  GPU devices: {data.get('cuda_device_count', 0)}")
            print(f"  Max VRAM: {data.get('max_vram_gb', 'N/A')} GB")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to API")
        print("  Make sure the server is running: python run.py")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_file_upload(video_path: str):
    """Test file upload endpoint"""
    print(f"\nTesting file upload with: {video_path}")

    if not Path(video_path).exists():
        print(f"✗ File not found: {video_path}")
        print("  Please provide a valid video file path")
        return False

    try:
        with open(video_path, "rb") as f:
            response = requests.post(
                "http://localhost:8000/api/video/upload/file",
                files={"file": f},
                timeout=600,
            )

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✓ File uploaded successfully")
            print(f"  Task ID: {task_id}")

            # Monitor progress for a bit
            print("\n  Monitoring progress (600 seconds)...")
            for i in range(600):
                time.sleep(1)

                status_response = requests.get(
                    f"http://localhost:8000/api/video/{task_id}/status", timeout=10
                )

                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"  [{status['progress']:.0f}%] {status['status']}")

                    if status["status"] == "completed":
                        print("\n✓ Processing completed!")

                        # Get segments
                        segments_response = requests.get(
                            f"http://localhost:8000/api/video/{task_id}/segments",
                            timeout=10,
                        )

                        if segments_response.status_code == 200:
                            segments_data = segments_response.json()
                            print(
                                f"✓ Retrieved {len(segments_data['segments'])} segments"
                            )

                            for idx, seg in enumerate(segments_data["segments"], 1):
                                print(f"\n  Segment {idx}: {seg['topic_title']}")
                                print(
                                    f"    Time: {seg['start_time']:.1f}s - {seg['end_time']:.1f}s"
                                )
                                print(f"    Quizzes: {len(seg['quizzes'])}")

                        return True

                    elif status["status"] == "failed":
                        print(f"\n✗ Processing failed: {status.get('error')}")
                        return False

            print("\n⚠ Still processing (this is normal for longer videos)")
            print(
                f"  Check status with: curl http://localhost:8000/api/video/{task_id}/status"
            )
            return True

        else:
            print(f"✗ Upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_url_submission(url: str):
    """Test URL submission endpoint"""
    print(f"\nTesting URL submission: {url}")

    try:
        response = requests.post(
            "http://localhost:8000/api/video/upload/url", json={"url": url}, timeout=600
        )

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✓ URL submitted successfully")
            print(f"  Task ID: {task_id}")
            print(
                f"  Check status with: curl http://localhost:8000/api/video/{task_id}/status"
            )
            return True
        else:
            print(f"✗ URL submission failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run API tests"""
    print("=" * 70)
    print("AI Video Quiz Generator - API Test")
    print("=" * 70)
    print()

    # Test 1: Health check
    if not test_health_check():
        print("\n✗ API is not accessible. Please start the server first.")
        print("  Run: python run.py")
        return 1

    # Test 2: File upload (if file provided)
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        test_file_upload(video_path)
    else:
        print("\n⚠ Skipping file upload test (no file provided)")
        print("  Usage: python test_api.py /path/to/video.mp4")

    # Test 3: URL submission (optional)
    if len(sys.argv) > 2:
        url = sys.argv[2]
        test_url_submission(url)

    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("✓ API is running and accessible")
    print()
    print("Next steps:")
    print("  1. Test with a video file: python test_api.py video.mp4")
    print("  2. Test with YouTube URL: python test_api.py '' 'https://youtube.com/...'")
    print("  3. Open interactive docs: http://localhost:8000/docs")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
