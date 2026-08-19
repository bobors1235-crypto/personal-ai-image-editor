"""
Shared Pydantic schemas for Personal AI Image Editor.
Used across Local and RunPod components for consistent data contracts.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time


class EditRequest(BaseModel):
    """Payload sent from Local server to RunPod inference API."""
    image_base64: str = Field(..., description="Base64 encoded original input image")
    prompt: str = Field(..., description="Original user prompt or enhanced prompt")
    enhanced_prompt: Optional[str] = Field(None, description="Pre-computed enhanced prompt if provided by local engine")
    model_name: str = Field(default="FireRed-Image-Edit-1.1", description="Model identifier to use for inference")
    seed: Optional[int] = Field(default=None, description="Random seed (None for random)")
    quality: str = Field(default="high", description="Output quality: high or normal")
    identity_strength: str = Field(default="high", description="Identity preservation level: high, normal, low")
    steps: Optional[int] = Field(default=None, description="Inference steps override")
    guidance_scale: Optional[float] = Field(default=None, description="Guidance scale override")


class EditResponse(BaseModel):
    """Response returned from RunPod inference API after processing."""
    success: bool = True
    image_base64: Optional[str] = Field(None, description="Base64 encoded result image")
    seed: int = Field(..., description="Actual seed used for generation")
    processing_time: float = Field(..., description="Inference execution time in seconds")
    model_name: str = Field(..., description="Model used for this edit")
    enhanced_prompt: str = Field(..., description="The exact prompt string executed by the model")
    error: Optional[str] = Field(None, description="Error message if success is False")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional debug/performance metrics")


class HealthResponse(BaseModel):
    """RunPod health and GPU status response."""
    status: str = Field(default="ready", description="Status: ready, loading, error, or idle")
    gpu_name: Optional[str] = Field(None, description="GPU model name e.g. NVIDIA RTX A6000")
    vram_used_gb: Optional[float] = Field(None, description="Used VRAM in GB")
    vram_total_gb: Optional[float] = Field(None, description="Total VRAM in GB")
    active_model: Optional[str] = Field(None, description="Currently loaded model in memory")
    server_time: float = Field(default_factory=time.time)
    version: str = "1.0.0"


class PromptAnalysis(BaseModel):
    """Result of local prompt parsing and categorization."""
    original_prompt: str
    language: str  # 'ar' or 'en'
    categories: List[str]  # e.g. ['OUTFIT', 'BACKGROUND']
    change_targets: List[str]  # what user wants to change
    preserve_targets: List[str]  # what should be preserved
    enhanced_prompt: str
    structured_sections: Dict[str, str] = Field(default_factory=dict)


class HistoryItem(BaseModel):
    """Metadata recorded for each edited image saved locally in /history/."""
    id: str
    timestamp: float
    date_str: str
    original_image_path: str
    result_image_path: str
    user_prompt: str
    enhanced_prompt: str
    categories: List[str]
    model_name: str
    seed: int
    quality: str
    identity_strength: str
    processing_time: float
    cost_estimate_usd: float = 0.0


class ConfigSchema(BaseModel):
    """Local application configuration."""
    runpod_endpoint_url: str = "http://127.0.0.1:8000"
    runpod_api_key: Optional[str] = None
    runpod_pod_id: Optional[str] = None
    gpu_hourly_cost: float = 0.33
    auto_stop_minutes: int = 30
    auto_stop_enabled: bool = True
    default_model: str = "FireRed-Image-Edit-1.1"
    default_quality: str = "high"
    default_identity_strength: str = "high"
    developer_mode: bool = False
    provider_type: str = "runpod"  # "runpod" or "mock"
