import logging
from typing import Dict, List, Optional

from vllm import LLM, SamplingParams

from app.core.config import settings
from app.schemas.models import (
    FrameAnalysis,
    Quiz,
    QuizTranslation,
    QuizType,
    SegmentTranslation,
    TranscriptionSegment,
    VideoSegment,
)

logger = logging.getLogger(__name__)


class VLLMService:
    """LLM service using vLLM for fast inference"""

    def __init__(self):
        self.model_name = settings.VLLM_MODEL
        self.model: Optional[LLM] = None
        self.model_loaded = False

    def load_model(self):
        """Load vLLM model"""
        if self.model_loaded:
            logger.info("vLLM model already loaded")
            return

        try:
            logger.info(f"Loading vLLM model: {self.model_name}")
            logger.info(
                f"GPU memory utilization: {settings.VLLM_GPU_MEMORY_UTILIZATION}"
            )

            self.model = LLM(
                model=self.model_name,
                tensor_parallel_size=settings.VLLM_TENSOR_PARALLEL_SIZE,
                gpu_memory_utilization=settings.VLLM_GPU_MEMORY_UTILIZATION,
                max_model_len=settings.VLLM_MAX_MODEL_LEN,
                dtype=settings.VLLM_DTYPE,
                trust_remote_code=True,
                download_dir=str(settings.MODELS_DIR),
            )

            self.model_loaded = True
            logger.info("vLLM model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load vLLM model: {e}")
            self.model_loaded = False
            raise Exception(f"vLLM model loading failed: {str(e)}")

    def unload_model(self):
        """Unload vLLM model"""
        if self.model is not None:
            del self.model
            self.model = None
            self.model_loaded = False
            logger.info("vLLM model unloaded")

    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        """
        Generate text from prompt using vLLM

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        if not self.model_loaded or self.model is None:
            self.load_model()

        try:
            sampling_params = SamplingParams(
                temperature=settings.LLAMA_TEMPERATURE,
                max_tokens=max_tokens,
                top_p=0.95,
                top_k=50,
            )

            outputs = self.model.generate([prompt], sampling_params)
            generated_text = outputs[0].outputs[0].text

            return generated_text.strip()

        except Exception as e:
            logger.error(f"vLLM generation failed: {e}")
            raise Exception(f"Text generation failed: {str(e)}")

    def generate_batch(self, prompts: List[str], max_tokens: int = 1024) -> List[str]:
        """
        Generate text for multiple prompts in batch (faster!)

        Args:
            prompts: List of prompts
            max_tokens: Maximum tokens to generate

        Returns:
            List of generated texts
        """
        if not self.model_loaded or self.model is None:
            self.load_model()

        try:
            sampling_params = SamplingParams(
                temperature=settings.LLAMA_TEMPERATURE,
                max_tokens=max_tokens,
                top_p=0.95,
                top_k=50,
            )

            outputs = self.model.generate(prompts, sampling_params)
            results = [output.outputs[0].text.strip() for output in outputs]

            return results

        except Exception as e:
            logger.error(f"vLLM batch generation failed: {e}")
            raise Exception(f"Batch text generation failed: {str(e)}")

    # Copy all the other methods from llm_service.py but use self.generate_text()
    # instead of the Ollama API calls

    def segment_video_content(
        self,
        transcript_segments: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
    ) -> List[VideoSegment]:
        """Segment video content into logical topics using vLLM"""
        logger.info("Segmenting video content into topics")

        # Build context
        transcript_text = " ".join(
            [seg.text for seg in transcript_segments if seg.text]
        )
        frame_descriptions = "\n".join(
            [
                f"[{fa.timestamp:.1f}s] {fa.description}"
                for fa in frame_analyses
                if fa.description
            ]
        )

        # Create segmentation prompt
        prompt = f"""You are a video content analyst. Analyze this video and segment it into logical topics.

Video Duration: {video_duration:.1f} seconds

Transcript:
{transcript_text}

Visual Content:
{frame_descriptions}

TASK: Divide the video into 1-3 logical segments based on topic changes.
Each segment should be at least 30 seconds long.

Respond with ONLY valid JSON (no markdown, no explanations):
[
  {{
    "title": "Topic Title",
    "start_time": 0.0,
    "end_time": 10.5,
    "description": "Brief description"
  }}
]"""

        try:
            response_text = self.generate_text(prompt, max_tokens=2048)

            # Parse JSON response
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            segments_data = json.loads(response_text)

            # Convert to VideoSegment objects
            segments = []
            for seg_data in segments_data:
                segment = VideoSegment(
                    title=seg_data.get("title", "Untitled Segment"),
                    start_time=float(seg_data.get("start_time", 0)),
                    end_time=float(seg_data.get("end_time", video_duration)),
                    description=seg_data.get("description", ""),
                    quizzes=[],
                )
                segments.append(segment)

            logger.info(f"Created {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            # Fallback: create single segment
            return [
                VideoSegment(
                    title="Full Video",
                    start_time=0.0,
                    end_time=video_duration,
                    description=transcript_text[:200] if transcript_text else "",
                    quizzes=[],
                )
            ]

    def generate_quiz_for_segment(
        self,
        segment: VideoSegment,
        transcript_text: str,
        frame_descriptions: str,
        language: str = "en",
        num_quizzes: int = 3,
    ) -> List[Quiz]:
        """Generate quizzes for a segment using vLLM"""
        logger.info(f"Generating multilingual quizzes for: {segment.title}")

        prompt = f"""Generate {num_quizzes} educational quiz questions based on this video segment.

