"""
Image utilities for RunPod and Local processing.
Handles base64 encoding/decoding, EXIF orientation fix, aspect-ratio resizing,
and memory optimization.
"""

import io
import base64
from typing import Tuple, Optional
from PIL import Image, ImageOps


def base64_to_pil(base64_str: str) -> Image.Image:
    """Convert base64 string (with or without data URI header) to PIL Image."""
    if "," in base64_str:
        base64_str = base64_str.split(",", 1)[1]
    
    image_data = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_data))
    
    # Correct EXIF rotation if any
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
        
    return image.convert("RGB")


def pil_to_base64(image: Image.Image, format: str = "PNG", quality: int = 95) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    if format.upper() == "JPEG" or format.upper() == "JPG":
        image.save(buffered, format="JPEG", quality=quality, optimize=True)
    elif format.upper() == "WEBP":
        image.save(buffered, format="WEBP", quality=quality)
    else:
        image.save(buffered, format="PNG", optimize=True)
        
    encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/{format.lower()};base64,{encoded}"


def resize_image_aspect_ratio(
    image: Image.Image,
    max_dim: int = 1024,
    multiple_of: int = 64
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Resize image to ensure max dimension <= max_dim and dimensions are multiples of multiple_of (required by diffusion models).
    Returns (resized_image, original_size).
    """
    orig_w, orig_h = image.size
    
    # Calculate scale factor
    scale = min(max_dim / orig_w, max_dim / orig_h, 1.0)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    # Round to closest multiple of 64 or 32 for UNet/DiT architectures
    new_w = max(multiple_of, (new_w // multiple_of) * multiple_of)
    new_h = max(multiple_of, (new_h // multiple_of) * multiple_of)
    
    if (new_w, new_h) != (orig_w, orig_h):
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return resized, (orig_w, orig_h)
        
    return image, (orig_w, orig_h)
