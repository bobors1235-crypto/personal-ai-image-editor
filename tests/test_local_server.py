"""
Unit & integration tests for Local FastAPI server, providers, and history persistence.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from fastapi.testclient import TestClient
from PIL import Image
from local.server import app, state
from runpod.image_utils import pil_to_base64


class TestLocalServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Force mock provider for testing
        state.config.provider_type = "mock"
        state.provider = state.init_provider()
        cls.client = TestClient(app)

        cls.sample_img = Image.new("RGB", (128, 128), color=(100, 150, 200))
        cls.sample_b64 = pil_to_base64(cls.sample_img, format="PNG")

    def test_health_route(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["provider_type"], "mock")
        self.assertIn("session_uptime_formatted", data)
        self.assertIn("estimated_cost_usd", data)

    def test_prompt_analyze_route(self):
        resp = self.client.post("/api/prompt/analyze", json={
            "prompt": "غير اللبس لبدلة سودا وخلي التصوير في شارع بنيويورك بالليل",
            "identity_strength": "high",
            "quality": "high"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["language"], "ar")
        self.assertIn("OUTFIT", data["categories"])
        self.assertIn("BACKGROUND", data["categories"])
        self.assertIn("[ACTION]", data["enhanced_prompt"])

    def test_edit_and_history_workflow(self):
        # 1. Execute Edit
        payload = {
            "image_base64": self.sample_b64,
            "prompt": "Change background to a modern office",
            "model_name": "FireRed-Image-Edit-1.1",
            "seed": 99999,
            "quality": "normal",
            "identity_strength": "high"
        }
        resp = self.client.post("/api/edit", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["edit_response"]["success"])
        self.assertIn("history_item", data)
        hist_id = data["history_item"]["id"]

        # 2. Check History
        hist_resp = self.client.get("/api/history")
        self.assertEqual(hist_resp.status_code, 200)
        items = hist_resp.json()
        self.assertTrue(any(item["id"] == hist_id for item in items))

        # 3. Clean up history entry
        del_resp = self.client.delete(f"/api/history/{hist_id}")
        self.assertEqual(del_resp.status_code, 200)

    def test_config_get_and_update(self):
        # GET config
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        cfg = resp.json()
        self.assertIn("gpu_hourly_cost", cfg)

        # POST config
        cfg["gpu_hourly_cost"] = 0.45
        update_resp = self.client.post("/api/config", json=cfg)
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(state.config.gpu_hourly_cost, 0.45)


if __name__ == "__main__":
    unittest.main()
