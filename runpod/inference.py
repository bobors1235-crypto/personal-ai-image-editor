"""
Inference Provider Layer for RunPod Image Editing.
Features modular providers for FireRed-Image-Edit-1.1 and Qwen-Image-Edit-2511.
"""

import os
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from PIL import Image

try:
    from image_utils import resize_image_aspect_ratio
    from model_loader import ModelManager
except ImportError:
    from runpod.image_utils import resize_image_aspect_ratio
    from runpod.model_loader import ModelManager

try:
    import torch
    from diffusers import DiffusionPipeline
except ImportError:
    torch = None
    DiffusionPipeline = None

logger = logging.getLogger("inference")
logging.basicConfig(level=logging.INFO)


class InferenceProvider(ABC):
    """Abstract base class for all image editing model providers."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.pipeline = None
        self.is_loaded = False

    @abstractmethod
    def load(self) -> bool:
        """Load model into GPU memory."""
        pass

    @abstractmethod
    def unload(self):
        """Unload model and free GPU memory."""
        pass

    @abstractmethod
    def edit(
        self,
        image: Image.Image,
        prompt: str,
        seed: Optional[int] = None,
        quality: str = "high",
        identity_strength: str = "high",
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None
    ) -> Tuple[Image.Image, int, float, Dict[str, Any]]:
        """
        Execute image edit.
        Returns (result_image, actual_seed, processing_time_seconds, metadata).
        """
        pass


class FireRedProvider(InferenceProvider):
    """
    Provider for FireRed-Image-Edit-1.1 foundation model.
    Maintains strong identity consistency and high photorealism.
    """

    DEFAULT_MODEL_ID = "FireRedTeam/FireRed-Image-Edit-1.1"

    def __init__(self, model_id: Optional[str] = None):
        super().__init__(model_id or self.DEFAULT_MODEL_ID)

    def load(self) -> bool:
        if self.is_loaded and self.pipeline is not None:
            return True

        if os.environ.get("MOCK_INFERENCE") == "1" or torch is None or DiffusionPipeline is None or not torch.cuda.is_available():
            logger.info("CUDA not detected or MOCK_INFERENCE enabled. Using lightweight simulation mode.")
            self.is_loaded = True
            return True

        logger.info(f"Loading FireRed-Image-Edit-1.1 from {self.model_id}...")
        start_t = time.time()
        cache_dir = ModelManager.get_cache_dir()
        dtype = ModelManager.get_dtype()
        device = "cuda"

        try:
            # Try specialized pipeline first or fallback to standard DiffusionPipeline
            self.pipeline = DiffusionPipeline.from_pretrained(
                self.model_id,
                torch_dtype=dtype,
                cache_dir=cache_dir,
                trust_remote_code=True
            )
            self.pipeline.to(device)

            # Enable memory optimizations if available
            if hasattr(self.pipeline, "enable_attention_slicing"):
                self.pipeline.enable_attention_slicing()
            if hasattr(self.pipeline, "enable_vae_tiling"):
                self.pipeline.enable_vae_tiling()

            self.is_loaded = True
            load_time = round(time.time() - start_t, 2)
            logger.info(f"FireRed-Image-Edit-1.1 loaded successfully in {load_time}s on {device}.")
            return True
        except Exception as e:
            logger.error(f"Failed to load FireRed model: {e}")
            self.unload()
            raise e

    def unload(self):
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
        self.is_loaded = False
        ModelManager.clear_vram()
        logger.info("FireRed-Image-Edit-1.1 unloaded.")

    def edit(
        self,
        image: Image.Image,
        prompt: str,
        seed: Optional[int] = None,
        quality: str = "high",
        identity_strength: str = "high",
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None
    ) -> Tuple[Image.Image, int, float, Dict[str, Any]]:
        if not self.is_loaded:
            self.load()

        actual_seed = seed if (seed is not None and seed >= 0) else random.randint(100000, 999999999)
        start_t = time.time()

        # Step count and resolution tuning
        max_dim = 1536 if quality == "high" else 1024
        inference_steps = steps or (35 if quality == "high" else 25)
        guidance = guidance_scale or (7.5 if identity_strength == "high" else 6.0)

        # Preprocess input image dimensions
        processed_image, orig_size = resize_image_aspect_ratio(image, max_dim=max_dim, multiple_of=64)

        if torch is None or self.pipeline is None:
            # Mock behavior for local testing without full CUDA/weights
            time.sleep(1.0)
            result_img = processed_image.copy()
            proc_time = round(time.time() - start_t, 2)
            return result_img, actual_seed, proc_time, {
                "engine": "mock_fire_red",
                "steps": inference_steps,
                "guidance_scale": guidance,
                "resolution": f"{processed_image.width}x{processed_image.height}"
            }

        generator = torch.Generator(device=self.pipeline.device).manual_seed(actual_seed)

        with torch.inference_mode():
            output = self.pipeline(
                prompt=prompt,
                image=processed_image,
                num_inference_steps=inference_steps,
                guidance_scale=guidance,
                generator=generator
            )
            result_img = output.images[0]

        proc_time = round(time.time() - start_t, 2)
        metadata = {
            "model": self.model_id,
            "steps": inference_steps,
            "guidance_scale": guidance,
            "resolution": f"{result_img.width}x{result_img.height}",
            "device": str(self.pipeline.device)
        }
        return result_img, actual_seed, proc_time, metadata


class QwenProvider(InferenceProvider):
    """
    Provider for Qwen-Image-Edit-2511 model.
    Second modular model option according to architecture design.
    """

    DEFAULT_MODEL_ID = "Qwen/Qwen-Image-Edit-2511"

    def __init__(self, model_id: Optional[str] = None):
        super().__init__(model_id or self.DEFAULT_MODEL_ID)

    def load(self) -> bool:
        if self.is_loaded and self.pipeline is not None:
            return True

        if os.environ.get("MOCK_INFERENCE") == "1" or torch is None or DiffusionPipeline is None or not torch.cuda.is_available():
            logger.info("CUDA not detected or MOCK_INFERENCE enabled. Using lightweight simulation mode.")
            self.is_loaded = True
            return True

        logger.info(f"Loading Qwen-Image-Edit-2511 from {self.model_id}...")
        start_t = time.time()
        cache_dir = ModelManager.get_cache_dir()
        dtype = ModelManager.get_dtype()
        device = "cuda"

        try:
            self.pipeline = DiffusionPipeline.from_pretrained(
                self.model_id,
                torch_dtype=dtype,
                cache_dir=cache_dir,
                trust_remote_code=True
            )
            self.pipeline.to(device)
            self.is_loaded = True
            load_time = round(time.time() - start_t, 2)
            logger.info(f"Qwen-Image-Edit-2511 loaded in {load_time}s.")
            return True
        except Exception as e:
            logger.error(f"Failed to load Qwen model: {e}")
            self.unload()
            raise e

    def unload(self):
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
        self.is_loaded = False
        ModelManager.clear_vram()
        logger.info("Qwen-Image-Edit-2511 unloaded.")

    def edit(
        self,
        image: Image.Image,
        prompt: str,
        seed: Optional[int] = None,
        quality: str = "high",
        identity_strength: str = "high",
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None
    ) -> Tuple[Image.Image, int, float, Dict[str, Any]]:
        if not self.is_loaded:
            self.load()

        actual_seed = seed if (seed is not None and seed >= 0) else random.randint(100000, 999999999)
        start_t = time.time()

        max_dim = 1536 if quality == "high" else 1024
        inference_steps = steps or (30 if quality == "high" else 20)
        guidance = guidance_scale or (7.0 if identity_strength == "high" else 5.5)

        processed_image, _ = resize_image_aspect_ratio(image, max_dim=max_dim, multiple_of=64)

        if torch is None or self.pipeline is None:
            time.sleep(1.0)
            result_img = processed_image.copy()
            proc_time = round(time.time() - start_t, 2)
            return result_img, actual_seed, proc_time, {
                "engine": "mock_qwen",
                "steps": inference_steps,
                "guidance_scale": guidance
            }

        generator = torch.Generator(device=self.pipeline.device).manual_seed(actual_seed)

        with torch.inference_mode():
            output = self.pipeline(
                prompt=prompt,
                image=processed_image,
                num_inference_steps=inference_steps,
                guidance_scale=guidance,
                generator=generator
            )
            result_img = output.images[0]

        proc_time = round(time.time() - start_t, 2)
        metadata = {
            "model": self.model_id,
            "steps": inference_steps,
            "guidance_scale": guidance,
            "resolution": f"{result_img.width}x{result_img.height}"
        }
        return result_img, actual_seed, proc_time, metadata


class ProviderRegistry:
    """Manages active providers and seamless model switching."""

    def __init__(self):
        self.providers: Dict[str, InferenceProvider] = {
            "FireRed-Image-Edit-1.1": FireRedProvider(),
            "Qwen-Image-Edit-2511": QwenProvider()
        }
        self.active_provider_name: str = "FireRed-Image-Edit-1.1"

    def get_provider(self, name: Optional[str] = None) -> InferenceProvider:
        target_name = name or self.active_provider_name
        if target_name not in self.providers:
            # Fallback to default
            target_name = "FireRed-Image-Edit-1.1"
        return self.providers[target_name]

    def switch_model(self, name: str) -> bool:
        if name not in self.providers:
            raise ValueError(f"Unknown model provider: {name}")

        if name == self.active_provider_name and self.providers[name].is_loaded:
            return True

        # Unload current provider to free VRAM
        current = self.providers.get(self.active_provider_name)
        if current and current.is_loaded:
            current.unload()

        self.active_provider_name = name
        new_provider = self.providers[name]
        return new_provider.load()


# Global instance
registry = ProviderRegistry()
