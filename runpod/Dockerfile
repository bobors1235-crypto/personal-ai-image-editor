FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY runpod/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir runpod && \
    pip install --no-cache-dir git+https://github.com/huggingface/diffusers.git

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
