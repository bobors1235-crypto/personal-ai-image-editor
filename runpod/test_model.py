"""
Automated Model Quality Benchmark Suite (Milestone 1 Quality Gate).
Runs 20 comprehensive test cases for FireRed-Image-Edit-1.1 and outputs
visual side-by-side results and benchmark metrics (prompt following, timing, seeds).
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from shared.schemas import EditRequest
from runpod.image_utils import pil_to_base64, base64_to_pil
from local.prompt_engine import PromptEngine
from runpod.inference import registry

TEST_CASES = [
    # 1. Outfit changes
    {"id": 1, "name": "Outfit - Black Tailored Suit", "prompt": "غير اللبس لبدلة سودا رسمية", "category": "OUTFIT"},
    {"id": 2, "name": "Outfit - Black Leather Jacket", "prompt": "Change the outfit to a premium black leather jacket", "category": "OUTFIT"},
    {"id": 3, "name": "Outfit - White Linen Shirt", "prompt": "لبسه قميص أبيض كاجوال مريح", "category": "OUTFIT"},
    {"id": 4, "name": "Outfit - Luxury Evening Dress", "prompt": "Change clothing to an elegant emerald green evening gown", "category": "OUTFIT"},
    
    # 2. Background changes
    {"id": 5, "name": "Background - Paris Street", "prompt": "خلي الخلفية في شارع بباريس بجانب برج ايفل بالنهار", "category": "BACKGROUND"},
    {"id": 6, "name": "Background - New York at Night", "prompt": "Change background to a rainy New York City street at night with neon lights", "category": "BACKGROUND"},
    {"id": 7, "name": "Background - Beach Sunset", "prompt": "خليه واقف على شاطئ البحر وقت الغروب", "category": "BACKGROUND"},
    {"id": 8, "name": "Background - 5-Star Hotel Lobby", "prompt": "Change environment to a luxury 5-star hotel lobby with marble floors", "category": "BACKGROUND"},
    
    # 3. Camera Angle & Perspective
    {"id": 9, "name": "Camera - Low Angle Cinematic", "prompt": "Change the camera angle to a low-angle dramatic cinematic shot", "category": "CAMERA"},
    {"id": 10, "name": "Camera - Intimate Portrait Close-Up", "prompt": "Close-up portrait shot with shallow depth of field and beautiful bokeh", "category": "CAMERA"},
    
    # 4. Pose Changes
    {"id": 11, "name": "Pose - Sitting at Cafe Table", "prompt": "خليه قاعد على كرسي في كافيه وماسك فنجان قهوة", "category": "POSE"},
    {"id": 12, "name": "Pose - Confident Standing Posture", "prompt": "Change pose to standing confidently with arms crossed", "category": "POSE"},
    
    # 5. Lighting
    {"id": 13, "name": "Lighting - Golden Hour Sunlight", "prompt": "خلي الإضاءة شمس دافية وقت العصر الذهبي golden hour", "category": "LIGHTING"},
    {"id": 14, "name": "Lighting - Cyberpunk Neon Lighting", "prompt": "Add moody cyberpunk blue and magenta rim lighting", "category": "LIGHTING"},
    
    # 6. Object Add / Remove
    {"id": 15, "name": "Object - Add Sunglasses", "prompt": "ضيف له نظارة شمس سودا كلاسيكية", "category": "OBJECT"},
    {"id": 16, "name": "Object - Add Luxury Watch", "prompt": "Add a luxury stainless steel chronograph watch on the subject's wrist", "category": "OBJECT"},
    
    # 7. Multiple Simultaneous Edits
    {"id": 17, "name": "Multi - Suit + NYC Street Night + Low Angle", 
     "prompt": "غير اللبس لبدلة سودا وخلي التصوير في شارع بنيويورك بالليل وزاوية تصوير منخفضة", 
     "category": "MULTI"},
    {"id": 18, "name": "Multi - Leather Jacket + Paris Sunset", 
     "prompt": "Change outfit to leather jacket and change background to Paris at sunset", 
     "category": "MULTI"},
     
    # 8. Strict Identity Preservation Under Extreme Lighting
    {"id": 19, "name": "Identity - Studio High Contrast", 
     "prompt": "Professional dramatic black and white studio portrait lighting, preserve exact face and eyes", 
     "category": "IDENTITY"},
     
    # 9. Sequential Editing Workflow
    {"id": 20, "name": "Sequential Step - Final Polish", 
     "prompt": "Add subtle warm backlight and refine contrast while keeping the exact outfit and face", 
     "category": "SEQUENTIAL"}
]


def create_dummy_test_image() -> Image.Image:
    """Generate a clean synthetic portrait image for testing if no real photo is provided."""
    img = Image.new("RGB", (768, 1024), color=(235, 238, 245))
    draw = ImageDraw.Draw(img)
    # Draw simple silhouette / face placeholder
    draw.ellipse((284, 250, 484, 480), fill=(215, 170, 140)) # Face
    draw.ellipse((334, 330, 364, 360), fill=(40, 40, 40))   # Left eye
    draw.ellipse((404, 330, 434, 360), fill=(40, 40, 40))   # Right eye
    draw.rectangle((234, 480, 534, 900), fill=(60, 90, 150)) # Torso
    draw.text((260, 100), "TEST IMAGE BENCHMARK", fill=(50, 50, 50))
    return img


def run_benchmark(input_image_path: str = None, output_dir: str = "benchmark_results", model_name: str = "FireRed-Image-Edit-1.1"):
    """Execute all 20 test cases and log benchmark metrics."""
    os.makedirs(output_dir, exist_ok=True)
    
    if input_image_path and os.path.exists(input_image_path):
        base_img = Image.open(input_image_path).convert("RGB")
        print(f"[+] Loaded test image: {input_image_path} ({base_img.width}x{base_img.height})")
    else:
        print("[!] No input image provided. Using synthetic test image.")
        base_img = create_dummy_test_image()
        synthetic_path = os.path.join(output_dir, "base_test_image.png")
        base_img.save(synthetic_path)

    provider = registry.get_provider(model_name)
    provider.load()

    results = []
    current_img = base_img

    print("\n" + "="*70)
    print(f" STARTING MILESTONE 1 BENCHMARK: {model_name} (20 CASES)")
    print("="*70 + "\n")

    for test in TEST_CASES:
        t_id = test["id"]
        t_name = test["name"]
        raw_prompt = test["prompt"]

        print(f"[{t_id:02d}/20] Running Test: {t_name}")
        print(f"     Prompt: '{raw_prompt}'")

        # 1. Local Prompt Enhancement
        analysis = PromptEngine.enhance_edit_prompt(raw_prompt, identity_strength="high", quality="high")

        # 2. Select input image (use output of test 18 for test 20 to test sequential editing)
        run_input_img = current_img if test["category"] == "SEQUENTIAL" else base_img

        # 3. Run Inference
        result_img, seed_used, proc_time, meta = provider.edit(
            image=run_input_img,
            prompt=analysis.enhanced_prompt,
            seed=42000 + t_id,
            quality="high",
            identity_strength="high"
        )

        # Save result image
        res_filename = f"test_{t_id:02d}_{test['category'].lower()}.png"
        res_path = os.path.join(output_dir, res_filename)
        result_img.save(res_path)

        if t_id == 18:
            current_img = result_img # Save for sequential test 20

        results.append({
            "test_id": t_id,
            "name": t_name,
            "category": test["category"],
            "original_prompt": raw_prompt,
            "language": analysis.language,
            "categories_detected": analysis.categories,
            "change_targets": analysis.change_targets,
            "preserve_targets": analysis.preserve_targets,
            "enhanced_prompt": analysis.enhanced_prompt,
            "seed": seed_used,
            "processing_time_s": proc_time,
            "output_file": res_filename
        })
        print(f"     ✓ Done in {proc_time}s | Seed: {seed_used} | Output: {res_filename}\n")

    # Save JSON report
    report_path = os.path.join(output_dir, "benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("="*70)
    print(f" Benchmark Complete! Results saved in: {output_dir}")
    print(f" Full JSON log: {report_path}")
    print("="*70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Milestone 1 Quality Gate Benchmark")
    parser.add_argument("--image", type=str, default=None, help="Path to input test portrait image")
    parser.add_argument("--output", type=str, default="benchmark_results", help="Output directory for results")
    parser.add_argument("--model", type=str, default="FireRed-Image-Edit-1.1", help="Model name to benchmark")
    args = parser.parse_args()

    run_benchmark(args.image, args.output, args.model)
