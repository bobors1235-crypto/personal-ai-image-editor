"""
RunPod FastAPI Inference Server.
Exposes /edit, /health, /model/load endpoints for remote image editing operations.
"""

import time
import logging
import sys
from pathlib import Path

# Add project root to sys.path to allow shared schemas import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from shared.schemas import EditRequest, EditResponse, HealthResponse

try:
    from image_utils import base64_to_pil, pil_to_base64
    from model_loader import ModelManager
    from inference import registry
except ImportError:
    from runpod.image_utils import base64_to_pil, pil_to_base64
    from runpod.model_loader import ModelManager
    from runpod.inference import registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("runpod_api")

app = FastAPI(
    title="Personal AI Image Editor - RunPod Inference Server",
    version="1.0.0",
    description="GPU Inference backend for instruction-based image editing (FireRed 1.1 / Qwen 2511)"
)

# Enable CORS for local web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing RunPod Inference Server...")
    gpu_info = ModelManager.get_gpu_info()
    logger.info(f"GPU Status: {gpu_info}")
    # Warm up default model in background or on first request
    try:
        provider = registry.get_provider("FireRed-Image-Edit-1.1")
        logger.info(f"Default model ready: {provider.model_id}")
    except Exception as e:
        logger.warning(f"Initial model preload deferred: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health status check and live VRAM metrics."""
    gpu_info = ModelManager.get_gpu_info()
    return HealthResponse(
        status="ready",
        gpu_name=gpu_info.get("gpu_name"),
        vram_used_gb=gpu_info.get("vram_used_gb"),
        vram_total_gb=gpu_info.get("vram_total_gb"),
        active_model=registry.active_model_name,
        server_time=time.time(),
        version="1.0.0"
    )


@app.get("/models")
async def list_models():
    """List available editing models."""
    return {
        "active_model": registry.active_model_name,
        "available_models": registry.list_models()["available_models"]
    }


@app.post("/model/load")
async def load_model(payload: dict):
    """Explicitly switch or reload a specific model provider into VRAM."""
    model_name = payload.get("model_name", "FireRed-Image-Edit-1.1")
    try:
        success = registry.switch_model(model_name)
        return {
            "success": success,
            "active_model": registry.active_model_name,
            "message": f"Model {model_name} loaded successfully."
        }
    except Exception as e:
        logger.error(f"Error switching model to {model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/edit", response_model=EditResponse)
async def edit_image(req: EditRequest):
    """
    Execute AI Image Edit.
    Receives base64 image and enhanced prompt, returns modified image.
    """
    start_time = time.time()
    try:
        # 1. Parse Image
        pil_image = base64_to_pil(req.image_base64)

        # 2. Select Prompt (use enhanced_prompt if provided, else prompt)
        effective_prompt = req.enhanced_prompt if req.enhanced_prompt else req.prompt

        # 3. Select Provider
        provider = registry.get_provider(req.model_name)

        # 4. Perform Inference
        result_pil, actual_seed, proc_time, meta = provider.edit(
            image=pil_image,
            prompt=effective_prompt,
            seed=req.seed,
            quality=req.quality,
            identity_strength=req.identity_strength,
            steps=req.steps,
            guidance_scale=req.guidance_scale
        )

        # 5. Convert Result to Base64
        result_b64 = pil_to_base64(result_pil, format="PNG")

        # Cleanup memory
        del pil_image
        del result_pil

        return EditResponse(
            success=True,
            image_base64=result_b64,
            seed=actual_seed,
            processing_time=proc_time,
            model_name=req.model_name,
            enhanced_prompt=effective_prompt,
            metadata=meta
        )

    except Exception as e:
        logger.error(f"Error processing edit request: {e}", exc_info=True)
        total_time = round(time.time() - start_time, 2)
        return EditResponse(
            success=False,
            image_base64=None,
            seed=req.seed or 0,
            processing_time=total_time,
            model_name=req.model_name,
            enhanced_prompt=req.enhanced_prompt or req.prompt,
            error=str(e),
            metadata={"error_detail": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("runpod.api:app", host="0.0.0.0", port=8000, reload=False)
