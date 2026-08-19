"""
Unit tests for Local Prompt Engine.
Validates language detection, multi-category classification,
'Preserve vs Change' conflict resolution, and structured prompt builder.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from local.prompt_engine import PromptEngine


class TestPromptEngine(unittest.TestCase):

    def test_language_detection(self):
        # Arabic inputs
        self.assertEqual(PromptEngine.detect_language("غير اللبس لبدلة سودا"), "ar")
        self.assertEqual(PromptEngine.detect_language("خليه واقف على البحر بالليل"), "ar")
        # English inputs
        self.assertEqual(PromptEngine.detect_language("Change the outfit to a black leather jacket"), "en")
        self.assertEqual(PromptEngine.detect_language("Set the background to Paris at sunset"), "en")

    def test_category_classification_arabic(self):
        # Outfit
        analysis_outfit = PromptEngine.enhance_edit_prompt("غير اللبس لبدلة سودا رسمية")
        self.assertIn("OUTFIT", analysis_outfit.categories)

        # Background
        analysis_bg = PromptEngine.enhance_edit_prompt("خلي الخلفية في شارع بنيويورك بالليل")
        self.assertIn("BACKGROUND", analysis_bg.categories)

        # Pose & Camera
        analysis_pose = PromptEngine.enhance_edit_prompt("خليه قاعد وزاوية تصوير منخفضة Low Angle")
        self.assertIn("POSE", analysis_pose.categories)
        self.assertIn("CAMERA", analysis_pose.categories)

        # Object
        analysis_obj = PromptEngine.enhance_edit_prompt("ضيف له نظارة شمس وساعة فاخرة")
        self.assertIn("OBJECT", analysis_obj.categories)

    def test_preserve_vs_change_logic(self):
        # When user asks to change pose, body pose MUST NOT be in preserve targets!
        analysis = PromptEngine.enhance_edit_prompt("غير وضعية الجسم وخليه قاعد")
        self.assertIn("POSE", analysis.categories)
        self.assertIn("body pose & posture", analysis.change_targets)
        
        # Check that original body pose is NOT in preserve targets
        for p in analysis.preserve_targets:
            self.assertNotIn("original body pose", p)
        
        # But facial identity and hair SHOULD still be preserved
        preserved_str = " ".join(analysis.preserve_targets)
        self.assertIn("facial identity", preserved_str)
        self.assertIn("hairstyle", preserved_str)

    def test_preserve_outfit_when_changing_background(self):
        # When user ONLY changes background, outfit must be preserved
        analysis = PromptEngine.enhance_edit_prompt("خلي الخلفية في باريس بجانب برج ايفل")
        self.assertIn("BACKGROUND", analysis.categories)
        self.assertNotIn("OUTFIT", analysis.categories)

        preserved_str = " ".join(analysis.preserve_targets)
        self.assertIn("clothing and outfit", preserved_str)
        self.assertIn("facial identity", preserved_str)

    def test_structured_prompt_output(self):
        analysis = PromptEngine.enhance_edit_prompt(
            prompt="غير اللبس لجاكيت جلد وخلي التصوير في نيويورك",
            identity_strength="high",
            quality="high"
        )
        self.assertTrue(len(analysis.enhanced_prompt) > 50)
        self.assertIn("[ACTION]", analysis.enhanced_prompt)
        self.assertIn("[SUBJECT & IDENTITY]", analysis.enhanced_prompt)
        self.assertIn("[QUALITY & AESTHETICS]", analysis.enhanced_prompt)


if __name__ == "__main__":
    unittest.main()
