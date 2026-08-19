"""
RunPod Serverless Worker Handler for FireRed-Image-Edit-1.1 & Qwen-Image-Edit-2511.
Processes on-demand scale-to-zero serverless requests.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add project root and runpod directory to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("serverless_worker")

# Import runpod SDK package
try:
    import runpod
except ImportError:
    runpod = None
    logger.warning("runpod python package is not installed. Install with 'pip install runpod'.")


def serverless_handler(job: dict) -> dict:
    """
    Standard RunPod Serverless handler function.
    Job input payload schema matches EditRequest.
    """
    # Lazy imports to ensure immediate worker registration
    from shared.schemas import EditRequest
    try:
        from image_utils import base64_to_pil, pil_to_base64
        from inference import registry
    except ImportError:
        from runpod.image_utils import base64_to_pil, pil_to_base64
        from runpod.inference import registry

    job_input = job.get("input", {})
    if not job_input:
        return {"error": "Missing input dictionary in job payload."}

    start_time = time.time()
    try:
        req = EditRequest(**job_input)

        # 1. Parse Image
        pil_image = base64_to_pil(req.image_base64)
        effective_prompt = req.enhanced_prompt if req.enhanced_prompt else req.prompt

        # 2. Select Provider & Ensure Loaded
        provider = registry.get_provider(req.model_name)
        if not provider.is_loaded:
            logger.info(f"Loading {req.model_name} into VRAM for job...")
            provider.load()

        # 3. Perform Inference
        result_pil, actual_seed, proc_time, meta = provider.edit(
            image=pil_image,
            prompt=effective_prompt,
            seed=req.seed,
            quality=req.quality,
            identity_strength=req.identity_strength,
            steps=req.steps,
            guidance_scale=req.guidance_scale
        )

        # 4. Convert Result to Base64
        result_b64 = pil_to_base64(result_pil, format="PNG")

        return {
            "success": True,
            "image_base64": result_b64,
            "seed": actual_seed,
            "processing_time": proc_time,
            "model_name": req.model_name,
            "enhanced_prompt": effective_prompt,
            "metadata": meta
        }

    except Exception as e:
        logger.error(f"Error in serverless handler: {e}", exc_info=True)
        return {
            "success": False,
            "image_base64": None,
            "seed": job_input.get("seed", 0),
            "processing_time": round(time.time() - start_time, 2),
            "model_name": job_input.get("model_name", "FireRed-Image-Edit-1.1"),
            "enhanced_prompt": job_input.get("enhanced_prompt") or job_input.get("prompt", ""),
            "error": str(e)
        }


if __name__ == "__main__":
    if runpod is not None:
        logger.info("Starting RunPod Serverless worker listener loop...")
        runpod.serverless.start({"handler": serverless_handler})
    else:
        logger.error("RunPod SDK not available. Run: pip install runpod")
