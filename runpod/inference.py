"""
Inference Provider Layer for RunPod Image Editing.
Features modular providers for FireRed-Image-Edit-1.1 and Qwen-Image-Edit-2511.
Optimized for 48GB GPU VRAM in native bfloat16 with low CPU memory footprint.
"""

import os
import gc
import time
import random
import logging
import threading
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


def _env_flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def _load_qwen_edit_pipeline(model_id: str, dtype: Any, cache_dir: str):
    """Load the model's declared pipeline exactly once, with one dtype argument.

    FireRed's model_index.json declares QwenImageEditPlusPipeline.  Falling back
    after an arbitrary load error caused duplicate downloads and masked storage
    errors, so a real failure is surfaced to the caller instead.
    """
    try:
        from diffusers import QwenImageEditPlusPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Installed diffusers does not provide QwenImageEditPlusPipeline. "
            "Build the supplied Dockerfile, which pins a compatible version."
        ) from exc

    return QwenImageEditPlusPipeline.from_pretrained(
        model_id,
        dtype=dtype,
        cache_dir=cache_dir,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )


class InferenceProvider(ABC):
    """Abstract interface for modular image editing models."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.pipeline = None
        self.is_loaded = False
        self._load_lock = threading.RLock()

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
        with self._load_lock:
            if self.is_loaded and self.pipeline is not None:
                return True

            if os.environ.get("MOCK_INFERENCE") == "1" or torch is None or DiffusionPipeline is None or not torch.cuda.is_available():
                logger.info("CUDA not detected or MOCK_INFERENCE enabled. Using lightweight simulation mode.")
                self.is_loaded = True
                return True

            logger.info(f"Loading FireRed-Image-Edit-1.1 from {self.model_id} in native bfloat16...")
            start_t = time.time()
            cache_dir = ModelManager.get_cache_dir()
            dtype = ModelManager.get_dtype()
            cpu_offload = _env_flag("RUNPOD_CPU_OFFLOAD")

            try:
                if not cpu_offload:
                    ModelManager.require_gpu_memory()
                pipe = _load_qwen_edit_pipeline(self.model_id, dtype, cache_dir)

                if cpu_offload:
                    logger.warning("CPU offload enabled. This requires at least 64GB endpoint RAM and is slower.")
                    pipe.enable_model_cpu_offload()
                    device = "cpu-offload"
                else:
                    pipe.to("cuda")
                    device = "cuda"

                if hasattr(pipe, "enable_attention_slicing"):
                    pipe.enable_attention_slicing(slice_size="auto")
                if hasattr(pipe, "enable_vae_tiling"):
                    pipe.enable_vae_tiling()
                if hasattr(pipe, "enable_vae_slicing"):
                    pipe.enable_vae_slicing()

                self.pipeline = pipe
                self.is_loaded = True
                load_time = round(time.time() - start_t, 2)
                logger.info(f"FireRed-Image-Edit-1.1 loaded on {device} in {load_time}s.")
                return True
            except Exception as e:
                logger.error(f"Failed to load FireRed model: {e}")
                self.unload()
                raise

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

        # Step count and resolution tuning (1024 native for optimal fidelity and memory)
        max_dim = 1024 if quality == "high" else 768
        inference_steps = steps or (30 if quality == "high" else 20)
        guidance = guidance_scale or (7.0 if identity_strength == "high" else 5.5)

        # Preprocess input image dimensions
        processed_image, orig_size = resize_image_aspect_ratio(image, max_dim=max_dim, multiple_of=64)

        if torch is None or self.pipeline is None:
            time.sleep(1.0)
            result_img = processed_image.copy()
            proc_time = round(time.time() - start_t, 2)
            return result_img, actual_seed, proc_time, {
                "engine": "mock_fire_red",
                "steps": inference_steps,
                "guidance_scale": guidance,
                "resolution": f"{processed_image.width}x{processed_image.height}"
            }

        dev_target = "cuda" if torch.cuda.is_available() else "cpu"
        generator = torch.Generator(device=dev_target).manual_seed(actual_seed)

        # Free any lingering cache before forward pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

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

        # Clean cache after forward pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        proc_time = round(time.time() - start_t, 2)
        metadata = {
            "model": self.model_id,
            "steps": inference_steps,
            "guidance_scale": guidance,
            "resolution": f"{result_img.width}x{result_img.height}",
            "device": dev_target
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
        with self._load_lock:
            if self.is_loaded and self.pipeline is not None:
                return True

            if os.environ.get("MOCK_INFERENCE") == "1" or torch is None or DiffusionPipeline is None or not torch.cuda.is_available():
                logger.info("CUDA not detected or MOCK_INFERENCE enabled. Using lightweight simulation mode.")
                self.is_loaded = True
                return True

            logger.info(f"Loading Qwen-Image-Edit-2511 from {self.model_id} in native bfloat16...")
            start_t = time.time()
            cache_dir = ModelManager.get_cache_dir()
            dtype = ModelManager.get_dtype()
            cpu_offload = _env_flag("RUNPOD_CPU_OFFLOAD")

            try:
                if not cpu_offload:
                    ModelManager.require_gpu_memory()
                pipe = _load_qwen_edit_pipeline(self.model_id, dtype, cache_dir)

                if cpu_offload:
                    logger.warning("CPU offload enabled. This requires at least 64GB endpoint RAM and is slower.")
                    pipe.enable_model_cpu_offload()
                else:
                    pipe.to("cuda")

                if hasattr(pipe, "enable_attention_slicing"):
                    pipe.enable_attention_slicing(slice_size="auto")
                if hasattr(pipe, "enable_vae_tiling"):
                    pipe.enable_vae_tiling()
                if hasattr(pipe, "enable_vae_slicing"):
                    pipe.enable_vae_slicing()

                self.pipeline = pipe
                self.is_loaded = True
                load_time = round(time.time() - start_t, 2)
                logger.info(f"Qwen-Image-Edit-2511 loaded in {load_time}s.")
                return True
            except Exception as e:
                logger.error(f"Failed to load Qwen model: {e}")
                self.unload()
                raise

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

        max_dim = 1024 if quality == "high" else 768
        inference_steps = steps or (35 if quality == "high" else 24)
        guidance = guidance_scale or (7.5 if identity_strength == "high" else 6.0)

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

        dev_target = "cuda" if torch.cuda.is_available() else "cpu"
        generator = torch.Generator(device=dev_target).manual_seed(actual_seed)

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

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

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        proc_time = round(time.time() - start_t, 2)
        metadata = {
            "model": self.model_id,
            "steps": inference_steps,
            "guidance_scale": guidance,
            "resolution": f"{result_img.width}x{result_img.height}",
            "device": dev_target
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
