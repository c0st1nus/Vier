import logging
from pathlib import Path
from typing import List, Optional

import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

from app.core.config import settings
from app.schemas.models import FrameAnalysis
from app.utils.video_utils import clear_vram, get_vram_usage

logger = logging.getLogger(__name__)


class VisionService:
    """Vision analysis service using Qwen2-VL model with optimizations"""

    def __init__(self):
        self.model: Optional[Qwen2VLForConditionalGeneration] = None
        self.processor: Optional[AutoProcessor] = None
        self.model_loaded = False

    def load_model(self):
        """Load Qwen2-VL model with memory optimization"""
        if self.model_loaded:
            logger.info("Qwen2-VL model already loaded")
            return

        try:
            logger.info(f"Loading Qwen2-VL model: {settings.QWEN_MODEL_PATH}")
            allocated, reserved = get_vram_usage()
            logger.info(
                f"VRAM before loading: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
            )

            # Load processor
            self.processor = AutoProcessor.from_pretrained(
                settings.QWEN_MODEL_PATH,
                cache_dir=str(settings.MODELS_DIR),
                trust_remote_code=True,
            )

            # Determine dtype based on settings
            if settings.TORCH_DTYPE == "bfloat16":
                dtype = torch.bfloat16
            elif settings.TORCH_DTYPE == "float16":
                dtype = torch.float16
            else:
                dtype = torch.float32

            # Prepare model loading kwargs
            model_kwargs = {
                "cache_dir": str(settings.MODELS_DIR),
                "torch_dtype": dtype,
                "device_map": "auto",
                "trust_remote_code": True,
            }

            # Add Flash Attention 2 if enabled
            if settings.QWEN_USE_FLASH_ATTENTION:
                logger.info("Enabling Flash Attention 2 for Qwen2-VL")
                model_kwargs["attn_implementation"] = "flash_attention_2"

            # Load model
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                settings.QWEN_MODEL_PATH, **model_kwargs
            )

            self.model.eval()

            # Apply torch.compile if enabled (PyTorch 2.0+)
            if settings.QWEN_USE_TORCH_COMPILE and settings.USE_TORCH_COMPILE:
                logger.info("Compiling Qwen2-VL model with torch.compile()")
                try:
                    # Store original model reference before compilation
                    compiled_model = torch.compile(self.model, mode="reduce-overhead")
                    # Type ignore for compiled model assignment
                    self.model = compiled_model  # type: ignore
                    logger.info("Model compilation successful")
                except Exception as e:
                    logger.warning(
                        f"torch.compile() failed, continuing without it: {e}"
                    )

            self.model_loaded = True

            allocated, reserved = get_vram_usage()
            logger.info(f"Qwen2-VL model loaded successfully")
            logger.info(
                f"VRAM after loading: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
            )

        except Exception as e:
            logger.error(f"Failed to load Qwen2-VL model: {e}")
            self.model_loaded = False
            raise Exception(f"Vision model loading failed: {str(e)}")

    def unload_model(self):
        """Unload model and free VRAM"""
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None

        self.model_loaded = False
        clear_vram()
        logger.info("Qwen2-VL model unloaded")

    def analyze_frame(self, frame_path: Path, prompt: Optional[str] = None) -> str:
        """
        Analyze a single frame and return description

        Args:
            frame_path: Path to frame image
            prompt: Custom prompt for analysis

        Returns:
            Description of frame content

        Raises:
            Exception: If analysis fails
        """
        if not self.model_loaded:
            self.load_model()

        if not frame_path.exists():
            raise FileNotFoundError(f"Frame not found: {frame_path}")

        try:
            # Default prompt for educational video analysis
            if prompt is None:
                prompt = (
                    "Describe what is shown in this educational video frame. "
                    "Focus on key visual elements, text, diagrams, or demonstrations visible. "
                    "Be concise and factual."
                )

            # Check processor is loaded
            if self.processor is None or self.model is None:
                raise Exception("Model or processor not loaded")

            # Prepare messages for Qwen2-VL
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": str(frame_path),
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            # Process inputs
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            vision_info = process_vision_info(messages)
            image_inputs = vision_info[0] if len(vision_info) > 0 else None
            video_inputs = vision_info[1] if len(vision_info) > 1 else None

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )

            # Move to device
            inputs = inputs.to(self.model.device)

            # Generate response
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    temperature=0.7,
                )

            # Trim generated tokens
            generated_ids_trimmed = [
                out_ids[len(in_ids) :]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]

            # Decode output
            description = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]

            logger.debug(f"Frame analysis: {description[:100]}...")
            return description.strip()

        except Exception as e:
            logger.error(f"Frame analysis failed for {frame_path}: {e}")
            return f"[Analysis failed: {str(e)}]"

        finally:
            # Clear VRAM only if not keeping models in memory
            if not settings.MODELS_STAY_IN_MEMORY:
                clear_vram()

    def analyze_frames_batch(
        self,
        frame_paths: List[Path],
        prompt: Optional[str] = None,
    ) -> List[str]:
        """
        Analyze multiple frames in batches for better performance

        Args:
            frame_paths: List of paths to frame images
            prompt: Custom prompt for all frames

        Returns:
            List of descriptions

        Raises:
            Exception: If analysis fails
        """
        if not self.model_loaded:
            self.load_model()

        batch_size = settings.QWEN_BATCH_SIZE
        logger.info(f"Analyzing {len(frame_paths)} frames with batch size {batch_size}")

        # Default prompt
        if prompt is None:
            prompt = (
                "Describe what is shown in this educational video frame. "
                "Focus on key visual elements, text, diagrams, or demonstrations visible. "
                "Be concise and factual."
            )

        all_descriptions = []

        try:
            for i in range(0, len(frame_paths), batch_size):
                batch_paths = frame_paths[i : i + batch_size]
                logger.debug(
                    f"Processing batch {i // batch_size + 1}: {len(batch_paths)} frames"
                )

                # Prepare batch messages
                batch_messages = []
                for frame_path in batch_paths:
                    if not frame_path.exists():
                        logger.warning(f"Frame not found: {frame_path}")
                        all_descriptions.append("[Frame not found]")
                        continue

                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": str(frame_path)},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ]
                    batch_messages.append(messages)

                if not batch_messages:
                    continue

                # Process batch
                batch_texts = []
                batch_image_inputs = []
                batch_video_inputs = []

                # Check processor is loaded
                if self.processor is None or self.model is None:
                    raise Exception("Model or processor not loaded")

                for messages in batch_messages:
                    text = self.processor.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                    batch_texts.append(text)

                    vision_info = process_vision_info(messages)
                    imgs = vision_info[0] if len(vision_info) > 0 else None
                    vids = vision_info[1] if len(vision_info) > 1 else None

                    if imgs:
                        batch_image_inputs.extend(imgs)
                    if vids:
                        batch_video_inputs.extend(vids)

                # Batch processing
                inputs = self.processor(
                    text=batch_texts,
                    images=batch_image_inputs if batch_image_inputs else None,
                    videos=batch_video_inputs if batch_video_inputs else None,
                    padding=True,
                    return_tensors="pt",
                )

                inputs = inputs.to(self.model.device)

                # Generate for batch
                with torch.no_grad():
                    generated_ids = self.model.generate(
                        **inputs,
                        max_new_tokens=256,
                        do_sample=False,
                    )

                # Trim and decode
                generated_ids_trimmed = [
                    out_ids[len(in_ids) :]
                    for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]

                descriptions = self.processor.batch_decode(
                    generated_ids_trimmed,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )

                all_descriptions.extend([desc.strip() for desc in descriptions])

                # Clear cache between batches if not keeping in memory
                if not settings.MODELS_STAY_IN_MEMORY:
                    clear_vram()

            logger.info(
                f"Batch analysis completed: {len(all_descriptions)} descriptions"
            )
            return all_descriptions

        except Exception as e:
            logger.error(f"Batch frame analysis failed: {e}")
            raise Exception(f"Vision batch analysis failed: {str(e)}")

    def analyze_frames(
        self, frame_paths: List[Path], batch_size: Optional[int] = None
    ) -> List[FrameAnalysis]:
        """
        Analyze multiple video frames

        Args:
            frame_paths: List of paths to frame images
            batch_size: Override default batch size (deprecated, uses settings)

        Returns:
            List of FrameAnalysis objects

        Raises:
            Exception: If analysis fails
        """
        if not self.model_loaded:
            self.load_model()

        logger.info(f"Analyzing {len(frame_paths)} frames")

        try:
            # Use batch processing if batch size > 1
            if settings.QWEN_BATCH_SIZE > 1:
                descriptions = self.analyze_frames_batch(frame_paths)
            else:
                # Fallback to single frame processing
                descriptions = []
                for i, frame_path in enumerate(frame_paths):
                    desc = self.analyze_frame(frame_path)
                    descriptions.append(desc)
                    logger.info(f"Analyzed frame {i + 1}/{len(frame_paths)}")

            # Build FrameAnalysis objects
            analyses = []
            for i, (frame_path, description) in enumerate(
                zip(frame_paths, descriptions)
            ):
                # Extract timestamp from filename (format: frame_123.45s.jpg)
                try:
                    timestamp_str = frame_path.stem.split("_")[1].replace("s", "")
                    timestamp = float(timestamp_str)
                except (IndexError, ValueError):
                    timestamp = i * 10.0  # Fallback: assume 10s intervals
                    logger.warning(
                        f"Could not parse timestamp from {frame_path.name}, using {timestamp}s"
                    )

                # Extract key elements
                key_elements = self._extract_key_elements(description)

                analysis = FrameAnalysis(
                    timestamp=timestamp,
                    description=description,
                    key_elements=key_elements,
                    frame_path=str(frame_path),
                )

                analyses.append(analysis)

            logger.info(f"Frame analysis completed: {len(analyses)} frames analyzed")
            return analyses

        except Exception as e:
            logger.error(f"Failed to analyze frames: {e}")
            raise Exception(f"Vision analysis failed: {str(e)}")

    def _extract_key_elements(self, description: str) -> List[str]:
        """
        Extract key elements/keywords from description

        Args:
            description: Frame description text

        Returns:
            List of key elements
        """
        # Simple keyword extraction based on common patterns
        keywords = []

        # Look for quoted terms
        import re

        quoted = re.findall(r'"([^"]+)"', description)
        keywords.extend(quoted)

        # Look for capitalized terms (likely proper nouns or important concepts)
        capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", description)
        keywords.extend(capitalized[:5])  # Limit to top 5

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_keywords.append(kw)

        return unique_keywords[:10]  # Return max 10 keywords

    def batch_analyze_with_prompt(
        self, frame_paths: List[Path], custom_prompt: str
    ) -> List[str]:
        """
        Analyze multiple frames with a custom prompt

        Args:
            frame_paths: List of frame paths
            custom_prompt: Custom prompt for all frames

        Returns:
            List of descriptions
        """
        if not self.model_loaded:
            self.load_model()

        return self.analyze_frames_batch(frame_paths, prompt=custom_prompt)
