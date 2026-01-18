#!/usr/bin/env python3
"""
AI Video Quiz Generator - Example Client

This script demonstrates the complete workflow for processing a video
and retrieving quiz questions.

Usage:
    python example_client.py path/to/video.mp4
    python example_client.py --url https://www.youtube.com/watch?v=...
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import requests


class VideoQuizClient:
    """Simple client for the AI Video Quiz Generator API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def health_check(self) -> dict:
        """Check if API is available"""
        try:
            response = self.session.get(f"{self.base_url}/api/video/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API is not available: {e}")
            print("Make sure the server is running: python run.py")
            sys.exit(1)

    def upload_file(self, video_path: str) -> str:
        """Upload a video file and return task ID"""
        video_file = Path(video_path)

        if not video_file.exists():
            print(f"❌ File not found: {video_path}")
            sys.exit(1)

        print(f"📤 Uploading video: {video_file.name}")
        print(f"   Size: {video_file.stat().st_size / 1024 / 1024:.2f} MB")

        try:
            with open(video_file, "rb") as f:
                response = self.session.post(
                    f"{self.base_url}/api/video/upload/file",
                    files={"file": (video_file.name, f, "video/mp4")},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                return data["task_id"]

        except requests.exceptions.RequestException as e:
            print(f"❌ Upload failed: {e}")
            sys.exit(1)

    def upload_url(self, url: str) -> str:
        """Submit a video URL and return task ID"""
        print(f"📤 Submitting URL: {url}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/video/upload/url",
                json={"url": url},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["task_id"]

        except requests.exceptions.RequestException as e:
            print(f"❌ URL submission failed: {e}")
            sys.exit(1)

    def get_status(self, task_id: str) -> dict:
        """Get current task status"""
        response = self.session.get(
            f"{self.base_url}/api/video/{task_id}/status", timeout=10
        )
        response.raise_for_status()
        return response.json()

    def get_segments(self, task_id: str) -> dict:
        """Get processed segments with quizzes"""
        response = self.session.get(
            f"{self.base_url}/api/video/{task_id}/segments", timeout=10
        )
        response.raise_for_status()
        return response.json()

    def wait_for_completion(self, task_id: str, poll_interval: int = 5) -> dict:
        """Wait for processing to complete and return results"""
        print(f"\n🔄 Processing video (Task ID: {task_id})")
        print("=" * 70)

        start_time = time.time()
        last_stage = None

        while True:
            try:
                status = self.get_status(task_id)

                current_status = status["status"]
                progress = status["progress"]
                stage = status.get("current_stage", "")

                # Show stage change
                if stage != last_stage and stage:
                    print(f"\n📍 Stage: {stage}")
                    last_stage = stage

                # Progress bar
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(
                    f"\r[{bar}] {progress:.1f}% - {current_status}", end="", flush=True
                )

                if current_status == "completed":
                    elapsed = time.time() - start_time
                    print(f"\n\n✅ Processing completed in {elapsed:.1f} seconds!")
                    return self.get_segments(task_id)

                elif current_status == "failed":
                    error = status.get("error", "Unknown error")
                    print(f"\n\n❌ Processing failed: {error}")
                    sys.exit(1)

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                print(f"Task ID: {task_id}")
                print(f"Check status: curl {self.base_url}/api/video/{task_id}/status")
                sys.exit(0)

            except requests.exceptions.RequestException as e:
                print(f"\n\n❌ Status check failed: {e}")
                sys.exit(1)

    def display_results(self, segments_data: dict):
        """Display the generated quizzes in a readable format"""
        print("\n" + "=" * 70)
        print("📊 RESULTS")
        print("=" * 70)

        segments = segments_data.get("segments", [])
        total_duration = segments_data.get("total_duration", 0)

        print(
            f"\n📹 Video Duration: {total_duration:.1f} seconds ({total_duration / 60:.1f} minutes)"
        )
        print(f"📚 Segments Generated: {len(segments)}")
        print(f"❓ Total Quizzes: {sum(len(seg['quizzes']) for seg in segments)}")

        for i, segment in enumerate(segments, 1):
            print(f"\n{'=' * 70}")
            print(f"📌 SEGMENT {i}: {segment['topic_title']}")
            print(f"{'=' * 70}")
            print(f"⏱️  Time: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s")
            print(f"📝 Summary: {segment['short_summary']}")

            if segment.get("keywords"):
                print(f"🏷️  Keywords: {', '.join(segment['keywords'][:5])}")

            print(f"\n🎯 Quizzes ({len(segment['quizzes'])}):")

            for j, quiz in enumerate(segment["quizzes"], 1):
                print(f"\n  Question {j}: {quiz['question']}")
                print(f"  Options:")

                for k, option in enumerate(quiz["options"]):
                    prefix = "    ✓" if k == quiz["correct_index"] else "    ○"
                    print(f"{prefix} {chr(65 + k)}. {option}")

                if quiz.get("explanation"):
                    print(f"  💡 Explanation: {quiz['explanation']}")

        print("\n" + "=" * 70)
        print("✨ Processing Complete!")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="AI Video Quiz Generator - Example Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python example_client.py video.mp4
  python example_client.py --url https://www.youtube.com/watch?v=dQw4w9WgXcQ
  python example_client.py --url https://www.youtube.com/watch?v=dQw4w9WgXcQ --base-url http://localhost:8000
        """,
    )

    parser.add_argument(
        "video_path",
        nargs="?",
        help="Path to video file",
    )

    parser.add_argument(
        "--url",
        help="YouTube or video URL",
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Status poll interval in seconds (default: 5)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.video_path and not args.url:
        parser.print_help()
        print("\n❌ Error: Provide either a video file path or --url")
        sys.exit(1)

    if args.video_path and args.url:
        print("⚠️  Warning: Both file and URL provided, using URL")

    # Create client
    print("🚀 AI Video Quiz Generator - Example Client")
    print("=" * 70)

    client = VideoQuizClient(base_url=args.base_url)

    # Check API health
    print(f"🔍 Checking API at {args.base_url}...")
    health = client.health_check()
    print(f"✅ API is available")
    print(f"   CUDA: {health.get('cuda_available', False)}")
    print(f"   GPUs: {health.get('cuda_device_count', 0)}")

    # Upload video
    if args.url:
        task_id = client.upload_url(args.url)
    else:
        task_id = client.upload_file(args.video_path)

    print(f"✅ Upload successful! Task ID: {task_id}")

    # Wait for completion and get results
    segments_data = client.wait_for_completion(
        task_id, poll_interval=args.poll_interval
    )

    # Display results
    client.display_results(segments_data)

    # Save to file (optional)
    output_file = f"quiz_results_{task_id[:8]}.json"
    import json

    with open(output_file, "w") as f:
        json.dump(segments_data, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")
    print(f"\n🎓 You can now integrate these quizzes into your application!")


if __name__ == "__main__":
    main()
