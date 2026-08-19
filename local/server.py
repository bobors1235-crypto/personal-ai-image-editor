"""
Local FastAPI Server and UI Host for Personal AI Image Editor.
Runs locally on Windows (e.g. http://127.0.0.1:7860).
Orchestrates prompt enhancement, RunPod/Mock providers, local /history/ storage,
live cost calculation, and auto-stop monitoring.
"""

import os
import sys
import json
import time
import uuid
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.schemas import EditRequest, EditResponse, HealthResponse, PromptAnalysis, HistoryItem, ConfigSchema
from local.prompt_engine import PromptEngine
from local.providers import RunPodClientProvider, RunPodServerlessClientProvider, MockClientProvider, RunPodAPIController
from runpod.image_utils import base64_to_pil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("local_server")

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_DIR = Path(__file__).resolve().parent
HISTORY_DIR = ROOT_DIR / "history"
CONFIG_PATH = LOCAL_DIR / "config.json"

# Ensure history directory exists
os.makedirs(HISTORY_DIR, exist_ok=True)

app = FastAPI(
    title="Personal AI Image Editor - Local Server",
    version="1.0.0",
    description="Local host for AI Image Editor with Prompt Engine & RunPod Connector"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# App State
class AppState:
    def __init__(self):
        self.config: ConfigSchema = self.load_config()
        self.provider = self.init_provider()
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.is_connected = False
        self.total_edits_count = 0

    def load_config(self) -> ConfigSchema:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return ConfigSchema(**data)
            except Exception as e:
                logger.error(f"Error loading config.json: {e}")
        return ConfigSchema()

    def save_config(self, new_cfg: ConfigSchema):
        self.config = new_cfg
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_cfg.model_dump_json(indent=2))
        self.provider = self.init_provider()

    def init_provider(self):
        if self.config.provider_type == "mock":
            logger.info("Initializing Local Mock Provider.")
            return MockClientProvider()
        elif self.config.provider_type == "serverless":
            logger.info(f"Initializing RunPod Serverless Provider for Endpoint: {self.config.runpod_serverless_endpoint_id}")
            return RunPodServerlessClientProvider(
                endpoint_id=self.config.runpod_serverless_endpoint_id or "",
                api_key=self.config.runpod_api_key or ""
            )
        else:
            logger.info(f"Initializing RunPod Pod Provider connected to: {self.config.runpod_endpoint_url}")
            return RunPodClientProvider(
                endpoint_url=self.config.runpod_endpoint_url,
                api_key=self.config.runpod_api_key
            )

    def touch_activity(self):
        self.last_activity_time = time.time()


state = AppState()


# Background task: Auto-stop monitoring
async def auto_stop_monitor():
    while True:
        await asyncio.sleep(60) # Check every 60 seconds
        if state.config.auto_stop_enabled and state.config.provider_type == "runpod":
            idle_minutes = (time.time() - state.last_activity_time) / 60.0
            if idle_minutes >= state.config.auto_stop_minutes:
                if state.config.runpod_api_key and state.config.runpod_pod_id:
                    logger.warning(f"Auto-stop triggered after {idle_minutes:.1f} minutes of inactivity. Stopping pod...")
                    success, msg = RunPodAPIController.stop_pod(
                        state.config.runpod_api_key,
                        state.config.runpod_pod_id
                    )
                    logger.info(f"Auto-stop result: {msg}")
                else:
                    logger.info(f"Idle time exceeded {state.config.auto_stop_minutes}m, but RunPod API Key/Pod ID not configured.")


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(auto_stop_monitor())
    logger.info("Local server started. Open http://127.0.0.1:7860 in your browser.")


# --- API Routes ---

@app.get("/api/health")
async def get_health():
    """Check health, connection status, uptime, and live estimated cost."""
    health_resp = state.provider.health()
    state.is_connected = (health_resp.status == "ready")
    
    uptime_seconds = time.time() - state.session_start_time
    hours = uptime_seconds / 3600.0
    estimated_cost = round(hours * state.config.gpu_hourly_cost, 3)
    idle_minutes = round((time.time() - state.last_activity_time) / 60.0, 1)

    return {
        "health": health_resp.model_dump(),
        "provider_type": state.config.provider_type,
        "session_uptime_seconds": int(uptime_seconds),
        "session_uptime_formatted": time.strftime("%H:%M:%S", time.gmtime(uptime_seconds)),
        "estimated_cost_usd": estimated_cost,
        "hourly_rate_usd": state.config.gpu_hourly_cost,
        "idle_minutes": idle_minutes,
        "total_edits": state.total_edits_count
    }


@app.post("/api/prompt/analyze", response_model=PromptAnalysis)
async def analyze_prompt(payload: dict):
    """Analyze and enhance prompt locally on CPU with zero GPU cost."""
    prompt = payload.get("prompt", "")
    identity_strength = payload.get("identity_strength", state.config.default_identity_strength)
    quality = payload.get("quality", state.config.default_quality)

    analysis = PromptEngine.enhance_edit_prompt(
        prompt=prompt,
        identity_strength=identity_strength,
        quality=quality
    )
    return analysis


