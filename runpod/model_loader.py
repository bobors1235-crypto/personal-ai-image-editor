"""
Model Loader and Memory Manager for RunPod GPU Server.
Handles model cache in /workspace, CUDA VRAM tracking, and warm loading.
"""

import os
import gc
import logging
import shutil
from typing import Dict, Any, Optional

try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger("model_loader")
logging.basicConfig(level=logging.INFO)


class ModelManager:
    """Manages GPU resources and model weights caching."""

    WORKSPACE_CACHE = "/workspace/models"
    LOCAL_CACHE = os.path.expanduser("~/.cache/image_editor_models")
    MIN_FREE_DISK_GB = 60

    @classmethod
    def get_cache_dir(cls) -> str:
        """Return one explicit cache directory and fail before a partial model download."""
        configured = os.environ.get("RUNPOD_MODEL_CACHE")
        if configured:
            cache_dir = configured
        elif os.path.isdir("/runpod-volume"):
            cache_dir = "/runpod-volume/cache/models"
        elif os.path.isdir("/workspace"):
            cache_dir = cls.WORKSPACE_CACHE
        else:
            cache_dir = os.environ.get("HF_HOME") or cls.LOCAL_CACHE
        os.makedirs(cache_dir, exist_ok=True)
        required_gb = int(os.environ.get("RUNPOD_MIN_FREE_DISK_GB", cls.MIN_FREE_DISK_GB))
        free_gb = shutil.disk_usage(cache_dir).free / (1024 ** 3)
        if free_gb < required_gb:
            raise RuntimeError(
                f"Insufficient disk for model cache at {cache_dir}: {free_gb:.1f}GB free; "
                f"at least {required_gb}GB is required. Increase the Serverless container disk "
                "or set RUNPOD_MODEL_CACHE to a larger mounted volume."
            )
        logger.info("Using model cache %s (%.1fGB free).", cache_dir, free_gb)
        return cache_dir

    @classmethod
    def require_gpu_memory(cls, minimum_gb: int = 70) -> None:
        """Reject an unsafe full-GPU load before the worker is killed by CUDA OOM."""
        if torch is None or not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required for RunPod inference.")
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if total_gb < minimum_gb:
            raise RuntimeError(
                f"This model needs a GPU with at least {minimum_gb}GB VRAM for reliable full-GPU inference; "
                f"this worker has {total_gb:.1f}GB. Configure the Serverless endpoint with an 80GB GPU "
                "(A100 80GB or H100), max workers = 1, and max concurrency = 1. "
                "Do not use CPU offload unless the endpoint also has at least 64GB RAM allocated."
            )

    @classmethod
    def get_gpu_info(cls) -> Dict[str, Any]:
        """Fetch real-time GPU and VRAM statistics."""
        if torch is None or not torch.cuda.is_available():
            return {
                "gpu_available": False,
                "gpu_name": "CPU (No CUDA)",
                "vram_used_gb": 0.0,
                "vram_total_gb": 0.0
            }

        try:
            device_id = 0
            device_name = torch.cuda.get_device_name(device_id)
            total_memory = torch.cuda.get_device_properties(device_id).total_memory / (1024 ** 3)
            allocated_memory = torch.cuda.memory_allocated(device_id) / (1024 ** 3)
            reserved_memory = torch.cuda.memory_reserved(device_id) / (1024 ** 3)
            
            return {
                "gpu_available": True,
                "gpu_name": device_name,
                "vram_used_gb": round(reserved_memory, 2),
                "vram_allocated_gb": round(allocated_memory, 2),
                "vram_total_gb": round(total_memory, 2)
            }
        except Exception as e:
            logger.warning(f"Error querying GPU: {e}")
            return {
                "gpu_available": True,
                "gpu_name": "CUDA Device",
                "vram_used_gb": 0.0,
                "vram_total_gb": 0.0
            }

    @classmethod
    def get_dtype(cls) -> Any:
        """Select optimal torch data type (bfloat16 preferred on Ampere+ GPUs)."""
        if torch is None or not torch.cuda.is_available():
            return torch.float32 if torch else None
            
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16

    @classmethod
    def clear_vram(cls):
        """Free cached VRAM and collect garbage."""
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            logger.info("Cleared PyTorch CUDA VRAM cache.")
