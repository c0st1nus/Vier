import json
import logging
from pathlib import Path
from typing import List, Optional

import requests

from app.core.config import settings
from app.schemas.models import (
    FrameAnalysis,
    Quiz,
    QuizType,
    TranscriptionSegment,
    VideoSegment,
)

logger = logging.getLogger(__name__)


class LLMService:
    """LLM service using Ollama for quiz generation and content segmentation"""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.model_name = settings.OLLAMA_MODEL
        self.model_loaded = False

    def load_model(self):
        """Check Ollama availability"""
        if self.model_loaded:
            logger.info("Ollama already connected")
            return

        try:
            logger.info(f"Connecting to Ollama at {self.ollama_url}")

            # Check if Ollama is running
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]
                logger.info(f"Available models: {model_names}")

                if self.model_name in model_names or any(
                    self.model_name in m for m in model_names
                ):
                    logger.info(
                        f"Ollama connected successfully with model: {self.model_name}"
                    )
                    self.model_loaded = True
                else:
                    logger.warning(
                        f"Model {self.model_name} not found, will try to use it anyway"
                    )
                    self.model_loaded = True
            else:
                raise Exception(f"Ollama returned status {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            logger.error("Make sure Ollama is running: ollama serve")
            self.model_loaded = False
            raise Exception(f"Ollama connection failed: {str(e)}")

    def unload_model(self):
        """Unload model (no-op for Ollama)"""
        logger.info("Ollama connection closed (model stays in Ollama)")
        self.model_loaded = False

    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        """
        Generate text from prompt using Ollama

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        if not self.model_loaded:
            self.load_model()

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": settings.LLAMA_TEMPERATURE,
                        "num_predict": max_tokens,
                    },
                },
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(
                    f"Ollama returned status {response.status_code}: {response.text}"
                )
                return ""

        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return ""

    def segment_transcript(
        self,
        transcription: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
    ) -> List[dict]:
        """
        Segment video content into logical topics

        Args:
            transcription: List of transcription segments
            frame_analyses: List of frame analyses
            video_duration: Total video duration

        Returns:
            List of segment definitions with start/end times and topics
        """
        if not self.model_loaded:
            self.load_model()

        logger.info("Segmenting video content into topics")

        try:
            # Prepare context from transcription and frames
            transcript_text = " ".join([seg.text for seg in transcription])

            # Get frame descriptions at key timestamps
            frame_context = "\n".join(
                [
                    f"At {fa.timestamp:.1f}s: {fa.description[:100]}"
                    for fa in frame_analyses[:10]
                ]
            )

            # Create segmentation prompt
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert at analyzing educational video content. Your task is to segment the video into logical topics or chapters based on the transcript and visual information.<|eot_id|><|start_header_id|>user<|end_header_id|>

Video Duration: {video_duration:.1f} seconds

Transcript:
{transcript_text[:2000]}

Visual Information:
{frame_context}

Task: Divide this video into 3-6 logical segments based on topic changes. For each segment, provide:
1. Start time (in seconds)
2. End time (in seconds)
3. Topic title (short, descriptive)
4. Brief summary (1-2 sentences)

Format your response as JSON array:
[
  {{"start_time": 0, "end_time": 45.5, "topic": "Introduction to Topic", "summary": "Brief description"}},
  ...
]

Response:"""

            # Generate segmentation
            response = self.generate_text(prompt, max_tokens=1024)

            # Parse JSON response
            segments = self._parse_json_response(response)

            if not segments:
                # Fallback: create simple time-based segments
                logger.warning("Could not parse LLM segmentation, using fallback")
                segments = self._create_fallback_segments(video_duration, transcription)

            logger.info(f"Created {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            # Return fallback segments
            return self._create_fallback_segments(video_duration, transcription)

    def generate_quizzes(self, segment_info: dict, transcript_text: str) -> List[Quiz]:
        """
        Generate quiz questions for a video segment

        Args:
            segment_info: Segment information (topic, summary, etc.)
            transcript_text: Transcript text for this segment

        Returns:
            List of Quiz objects
        """
        if not self.model_loaded:
            self.load_model()

        logger.info(f"Generating quizzes for: {segment_info.get('topic', 'segment')}")

        try:
            # Create quiz generation prompt
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert educator creating quiz questions for educational video content. Create clear, accurate questions that test understanding of the key concepts.<|eot_id|><|start_header_id|>user<|end_header_id|>

Topic: {segment_info.get("topic", "Video Content")}
Summary: {segment_info.get("summary", "")}

Content:
{transcript_text[:1500]}

Task: Create {settings.QUIZZES_PER_SEGMENT} multiple-choice questions based on this content.

For each question provide:
1. A clear question
2. Exactly 4 answer options
3. The index (0-3) of the correct answer
4. Brief explanation of why it's correct

Format as JSON array:
[
  {{
    "question": "What is...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 1,
    "explanation": "Because..."
  }},
  ...
]

Response:"""

            # Generate quizzes
            response = self.generate_text(prompt, max_tokens=1024)

            # Parse JSON response
            quiz_data = self._parse_json_response(response)

            if not quiz_data:
                logger.warning("Could not parse quiz response, using fallback")
                quiz_data = self._create_fallback_quizzes(segment_info)

            # Convert to Quiz objects
            quizzes = []
            for item in quiz_data[: settings.QUIZZES_PER_SEGMENT]:
                try:
                    quiz = Quiz(
                        question=item.get("question", "Sample question?"),
                        options=item.get(
                            "options", ["Option A", "Option B", "Option C", "Option D"]
                        ),
                        correct_index=item.get("correct_index", 0),
                        type=QuizType.MULTIPLE_CHOICE,
                        explanation=item.get("explanation"),
                    )
                    quizzes.append(quiz)
                except Exception as e:
                    logger.warning(f"Skipping invalid quiz: {e}")
                    continue

            if not quizzes:
                # Create at least one fallback quiz
                quizzes = [
                    Quiz(
                        question=f"What is the main topic of this segment about {segment_info.get('topic', 'this content')}?",
                        options=[
                            segment_info.get("topic", "Main topic"),
                            "Something else",
                            "Another option",
                            "Different topic",
                        ],
                        correct_index=0,
                        type=QuizType.MULTIPLE_CHOICE,
                        explanation="This segment focuses on the stated topic.",
                    )
                ]

            logger.info(f"Generated {len(quizzes)} quizzes")
            return quizzes

        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            return self._create_fallback_quizzes(segment_info)

    def segment_and_generate_quizzes(
        self,
        transcription: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
    ) -> List[VideoSegment]:
        """
        Complete pipeline: segment video and generate quizzes for each segment

        Args:
            transcription: Video transcription
            frame_analyses: Frame analyses
            video_duration: Video duration in seconds

        Returns:
            List of VideoSegment objects with quizzes
        """
        logger.info("Starting segmentation and quiz generation pipeline")

        # Step 1: Segment the content
        segment_defs = self.segment_transcript(
            transcription, frame_analyses, video_duration
        )

        # Step 2: Generate quizzes for each segment
        video_segments = []

        for seg_def in segment_defs:
            start_time = seg_def.get("start_time", 0)
            end_time = seg_def.get("end_time", video_duration)

            # Get transcript for this segment
            segment_transcript = self._get_transcript_for_range(
                transcription, start_time, end_time
            )

            # Generate quizzes
            quizzes = self.generate_quizzes(seg_def, segment_transcript)

            # Extract keywords from transcript
            keywords = self._extract_keywords(segment_transcript)

            # Create VideoSegment
            video_segment = VideoSegment(
                start_time=start_time,
                end_time=end_time,
                topic_title=seg_def.get("topic", f"Segment {len(video_segments) + 1}"),
                short_summary=seg_def.get("summary", "Video content segment"),
                keywords=keywords,
                quizzes=quizzes,
            )

            video_segments.append(video_segment)
            logger.info(
                f"Completed segment: {video_segment.topic_title} ({start_time:.1f}s - {end_time:.1f}s)"
            )

        logger.info(f"Pipeline completed: {len(video_segments)} segments created")
        return video_segments

    def _parse_json_response(self, response: str) -> List[dict]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON array in response
            start_idx = response.find("[")
            end_idx = response.rfind("]") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Try parsing entire response
                return json.loads(response)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            return []

    def _create_fallback_segments(
        self, video_duration: float, transcription: List[TranscriptionSegment]
    ) -> List[dict]:
        """Create simple time-based segments as fallback"""
        num_segments = min(5, max(3, int(video_duration / 60)))  # 3-5 segments
        segment_duration = video_duration / num_segments

        segments = []
        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, video_duration)

            # Get sample text for this segment
            sample_text = self._get_transcript_for_range(transcription, start, end)
            words = sample_text.split()[:10]
            topic = " ".join(words) if words else f"Segment {i + 1}"

            segments.append(
                {
                    "start_time": start,
                    "end_time": end,
                    "topic": topic[:50] + "..." if len(topic) > 50 else topic,
                    "summary": f"Content from {start:.1f}s to {end:.1f}s",
                }
            )

        return segments

    def _create_fallback_quizzes(self, segment_info: dict) -> List[Quiz]:
        """Create simple fallback quizzes"""
        topic = segment_info.get("topic", "this content")

        return [
            Quiz(
                question=f"What is discussed in the segment about {topic}?",
                options=[topic, "Unrelated topic A", "Unrelated topic B", "Other"],
                correct_index=0,
                type=QuizType.MULTIPLE_CHOICE,
                explanation=f"This segment focuses on {topic}.",
            )
        ]

    def _get_transcript_for_range(
        self,
        transcription: List[TranscriptionSegment],
        start_time: float,
        end_time: float,
    ) -> str:
        """Get transcript text for time range"""
        text_parts = []
        for seg in transcription:
            if seg.end >= start_time and seg.start <= end_time:
                text_parts.append(seg.text)
        return " ".join(text_parts)

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text (simple implementation)"""
        # Remove common words
        stop_words = {
            "the",
            "is",
            "at",
            "which",
            "on",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "with",
            "to",
            "for",
            "of",
            "as",
            "by",
            "that",
            "this",
            "it",
            "from",
            "are",
            "was",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
        }

        # Extract words
        words = text.lower().split()
        keywords = []

        for word in words:
            # Clean word
            word = "".join(c for c in word if c.isalnum())
            if len(word) > 4 and word not in stop_words and word not in keywords:
                keywords.append(word)

        return keywords[:max_keywords]
