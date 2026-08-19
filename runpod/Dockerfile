FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cleanly install matched PyTorch 2.5.1 suite to eliminate torchaudio ABI undefined symbol errors
RUN pip uninstall -y torchaudio torchvision torch && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124 && \
    pip install --no-cache-dir git+https://github.com/huggingface/diffusers.git transformers accelerate safetensors sentencepiece protobuf runpod fastapi uvicorn pillow pydantic requests httpx

# Create cache directories
RUN mkdir -p /root/.cache/huggingface /root/.cache/torch /root/.cache/image_editor_models

# Copy project files
COPY shared /app/shared
COPY runpod /app/runpod

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/runpod
ENV HF_HOME=/root/.cache/huggingface
ENV TORCH_HOME=/root/.cache/torch

CMD ["python", "-u", "/app/runpod/serverless_handler.py"]