@app.post("/api/edit")
async def execute_edit(req: EditRequest):
    """Execute AI Image Edit with local prompt enhancement and local history logging."""
    state.touch_activity()
    start_t = time.time()

    # 1. Local Prompt Enhancement
    analysis = PromptEngine.enhance_edit_prompt(
        prompt=req.prompt,
        identity_strength=req.identity_strength,
        quality=req.quality
    )
    # Pass enhanced prompt to provider
    req.enhanced_prompt = analysis.enhanced_prompt

    # 2. Call Inference Provider (RunPod or Mock)
    edit_resp = state.provider.edit(req)
    state.touch_activity()

    if not edit_resp.success:
        return JSONResponse(status_code=500, content=edit_resp.model_dump())

    # 3. Save to Local History (/history/)
    item_id = str(uuid.uuid4())[:8]
    item_dir = HISTORY_DIR / item_id
    os.makedirs(item_dir, exist_ok=True)

    # Save original image
    orig_pil = base64_to_pil(req.image_base64)
    orig_img_path = item_dir / "original.png"
    orig_pil.save(orig_img_path)

    # Save result image
    res_pil = base64_to_pil(edit_resp.image_base64)
    res_img_path = item_dir / "result.png"
    res_pil.save(res_img_path)

    # Save metadata JSON
    hist_item = HistoryItem(
        id=item_id,
        timestamp=time.time(),
        date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        original_image_path=f"/history_media/{item_id}/original.png",
        result_image_path=f"/history_media/{item_id}/result.png",
        user_prompt=req.prompt,
        enhanced_prompt=analysis.enhanced_prompt,
        categories=analysis.categories,
        model_name=req.model_name,
        seed=edit_resp.seed,
        quality=req.quality,
        identity_strength=req.identity_strength,
        processing_time=edit_resp.processing_time,
        cost_estimate_usd=round((edit_resp.processing_time / 3600.0) * state.config.gpu_hourly_cost, 4)
    )

    with open(item_dir / "metadata.json", "w", encoding="utf-8") as f:
        f.write(hist_item.model_dump_json(indent=2))

    state.total_edits_count += 1

    return {
        "edit_response": edit_resp.model_dump(),
        "prompt_analysis": analysis.model_dump(),
        "history_item": hist_item.model_dump()
    }


@app.get("/api/history", response_model=List[HistoryItem])
async def get_history():
    """Retrieve all local history items sorted chronologically (newest first)."""
    items = []
    if HISTORY_DIR.exists():
        for sub_dir in sorted(HISTORY_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            meta_file = sub_dir / "metadata.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        items.append(HistoryItem(**data))
                except Exception as e:
                    logger.warning(f"Failed to read history item {sub_dir.name}: {e}")
    return items


@app.delete("/api/history/{item_id}")
async def delete_history_item(item_id: str):
    """Delete a history entry and its saved images."""
    target_dir = HISTORY_DIR / item_id
    if target_dir.exists():
        import shutil
        shutil.rmtree(target_dir, ignore_errors=True)
        return {"success": True, "message": f"Item {item_id} deleted."}
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/api/config")
async def get_config():
    """Retrieve current application configuration."""
    return state.config.model_dump()


@app.post("/api/config")
async def update_config(new_cfg: ConfigSchema):
    """Update application configuration."""
    state.save_config(new_cfg)
    return {"success": True, "config": state.config.model_dump()}


@app.post("/api/pod/start")
async def start_runpod():
    """Send Start command to RunPod pod via RunPod API."""
    if not state.config.runpod_api_key or not state.config.runpod_pod_id:
        raise HTTPException(status_code=400, detail="RunPod API Key and Pod ID must be configured in Settings.")
    
    success, msg = RunPodAPIController.start_pod(state.config.runpod_api_key, state.config.runpod_pod_id)
    state.touch_activity()
    return {"success": success, "message": msg}


@app.post("/api/pod/stop")
async def stop_runpod():
    """Send Stop command to RunPod pod via RunPod API."""
    if not state.config.runpod_api_key or not state.config.runpod_pod_id:
        raise HTTPException(status_code=400, detail="RunPod API Key and Pod ID must be configured in Settings.")
    
    success, msg = RunPodAPIController.stop_pod(state.config.runpod_api_key, state.config.runpod_pod_id)
    return {"success": success, "message": msg}


@app.post("/api/session/reset-timer")
async def reset_session_timer():
    """Reset the session uptime timer and cost counter."""
    state.session_start_time = time.time()
    state.last_activity_time = time.time()
    return {"success": True, "message": "Session timer reset."}


# Serve local history image files statically
app.mount("/history_media", StaticFiles(directory=str(HISTORY_DIR)), name="history_media")

# Serve UI Static Assets (css, js)
app.mount("/css", StaticFiles(directory=str(LOCAL_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(LOCAL_DIR / "js")), name="js")

# Serve index.html at root
@app.get("/")
async def serve_index():
    return FileResponse(LOCAL_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("local.server:app", host="127.0.0.1", port=7860, reload=False)
