FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Keep the base image's CUDA-matched PyTorch. Pin Diffusers because FireRed's
# model index requires QwenImageEditPlusPipeline; a Git HEAD build is not reproducible.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir diffusers==0.36.0 "transformers>=4.49,<5" "accelerate>=1.4,<2" safetensors sentencepiece protobuf runpod fastapi uvicorn pillow pydantic requests httpx && \
    rm -rf /root/.cache/pip /tmp/*

# Create cache directories
RUN mkdir -p /root/.cache/huggingface /root/.cache/torch /root/.cache/image_editor_models

# Copy project files
COPY shared /app/shared
COPY runpod /app/runpod

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/runpod
ENV HF_HOME=/workspace/models
ENV RUNPOD_MODEL_CACHE=/workspace/models
ENV RUNPOD_MIN_FREE_DISK_GB=60
ENV RUNPOD_CPU_OFFLOAD=0
ENV TORCH_HOME=/root/.cache/torch
ENV PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

CMD ["python", "-u", "/app/runpod/serverless_handler.py"]
