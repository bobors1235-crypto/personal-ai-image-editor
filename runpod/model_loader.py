"""
Model Loader and Memory Manager for RunPod GPU Server.
Handles model cache in /workspace, CUDA VRAM tracking, and warm loading.
"""

import os
import gc
import logging
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

    @classmethod
    def get_cache_dir(cls) -> str:
        """Return persistent /workspace cache or /runpod-volume if available, otherwise local cache."""
        if os.path.exists("/workspace") and os.path.isdir("/workspace"):
            os.makedirs(cls.WORKSPACE_CACHE, exist_ok=True)
            return cls.WORKSPACE_CACHE
        if os.path.exists("/runpod-volume") and os.path.isdir("/runpod-volume"):
            path = "/runpod-volume/cache/models"
            os.makedirs(path, exist_ok=True)
            return path
        cache_dir = os.environ.get("HF_HOME") or cls.LOCAL_CACHE
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

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
