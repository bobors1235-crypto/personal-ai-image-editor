"""
Integration tests for RunPod API inference server.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from fastapi.testclient import TestClient
from PIL import Image
from runpod.api import app
from runpod.image_utils import pil_to_base64


class TestRunPodAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Create a small sample image
        cls.sample_img = Image.new("RGB", (128, 128), color=(200, 150, 100))
        cls.sample_b64 = pil_to_base64(cls.sample_img, format="PNG")

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ready")
        self.assertIn("gpu_name", data)
        self.assertIn("active_model", data)

    def test_models_endpoint(self):
        resp = self.client.get("/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("FireRed-Image-Edit-1.1", data["available_models"])

    def test_edit_endpoint(self):
        payload = {
            "image_base64": self.sample_b64,
            "prompt": "Change outfit to a black suit",
            "model_name": "FireRed-Image-Edit-1.1",
            "seed": 42123,
            "quality": "normal",
            "identity_strength": "high"
        }
        resp = self.client.post("/edit", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["image_base64"])
        self.assertEqual(data["seed"], 42123)
        self.assertTrue(data["processing_time"] >= 0)


if __name__ == "__main__":
    unittest.main()
