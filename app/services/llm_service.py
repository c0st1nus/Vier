import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests

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

    def generate_video_title(
        self,
        transcription: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
        language: str = "ru",
    ) -> str:
        """
        Generate a descriptive title for the video based on its content

        Args:
            transcription: List of transcription segments
            frame_analyses: List of frame analyses
            video_duration: Total video duration

        Returns:
            Generated video title
        """
        if not self.model_loaded:
            self.load_model()

        logger.info("Generating video title")

        try:
            # Prepare context from transcription
            transcript_text = " ".join([seg.text for seg in transcription[:50]])

            # Get frame descriptions at key timestamps
            frame_context = "\n".join(
                [
                    f"At {fa.timestamp:.1f}s: {fa.description[:100]}"
                    for fa in frame_analyses[:5]
                ]
            )

            # Create title generation prompt
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert at creating concise, descriptive titles for educational video content.<|eot_id|><|start_header_id|>user<|end_header_id|>

Video Duration: {video_duration:.1f} seconds

Transcript excerpt:
{transcript_text[:1000]}

Visual Information:
{frame_context}

Task: Generate a short, descriptive title for this video (maximum 80 characters). The title should:
1. Capture the main topic or theme
2. Be clear and engaging
3. Be concise and informative

Respond with ONLY the title text, nothing else.

