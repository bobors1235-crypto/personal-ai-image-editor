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
    """Abstract interface for modular image editing models."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.pipeline = None
        self.is_loaded = False

    @abstractmethod
    def load(self) -> bool:
        """Load model into GPU VRAM."""
        pass

    @abstractmethod
    def unload(self):
        """Unload model and free VRAM."""
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
        Execute image editing inference.
        Returns: (result_image, seed, processing_time, metadata)
        """
        pass


class FireRedProvider(InferenceProvider):
    """
    Provider for FireRed-Image-Edit-1.1 model.
    Default high-fidelity editing model preserving facial identity and context.
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
            # Try QwenImageEditPlusPipeline or fallback to DiffusionPipeline
            pipe = None
            try:
                from diffusers import QwenImageEditPlusPipeline
                pipe = QwenImageEditPlusPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=dtype,
                    cache_dir=cache_dir,
                    trust_remote_code=True
                )
            except Exception as pe:
                logger.info(f"Direct QwenImageEditPlusPipeline load notice: {pe}. Falling back to DiffusionPipeline...")
                pipe = DiffusionPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=dtype,
                    cache_dir=cache_dir,
                    trust_remote_code=True
                )

            self.pipeline = pipe
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
            # Robust inference call with parameter compatibility
            try:
                output = self.pipeline(
                    prompt=prompt,
                    image=processed_image,
                    num_inference_steps=inference_steps,
                    guidance_scale=guidance,
                    generator=generator
                )
            except TypeError:
                output = self.pipeline(
                    prompt=prompt,
                    image=[processed_image],
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
            pipe = None
            try:
                from diffusers import QwenImageEditPlusPipeline
                pipe = QwenImageEditPlusPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=dtype,
                    cache_dir=cache_dir,
                    trust_remote_code=True
                )
            except Exception:
                pipe = DiffusionPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=dtype,
                    cache_dir=cache_dir,
                    trust_remote_code=True
                )

            self.pipeline = pipe
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
        inference_steps = steps or (40 if quality == "high" else 28)
        guidance = guidance_scale or (8.0 if identity_strength == "high" else 6.5)

        processed_image, orig_size = resize_image_aspect_ratio(image, max_dim=max_dim, multiple_of=64)

        if torch is None or self.pipeline is None:
            time.sleep(1.0)
            result_img = processed_image.copy()
            proc_time = round(time.time() - start_t, 2)
            return result_img, actual_seed, proc_time, {
                "engine": "mock_qwen",
                "steps": inference_steps,
                "guidance_scale": guidance,
                "resolution": f"{processed_image.width}x{processed_image.height}"
            }

        generator = torch.Generator(device=self.pipeline.device).manual_seed(actual_seed)

        with torch.inference_mode():
            try:
                output = self.pipeline(
                    prompt=prompt,
                    image=processed_image,
                    num_inference_steps=inference_steps,
                    guidance_scale=guidance,
                    generator=generator
                )
            except TypeError:
                output = self.pipeline(
                    prompt=prompt,
                    image=[processed_image],
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


class ModelRegistry:
    """Registry managing active model lifecycle and multi-model switching."""

    def __init__(self):
        self._providers: Dict[str, InferenceProvider] = {
            "FireRed-Image-Edit-1.1": FireRedProvider(),
            "Qwen-Image-Edit-2511": QwenProvider()
        }
        self.active_model_name: str = "FireRed-Image-Edit-1.1"

    def get_provider(self, model_name: str) -> InferenceProvider:
        if model_name not in self._providers:
            raise ValueError(f"Model '{model_name}' is not registered. Available: {list(self._providers.keys())}")
        return self._providers[model_name]

    def switch_active_model(self, target_model_name: str) -> bool:
        if target_model_name not in self._providers:
            raise ValueError(f"Unknown model: {target_model_name}")

        if target_model_name == self.active_model_name:
            provider = self._providers[target_model_name]
            if not provider.is_loaded:
                provider.load()
            return True

        logger.info(f"Switching active model from {self.active_model_name} to {target_model_name}...")
        current_provider = self._providers[self.active_model_name]
        current_provider.unload()

        new_provider = self._providers[target_model_name]
        new_provider.load()
        self.active_model_name = target_model_name
        logger.info(f"Active model successfully switched to: {target_model_name}")
        return True

    def list_models(self) -> Dict[str, Any]:
        return {
            "active_model": self.active_model_name,
            "available_models": list(self._providers.keys()),
            "models_status": {
                name: {
                    "loaded": provider.is_loaded,
                    "model_id": provider.model_id
                }
                for name, provider in self._providers.items()
            }
        }


registry = ModelRegistry()
