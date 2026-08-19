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


class RunPodServerlessClientProvider(BaseInferenceClient):
    """Client for RunPod Serverless Endpoints (Scale-to-Zero)."""

    def __init__(self, endpoint_id: str, api_key: str, timeout: int = 300):
        self.endpoint_id = endpoint_id.strip() if endpoint_id else ""
        self.api_key = api_key.strip() if api_key else ""
        self.timeout = timeout
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def health(self) -> HealthResponse:
        if not self.endpoint_id or not self.api_key:
            return HealthResponse(status="offline", gpu_name="Missing Serverless Endpoint ID or API Key")

        url = f"{self.base_url}/health"
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                workers = data.get("workers", {})
                ready_workers = workers.get("ready", 0) + workers.get("running", 0)
                idle_workers = workers.get("idle", 0)
                return HealthResponse(
                    status="ready",
                    gpu_name=f"RunPod Serverless ({ready_workers + idle_workers} active workers)",
                    vram_used_gb=0.0,
                    vram_total_gb=48.0,
                    active_model="FireRed-Image-Edit-1.1"
                )
            return HealthResponse(status="offline", gpu_name=f"Serverless Error ({resp.status_code})")
        except Exception as e:
            return HealthResponse(status="offline", gpu_name=f"Serverless Offline ({type(e).__name__})")

    def edit(self, request: EditRequest) -> EditResponse:
        if not self.endpoint_id or not self.api_key:
            return EditResponse(
                success=False,
                seed=0,
                processing_time=0.0,
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error="Serverless Endpoint ID and RunPod API Key are required. Please configure them in Settings."
            )

        start_time = time.time()
        payload = {"input": request.model_dump()}

        # Always submit via async /run to prevent HTTP Gateway timeouts during Cold Starts
        run_url = f"{self.base_url}/run"
        try:
            logger.info(f"Submitting job to RunPod Serverless Endpoint {self.endpoint_id}...")
            resp = requests.post(run_url, headers=self.headers, json=payload, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("id")
                status = data.get("status")
                logger.info(f"Job created on RunPod: ID={job_id}, Initial Status={status}")

                if status == "COMPLETED":
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        if "seed" not in output:
                            output["seed"] = request.seed or 0
                        if "model_name" not in output:
                            output["model_name"] = request.model_name
                        if "enhanced_prompt" not in output:
                            output["enhanced_prompt"] = request.enhanced_prompt or request.prompt
                        output["processing_time"] = round(time.time() - start_time, 2)
                        return EditResponse(**output)

                if job_id:
                    return self._poll_job(job_id, start_time, request)

            return EditResponse(
                success=False,
                seed=request.seed or 0,
                processing_time=round(time.time() - start_time, 2),
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error=f"Serverless launch error: HTTP {resp.status_code} - {resp.text}"
            )

        except Exception as e:
            return EditResponse(
                success=False,
                seed=request.seed or 0,
                processing_time=round(time.time() - start_time, 2),
                model_name=request.model_name,
                enhanced_prompt=request.enhanced_prompt or request.prompt,
                error=f"Serverless connection error: {str(e)}"
            )

    def _poll_job(self, job_id: str, start_time: float, request: EditRequest) -> EditResponse:
        status_url = f"{self.base_url}/status/{job_id}"
        poll_interval = 3.0
        max_duration = 600.0  # Allow up to 10 minutes for cold start + generation
        max_polls = int(max_duration / poll_interval)

        logger.info(f"Polling RunPod job {job_id} for up to {int(max_duration)}s...")

        for poll_idx in range(max_polls):
            time.sleep(poll_interval)
            try:
                resp = requests.get(status_url, headers=self.headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")

                    if poll_idx % 4 == 0:
                        elapsed = int(time.time() - start_time)
                        logger.info(f"Job {job_id} status: {status} (elapsed: {elapsed}s)")

                    if status == "COMPLETED":
                        output = data.get("output", {})
                        if isinstance(output, dict):
                            if "seed" not in output:
                                output["seed"] = request.seed or 0
                            if "model_name" not in output:
                                output["model_name"] = request.model_name
                            if "enhanced_prompt" not in output:
                                output["enhanced_prompt"] = request.enhanced_prompt or request.prompt
                            output["processing_time"] = round(time.time() - start_time, 2)
                            logger.info(f"Job {job_id} completed successfully in {output['processing_time']}s!")
                            return EditResponse(**output)

                    elif status in ["FAILED", "CANCELLED"]:
                        err_msg = data.get("error", "Serverless job failed or was cancelled.")
                        logger.error(f"Job {job_id} failed: {err_msg}")
                        return EditResponse(
                            success=False,
                            seed=request.seed or 0,
                            processing_time=round(time.time() - start_time, 2),
                            model_name=request.model_name,
                            enhanced_prompt=request.enhanced_prompt or request.prompt,
                            error=f"Job {status}: {err_msg}"
                        )
            except Exception as e:
                logger.warning(f"Transient error polling job {job_id}: {e}")

        return EditResponse(
            success=False,
            seed=request.seed or 0,
            processing_time=round(time.time() - start_time, 2),
            model_name=request.model_name,
            enhanced_prompt=request.enhanced_prompt or request.prompt,
            error="Serverless job timed out waiting for worker cold start and execution."
        )

    def switch_model(self, model_name: str) -> bool:
        return True


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
