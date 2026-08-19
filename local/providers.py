"""
Inference Client Providers for Local FastAPI Server.
Supports remote RunPod GPU Pod connections and Local Mock Provider for zero-cost testing.
Also includes RunPod GraphQL/REST API integration for Pod start/stop control.
"""

import time
import json
import logging
import requests
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageEnhance, ImageFilter

from shared.schemas import EditRequest, EditResponse, HealthResponse
from runpod.image_utils import base64_to_pil, pil_to_base64

logger = logging.getLogger("local_providers")


class BaseInferenceClient(ABC):
    """Abstract interface for local server to communicate with inference engines."""

    @abstractmethod
    def health(self) -> HealthResponse:
        """Check inference service health and availability."""
        pass

    @abstractmethod
    def edit(self, request: EditRequest) -> EditResponse:
        """Send image and prompt for editing."""
        pass

    @abstractmethod
    def switch_model(self, model_name: str) -> bool:
        """Switch active model."""
        pass


class RunPodClientProvider(BaseInferenceClient):
    """Client that communicates with the FastAPI server running on a RunPod GPU Pod."""

    def __init__(self, endpoint_url: str, api_key: Optional[str] = None, timeout: int = 180):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def health(self) -> HealthResponse:
        url = f"{self.endpoint_url}/health"
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return HealthResponse(**data)
            return HealthResponse(status="offline", gpu_name="RunPod Unreachable")
        except Exception as e:
            return HealthResponse(status="offline", gpu_name=f"Offline ({type(e).__name__})")

    def edit(self, request: EditRequest) -> EditResponse:
        url = f"{self.endpoint_url}/edit"
        try:
            resp = requests.post(url, headers=self.headers, json=request.model_dump(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return EditResponse(**data)
            else:
                return EditResponse(
                    success=False,
                    image_base64=None,
                    seed=request.seed or 0,
                    processing_time=0.0,
                    model_name=request.model_name,
                    enhanced_prompt=request.enhanced_prompt or request.prompt,
                    error=f"RunPod HTTP {resp.status_code}: {resp.text}"
                )
        except requests.exceptions.Timeout:
            return EditResponse(
                success=False,
                image_base64=None,
                seed=request.seed or 0,
                processing_time=self.timeout,
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error="RunPod inference request timed out. Please verify GPU pod status."
            )
        except Exception as e:
            return EditResponse(
                success=False,
                image_base64=None,
                seed=request.seed or 0,
                processing_time=0.0,
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error=f"Connection Error: {str(e)}"
            )

    def switch_model(self, model_name: str) -> bool:
        url = f"{self.endpoint_url}/model/load"
        try:
            resp = requests.post(url, headers=self.headers, json={"model_name": model_name}, timeout=60)
            return resp.status_code == 200 and resp.json().get("success", False)
        except Exception:
            return False


class MockClientProvider(BaseInferenceClient):
    """
    Mock inference provider for testing UI, history, and Prompt Engine locally
    without needing an active GPU or RunPod credit expenditure.
    """

    def __init__(self):
        self.active_model = "FireRed-Image-Edit-1.1"

    def health(self) -> HealthResponse:
        return HealthResponse(
            status="ready",
            gpu_name="Local Mock Provider (Zero Cost Test Mode)",
            vram_used_gb=0.0,
            vram_total_gb=48.0,
            active_model=self.active_model
        )

    def edit(self, request: EditRequest) -> EditResponse:
        start_t = time.time()
        # Simulate slight processing delay
        time.sleep(1.2)
        
        try:
            # Parse input image and apply subtle visual grading as mock demonstration
            pil_img = base64_to_pil(request.image_base64)
            
            # Subtle enhancement to visually show "edited" output in mock mode
            enhancer = ImageEnhance.Color(pil_img)
            mock_img = enhancer.enhance(1.15)
            sharpener = ImageEnhance.Sharpness(mock_img)
            mock_img = sharpener.enhance(1.2)

            res_b64 = pil_to_base64(mock_img, format="PNG")
            proc_time = round(time.time() - start_t, 2)
            actual_seed = request.seed if (request.seed and request.seed > 0) else 777123

            return EditResponse(
                success=True,
                image_base64=res_b64,
                seed=actual_seed,
                processing_time=proc_time,
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                metadata={
                    "mode": "mock_simulation",
                    "note": "Output generated in Mock Test Mode. Set provider to RunPod in Settings when GPU is running."
                }
            )
        except Exception as e:
            return EditResponse(
                success=False,
                image_base64=None,
                seed=0,
                processing_time=0.0,
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error=f"Mock processing error: {str(e)}"
            )

    def switch_model(self, model_name: str) -> bool:
        self.active_model = model_name
        return True


class RunPodAPIController:
    """Helper to start/stop Pods via RunPod GraphQL API."""

    RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"

    @classmethod
    def stop_pod(cls, api_key: str, pod_id: str) -> Tuple[bool, str]:
        """Send stop command to RunPod pod."""
        if not api_key or not pod_id:
            return False, "Missing RunPod API Key or Pod ID"

        query = """
        mutation {
            podStop(input: {podId: "%s"}) {
                id
                desiredStatus
            }
        }
        """ % pod_id

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(cls.RUNPOD_GRAPHQL_URL, headers=headers, json={"query": query}, timeout=15)
            if resp.status_code == 200 and "data" in resp.json():
                return True, f"Pod {pod_id} stop request sent successfully."
            return False, f"RunPod API error: {resp.text}"
        except Exception as e:
            return False, f"Failed to stop pod: {str(e)}"

    @classmethod
    def start_pod(cls, api_key: str, pod_id: str) -> Tuple[bool, str]:
        """Send resume/start command to RunPod pod."""
        if not api_key or not pod_id:
            return False, "Missing RunPod API Key or Pod ID"

        query = """
        mutation {
            podResume(input: {podId: "%s", gpuCount: 1}) {
                id
                desiredStatus
            }
        }
        """ % pod_id

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(cls.RUNPOD_GRAPHQL_URL, headers=headers, json={"query": query}, timeout=15)
            if resp.status_code == 200 and "data" in resp.json():
                return True, f"Pod {pod_id} start request sent successfully."
            return False, f"RunPod API error: {resp.text}"
        except Exception as e:
            return False, f"Failed to start pod: {str(e)}"
