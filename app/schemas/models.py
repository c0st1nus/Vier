from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class TaskStatus(str, Enum):
    """Status of video processing task"""

    PENDING = "pending"
    PROCESSING = "processing"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING_FRAMES = "analyzing_frames"
    GENERATING_QUIZZES = "generating_quizzes"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(str, Enum):
    """Current stage of processing"""

    DOWNLOAD = "download"
    AUDIO_EXTRACTION = "audio_extraction"
    TRANSCRIPTION = "transcription"
    FRAME_ANALYSIS = "frame_analysis"
    SEGMENTATION = "segmentation"
    QUIZ_GENERATION = "quiz_generation"
    FINALIZATION = "finalization"


class QuizType(str, Enum):
    """Type of quiz question"""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


# Request models
class VideoUploadResponse(BaseModel):
    """Response after video upload"""

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    message: str = Field(..., description="Status message")


class VideoURLRequest(BaseModel):
    """Request body for URL-based video upload"""

    url: HttpUrl = Field(..., description="YouTube or direct video URL")


class VideoURLResponse(BaseModel):
    """Response after URL submission"""

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(default=TaskStatus.PENDING)


# Status models
class TaskStatusResponse(BaseModel):
    """Current status of a processing task"""

    task_id: str
    status: TaskStatus
    progress: float = Field(
        ..., ge=0, le=100, description="Progress percentage (0-100)"
    )
    current_stage: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Quiz models
class QuizOption(BaseModel):
    """Single quiz option"""

    text: str
    is_correct: bool = False


class QuizTranslation(BaseModel):
    """Translation for a single language"""

    question: str = Field(..., description="Quiz question text")
    options: Optional[List[str]] = Field(
        None, description="Answer options for multiple choice"
    )
    short_answers: Optional[List[str]] = Field(
        None, description="Accepted short answers for this language"
    )
    answer_case_sensitive: bool = Field(
        default=False, description="Whether short answer matching is case-sensitive"
    )
    explanation: Optional[str] = Field(
        None, description="Explanation for the correct answer"
    )


class Quiz(BaseModel):
    """A single quiz question with multilingual support"""

    translations: Dict[str, QuizTranslation] = Field(
        ..., description="Translations for different languages (ru, en, kk)"
    )
    correct_index: Optional[int] = Field(
        None, ge=0, description="Index of correct answer (0-based)"
    )
    type: QuizType = Field(default=QuizType.MULTIPLE_CHOICE)

    # For backward compatibility, provide default language accessors
    @property
    def question(self) -> str:
        """Get question in Russian (default language)"""
        return self.translations.get("ru", list(self.translations.values())[0]).question

    @property
    def options(self) -> List[str]:
        """Get options in Russian (default language)"""
        options = self.translations.get(
            "ru", list(self.translations.values())[0]
        ).options
        return options or []

    @property
    def explanation(self) -> Optional[str]:
        """Get explanation in Russian (default language)"""
        return self.translations.get(
            "ru", list(self.translations.values())[0]
        ).explanation


# Segment models
class SegmentTranslation(BaseModel):
    """Translation for segment text"""

    topic_title: str = Field(..., description="Title/topic of this segment")
    short_summary: str = Field(..., description="Brief summary of segment content")


class VideoSegment(BaseModel):
    """A semantic segment of the video with quizzes and multilingual support"""

    start_time: float = Field(..., ge=0, description="Start time in seconds")
    end_time: float = Field(..., gt=0, description="End time in seconds")
    translations: Dict[str, SegmentTranslation] = Field(
        ..., description="Translations for different languages (ru, en, kk)"
    )
    keywords: List[str] = Field(
        default_factory=list, description="Key terms from segment"
    )
    quizzes: List[Quiz] = Field(
        default_factory=list, description="Generated quiz questions"
    )

    # For backward compatibility
    @property
    def topic_title(self) -> str:
        """Get topic title in Russian (default language)"""
        return self.translations.get(
            "ru", list(self.translations.values())[0]
        ).topic_title

    @property
    def short_summary(self) -> str:
        """Get summary in Russian (default language)"""
        return self.translations.get(
            "ru", list(self.translations.values())[0]
        ).short_summary

    class Config:
        json_schema_extra = {
            "example": {
                "start_time": 0.0,
                "end_time": 45.5,
                "translations": {
                    "ru": {
                        "topic_title": "Введение в нейронные сети",
                        "short_summary": "Обзор основ нейронных сетей и архитектуры",
                    },
                    "en": {
                        "topic_title": "Introduction to Neural Networks",
                        "short_summary": "Overview of neural network basics and architecture",
                    },
                    "kk": {
                        "topic_title": "Нейрондық желілерге кіріспе",
                        "short_summary": "Нейрондық желілердің негіздері мен архитектурасына шолу",
                    },
                },
                "keywords": ["neural networks", "deep learning", "backpropagation"],
                "quizzes": [
                    {
                        "translations": {
                            "ru": {
                                "question": "Какова основная цель обратного распространения?",
                                "options": [
                                    "Прямое вычисление",
                                    "Оптимизация весов",
                                    "Предобработка данных",
                                    "Оценка модели",
                                ],
                                "explanation": "Обратное распространение используется для оптимизации весов",
                            },
                            "en": {
                                "question": "What is the primary purpose of backpropagation?",
                                "options": [
                                    "Forward pass computation",
                                    "Weight optimization",
                                    "Data preprocessing",
                                    "Model evaluation",
                                ],
                                "explanation": "Backpropagation is used for weight optimization",
                            },
                            "kk": {
                                "question": "Кері тарату әдісінің негізгі мақсаты қандай?",
                                "options": [
                                    "Тура есептеу",
                                    "Салмақты оңтайландыру",
                                    "Деректерді алдын ала өңдеу",
                                    "Модельді бағалау",
                                ],
                                "explanation": "Кері тарату салмақты оңтайландыру үшін қолданылады",
                            },
                        },
                        "correct_index": 1,
                        "type": "multiple_choice",
                    }
                ],
            }
        }


class SegmentsResponse(BaseModel):
    """Response containing all video segments"""

    task_id: str
    segments: List[VideoSegment]
    total_duration: float = Field(..., description="Total video duration in seconds")
    video_title: Optional[str] = None


# Internal processing models
class TranscriptionSegment(BaseModel):
    """Individual transcription segment from ASR"""

    start: float
    end: float
    text: str
    confidence: Optional[float] = None


class FrameAnalysis(BaseModel):
    """Analysis result for a video frame"""

    timestamp: float
    description: str
    key_elements: List[str] = Field(default_factory=list)
    frame_path: Optional[str] = None


class VideoMetadata(BaseModel):
    """Metadata about the video"""

    duration: float
    fps: float
    width: int
    height: int
    format: str
    title: Optional[str] = None
    source_url: Optional[str] = None


class ProcessingTask(BaseModel):
    """Internal task tracking model"""

    task_id: str
    status: TaskStatus
    progress: float = 0.0
    current_stage: Optional[ProcessingStage] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    metadata: Optional[VideoMetadata] = None
    transcription: List[TranscriptionSegment] = Field(default_factory=list)
    frame_analyses: List[FrameAnalysis] = Field(default_factory=list)
    segments: List[VideoSegment] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


# Error response
class ErrorResponse(BaseModel):
    """Error response model"""

    error: str
    detail: Optional[str] = None
    task_id: Optional[str] = None