Response:"""

            # Generate title
            title = self.generate_text(prompt, max_tokens=100)

            # Clean up the title
            title = title.strip().strip("\"'").strip()

            # Truncate if too long
            if len(title) > 80:
                title = title[:77] + "..."

            # Fallback if empty
            if not title or len(title) < 3:
                logger.warning("Generated title too short, using fallback")
                # Use first few words from transcript as fallback
                words = transcript_text.split()[:8]
                title = " ".join(words)
                if len(title) > 80:
                    title = title[:77] + "..."

            logger.info(f"Generated title: {title}")
            return title

        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            # Fallback: use first few words from transcript
            transcript_text = " ".join([seg.text for seg in transcription[:10]])
            words = transcript_text.split()[:8]
            title = " ".join(words)
            if len(title) > 80:
                title = title[:77] + "..."
            return title if title else "Untitled Video"

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

    def generate_multilingual_quizzes(
        self, segment_info: dict, transcript_text: str
    ) -> List[Quiz]:
        """
        Generate quiz questions in multiple languages (ru, en, kk)

        Args:
            segment_info: Segment information (topic, summary, etc.)
            transcript_text: Transcript text for this segment

        Returns:
            List of Quiz objects with multilingual translations
        """
        if not self.model_loaded:
            self.load_model()

        logger.info(
            f"Generating multilingual quizzes for: {segment_info.get('topic', 'segment')}"
        )

        try:
            # Create quiz generation prompt for all three languages
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert multilingual educator. Create quiz questions in THREE languages: Russian (ru), English (en), and Kazakh (kk).<|eot_id|><|start_header_id|>user<|end_header_id|>

Topic: {segment_info.get("topic", "Video Content")}
Summary: {segment_info.get("summary", "")}

Content:
{transcript_text[:1500]}

Task: Create {settings.QUIZZES_PER_SEGMENT} multiple-choice questions AND {settings.SHORT_ANSWER_QUIZZES_PER_SEGMENT} short-answer questions. For EACH question, provide translations in ALL THREE languages.

Format as JSON array with this EXACT structure:
[
  {{
    "type": "multiple_choice",
    "translations": {{
      "ru": {{
        "question": "Вопрос на русском?",
        "options": ["Вариант А", "Вариант Б", "Вариант В", "Вариант Г"],
        "explanation": "Объяснение на русском"
      }},
      "en": {{
        "question": "Question in English?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "explanation": "Explanation in English"
      }},
      "kk": {{
        "question": "Сұрақ қазақ тілінде?",
        "options": ["Нұсқа А", "Нұсқа Б", "Нұсқа В", "Нұсқа Г"],
        "explanation": "Қазақ тіліндегі түсініктеме"
      }}
    }},
    "correct_index": 1
  }},
  {{
    "type": "short_answer",
    "translations": {{
      "ru": {{
        "question": "Короткий вопрос на русском?",
        "short_answers": ["правильный ответ", "короткий вариант"],
        "answer_case_sensitive": false,
        "explanation": "Объяснение на русском"
      }},
      "en": {{
        "question": "Short answer question in English?",
        "short_answers": ["correct answer", "short variant"],
        "answer_case_sensitive": false,
        "explanation": "Explanation in English"
      }},
      "kk": {{
        "question": "Қысқа жауап сұрағы?",
        "short_answers": ["дұрыс жауап", "қысқа нұсқа"],
        "answer_case_sensitive": false,
        "explanation": "Қазақ тіліндегі түсініктеме"
      }}
    }}
  }}
]

IMPORTANT:
- All three translations must have the SAME correct_index for multiple_choice
- short_answer questions MUST NOT include correct_index or options
- short_answer must include short_answers array per language

Response:"""

            # Generate quizzes
            response = self.generate_text(prompt, max_tokens=2048)

            # Parse JSON response
            quiz_data = self._parse_json_response(response)

            if not quiz_data:
                logger.warning(
                    "Could not parse multilingual quiz response, using fallback"
                )
                return self._create_fallback_multilingual_quizzes(segment_info)

            # Convert to Quiz objects
            quizzes = []
            total_mc = settings.QUIZZES_PER_SEGMENT
            total_short = settings.SHORT_ANSWER_QUIZZES_PER_SEGMENT
            target_total = total_mc + total_short
            mc_count = 0
            short_count = 0

            for item in quiz_data:
                if len(quizzes) >= target_total:
                    break
                try:
                    translations_data = item.get("translations", {})
                    item_type = item.get("type", "multiple_choice")

                    # Validate that we have all three languages
                    if not all(
                        lang in translations_data for lang in ["ru", "en", "kk"]
                    ):
                        logger.warning("Missing language translations, skipping quiz")
                        continue

                    if (
                        item_type == QuizType.SHORT_ANSWER.value
                        or item_type == "short_answer"
                    ):
                        if short_count >= total_short:
                            continue

                        translations = {}
                        for lang in ["ru", "en", "kk"]:
                            trans = translations_data[lang] or {}
                            translations[lang] = QuizTranslation(
                                question=trans.get("question", "Question?"),
                                short_answers=trans.get("short_answers"),
                                answer_case_sensitive=bool(
                                    trans.get("answer_case_sensitive", False)
                                ),
                                explanation=trans.get("explanation"),
                            )

                        if not any(
                            (translations[lang].short_answers or [])
                            for lang in ["ru", "en", "kk"]
                        ):
                            logger.warning("Missing short_answers, skipping quiz")
                            continue

                        quiz = Quiz(
                            translations=translations,
                            correct_index=None,
                            type=QuizType.SHORT_ANSWER,
                        )
                        quizzes.append(quiz)
                        short_count += 1
                    else:
                        if mc_count >= total_mc:
                            continue

                        if item.get("correct_index") is None:
                            logger.warning("Missing correct_index, skipping quiz")
                            continue

                        translations = {}
                        for lang in ["ru", "en", "kk"]:
                            trans = translations_data[lang] or {}
                            translations[lang] = QuizTranslation(
                                question=trans.get("question", "Question?"),
                                options=trans.get("options", ["A", "B", "C", "D"]),
                                explanation=trans.get("explanation"),
                            )

                        quiz = Quiz(
                            translations=translations,
                            correct_index=item.get("correct_index", 0),
                            type=QuizType.MULTIPLE_CHOICE,
                        )
                        quizzes.append(quiz)
                        mc_count += 1
                except Exception as e:
                    logger.warning(f"Skipping invalid multilingual quiz: {e}")
                    continue

            if not quizzes:
                logger.warning("No valid quizzes generated, using fallback")
                return self._create_fallback_multilingual_quizzes(segment_info)

            logger.info(f"Generated {len(quizzes)} multilingual quizzes")
            return quizzes

        except Exception as e:
            logger.error(f"Multilingual quiz generation failed: {e}")
            return self._create_fallback_multilingual_quizzes(segment_info)

    def generate_quizzes(self, segment_info: dict, transcript_text: str) -> List[Quiz]:
        """
        Generate quiz questions for a video segment (uses multilingual generation)

        Args:
            segment_info: Segment information (topic, summary, etc.)
            transcript_text: Transcript text for this segment

        Returns:
            List of Quiz objects
        """
        return self.generate_multilingual_quizzes(segment_info, transcript_text)

    def translate_segment_text(
        self, topic: str, summary: str
    ) -> Dict[str, SegmentTranslation]:
        """
        Translate segment title and summary to all three languages

        Args:
            topic: Original topic title
            summary: Original summary

        Returns:
            Dict with translations for ru, en, kk
        """
        if not self.model_loaded:
            self.load_model()

        try:
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a professional translator. Translate the following video segment information into Russian, English, and Kazakh.<|eot_id|><|start_header_id|>user<|end_header_id|>