Segment: {segment.title}
Time: {segment.start_time:.1f}s - {segment.end_time:.1f}s

Transcript:
{transcript_text}

Visual Content:
{frame_descriptions}

IMPORTANT:
- Generate questions in BOTH English AND the detected language ({language})
- Questions must be based on actual content from the video
- Include 4 answer options for each question
- Mark the correct answer

Respond with ONLY valid JSON:
[
  {{
    "question_en": "Question in English",
    "question_{language}": "Question in {language}",
    "options_en": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "options_{language}": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
    "correct_answer": 0,
    "explanation_en": "Why this is correct",
    "explanation_{language}": "Почему это правильно"
  }}
]"""

        try:
            response_text = self.generate_text(prompt, max_tokens=3072)

            # Parse JSON
            import json
            import re

            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            quizzes_data = json.loads(response_text)

            quizzes = []
            for i, quiz_data in enumerate(quizzes_data[:num_quizzes]):
                quiz = Quiz(
                    question=quiz_data.get("question_en", f"Question {i + 1}"),
                    options=quiz_data.get("options_en", []),
                    correct_answer=quiz_data.get("correct_answer", 0),
                    explanation=quiz_data.get("explanation_en", ""),
                    quiz_type=QuizType.MULTIPLE_CHOICE,
                    timestamp=segment.start_time,
                    translations={},
                )

                # Add translations
                if f"question_{language}" in quiz_data:
                    quiz.translations[language] = QuizTranslation(
                        question=quiz_data.get(f"question_{language}", ""),
                        options=quiz_data.get(f"options_{language}", []),
                        explanation=quiz_data.get(f"explanation_{language}", ""),
                    )

                quizzes.append(quiz)

            logger.info(f"Generated {len(quizzes)} multilingual quizzes")
            return quizzes

        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            return []

    def segment_and_generate_quizzes(
        self,
        transcript_segments: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
        language: str = "en",
        num_quizzes_per_segment: int = 3,
    ) -> List[VideoSegment]:
        """
        Segment video and generate quizzes for each segment using vLLM

        Args:
            transcript_segments: List of transcription segments
            frame_analyses: List of frame analyses
            video_duration: Total video duration
            language: Detected language code
            num_quizzes_per_segment: Number of quizzes per segment

        Returns:
            List of VideoSegments with quizzes
        """
        logger.info("Segmenting video and generating quizzes")

        # Step 1: Segment the video
        segments = self.segment_video_content(
            transcript_segments, frame_analyses, video_duration
        )

        # Step 2: Generate quizzes for each segment
        for segment in segments:
            # Get transcript text for this segment
            segment_transcript = " ".join(
                [
                    seg.text
                    for seg in transcript_segments
                    if seg.start >= segment.start_time and seg.end <= segment.end_time
                ]
            )

            # Get frame descriptions for this segment
            segment_frames = [
                f"[{fa.timestamp:.1f}s] {fa.description}"
                for fa in frame_analyses
                if segment.start_time <= fa.timestamp <= segment.end_time
            ]
            frame_descriptions = "\n".join(segment_frames)

            # Generate quizzes
            quizzes = self.generate_quiz_for_segment(
                segment,
                segment_transcript,
                frame_descriptions,
                language,
                num_quizzes_per_segment,
            )

            segment.quizzes = quizzes

        logger.info(
            f"Completed segmentation and quiz generation for {len(segments)} segments"
        )
        return segments

    def generate_video_title(
        self, transcript_text: str, frame_descriptions: str, language: str = "en"
    ) -> str:
        """Generate video title using vLLM"""
        logger.info("Generating video title")

        prompt = f"""Generate a short, engaging title for this video content.

Transcript:
{transcript_text[:500]}

Visual Content:
{frame_descriptions[:500]}

Detected Language: {language}

TASK: Generate a title in the detected language ({language}).
The title should be 5-10 words, catchy and descriptive.

Respond with ONLY the title text (no quotes, no explanations):"""

        try:
            title = self.generate_text(prompt, max_tokens=50)
            title = title.strip().strip('"').strip("'")
            logger.info(f"Generated title: {title}")
            return title
        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            return "Untitled Video"