Original Topic: {topic}
Original Summary: {summary}

Provide translations in JSON format:
{{
  "ru": {{
    "topic_title": "Заголовок на русском",
    "short_summary": "Краткое описание на русском"
  }},
  "en": {{
    "topic_title": "Title in English",
    "short_summary": "Short description in English"
  }},
  "kk": {{
    "topic_title": "Қазақ тіліндегі тақырып",
    "short_summary": "Қазақ тіліндегі қысқаша сипаттама"
  }}
}}

Response:"""

            response = self.generate_text(prompt, max_tokens=512)
            logger.debug(f"Translation response (first 500 chars): {response[:500]}")

            # Parse JSON object (not array) for translations
            try:
                # Try to find JSON object in response
                start_idx = response.find("{")
                end_idx = response.rfind("}") + 1

                if start_idx != -1 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    # Clean invalid control characters from JSON
                    json_str = (
                        json_str.replace("\n", " ")
                        .replace("\r", " ")
                        .replace("\t", " ")
                    )
                    # Remove other control characters
                    json_str = "".join(
                        char if ord(char) >= 32 or char in "\n\r\t" else " "
                        for char in json_str
                    )
                    translations_data = json.loads(json_str)
                else:
                    # Try parsing entire response
                    response_clean = (
                        response.replace("\n", " ")
                        .replace("\r", " ")
                        .replace("\t", " ")
                    )
                    translations_data = json.loads(response_clean)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed for translations: {e}")
                logger.debug(f"Failed to parse response: {response[:1000]}")
                raise ValueError("Invalid translation response")

            if not translations_data or not isinstance(translations_data, dict):
                raise ValueError("Invalid translation response")

            translations = {}
            for lang in ["ru", "en", "kk"]:
                if lang in translations_data:
                    trans = translations_data[lang]
                    translations[lang] = SegmentTranslation(
                        topic_title=trans.get("topic_title", topic),
                        short_summary=trans.get("short_summary", summary),
                    )
                else:
                    # Fallback
                    translations[lang] = SegmentTranslation(
                        topic_title=topic, short_summary=summary
                    )

            return translations

        except Exception as e:
            logger.error(f"Translation failed: {e}, using fallback")
            # Fallback: use same text for all languages
            return {
                lang: SegmentTranslation(topic_title=topic, short_summary=summary)
                for lang in ["ru", "en", "kk"]
            }

    def segment_and_generate_quizzes(
        self,
        transcription: List[TranscriptionSegment],
        frame_analyses: List[FrameAnalysis],
        video_duration: float,
        language: str = "ru",
    ) -> List[VideoSegment]:
        """
        Complete pipeline: segment video and generate multilingual quizzes for each segment

        Args:
            transcription: Video transcription
            frame_analyses: Frame analyses
            video_duration: Video duration in seconds

        Returns:
            List of VideoSegment objects with multilingual quizzes
        """
        logger.info("Starting multilingual segmentation and quiz generation pipeline")

        # Step 1: Segment the content
        segment_defs = self.segment_transcript(
            transcription, frame_analyses, video_duration
        )

        # Step 2: Generate multilingual quizzes for each segment
        video_segments = []

        for seg_def in segment_defs:
            start_time = seg_def.get("start_time", 0)
            end_time = seg_def.get("end_time", video_duration)

            # Get transcript for this segment
            segment_transcript = self._get_transcript_for_range(
                transcription, start_time, end_time
            )

            # Generate multilingual quizzes
            quizzes = self.generate_multilingual_quizzes(seg_def, segment_transcript)

            # Translate segment title and summary
            topic = seg_def.get("topic", f"Segment {len(video_segments) + 1}")
            summary = seg_def.get("summary", "Video content segment")
            translations = self.translate_segment_text(topic, summary)

            # Extract keywords from transcript
            keywords = self._extract_keywords(segment_transcript)

            # Create VideoSegment with multilingual support
            video_segment = VideoSegment(
                start_time=start_time,
                end_time=end_time,
                translations=translations,
                keywords=keywords,
                quizzes=quizzes,
            )

            video_segments.append(video_segment)
            logger.info(
                f"Completed multilingual segment: {topic} ({start_time:.1f}s - {end_time:.1f}s)"
            )

        logger.info(
            f"Pipeline completed: {len(video_segments)} multilingual segments created"
        )
        return video_segments

    def _parse_json_response(self, response: str) -> List[dict]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON array in response
            start_idx = response.find("[")
            end_idx = response.rfind("]") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
            else:
                # Try parsing entire response
                json_str = response

            # Clean control characters that might break JSON parsing
            # Remove literal newlines, tabs, and other control characters from string values
            json_str = (
                json_str.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
            )

            # Remove actual control characters (but keep JSON structural characters)
            cleaned = []
            in_string = False
            escape_next = False

            for char in json_str:
                if escape_next:
                    cleaned.append(char)
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    cleaned.append(char)
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    cleaned.append(char)
                    continue

                # If we're inside a string, replace control characters with spaces
                if in_string and ord(char) < 32 and char not in "\n\r\t":
                    cleaned.append(" ")
                else:
                    cleaned.append(char)

            json_str = "".join(cleaned)

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            logger.debug(f"Failed to parse response: {response[:1000]}")
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

    def _create_fallback_multilingual_quizzes(self, segment_info: dict) -> List[Quiz]:
        """Create simple fallback quizzes with multilingual support"""
        topic = segment_info.get("topic", "this content")

        translations = {
            "ru": QuizTranslation(
                question=f"О чём говорится в этом сегменте про {topic}?",
                options=[topic, "Несвязанная тема А", "Несвязанная тема Б", "Другое"],
                explanation=f"Этот сегмент посвящён {topic}.",
            ),
            "en": QuizTranslation(
                question=f"What is discussed in the segment about {topic}?",
                options=[topic, "Unrelated topic A", "Unrelated topic B", "Other"],
                explanation=f"This segment focuses on {topic}.",
            ),
            "kk": QuizTranslation(
                question=f"{topic} туралы бұл сегментте не талқыланады?",
                options=[
                    topic,
                    "Байланыссыз тақырып А",
                    "Байланыссыз тақырып Б",
                    "Басқа",
                ],
                explanation=f"Бұл сегмент {topic} туралы.",
            ),
        }

        quizzes = [
            Quiz(
                translations=translations,
                correct_index=0,
                type=QuizType.MULTIPLE_CHOICE,
            )
        ]

        if settings.SHORT_ANSWER_QUIZZES_PER_SEGMENT > 0:
            short_translations = {
                "ru": QuizTranslation(
                    question=f"Назовите ключевую тему сегмента про {topic}.",
                    short_answers=[topic],
                    answer_case_sensitive=False,
                    explanation=f"Ключевая тема сегмента — {topic}.",
                ),
                "en": QuizTranslation(
                    question=f"Name the key topic of the segment about {topic}.",
                    short_answers=[topic],
                    answer_case_sensitive=False,
                    explanation=f"The key topic of the segment is {topic}.",
                ),
                "kk": QuizTranslation(
                    question=f"{topic} туралы сегменттің негізгі тақырыбын атаңыз.",
                    short_answers=[topic],
                    answer_case_sensitive=False,
                    explanation=f"Сегменттің негізгі тақырыбы — {topic}.",
                ),
            }

            quizzes.append(
                Quiz(
                    translations=short_translations,
                    correct_index=None,
                    type=QuizType.SHORT_ANSWER,
                )
            )

        return quizzes

    def _create_fallback_quizzes(self, segment_info: dict) -> List[Quiz]:
        """Create simple fallback quizzes (uses multilingual version)"""
        return self._create_fallback_multilingual_quizzes(segment_info)

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
