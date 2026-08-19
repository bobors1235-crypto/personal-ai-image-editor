#!/bin/bash
set -e

echo "=========================================================="
echo " Personal AI Image Editor - RunPod Installation Script    "
echo "=========================================================="

# Ensure /workspace storage exists
mkdir -p /workspace/models
mkdir -p /workspace/cache

export HF_HOME=/workspace/cache/huggingface
export TORCH_HOME=/workspace/cache/torch

echo "[1/4] Updating packages..."
apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 git curl

echo "[2/4] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Installing Diffusers from source (recommended for latest FireRed / Qwen edits)..."
pip install git+https://github.com/huggingface/diffusers.git

echo "[4/4] Verifying GPU and CUDA availability..."
python3 -c "import torch; print('CUDA Available:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

echo "=========================================================="
echo " Installation Complete! Run ./start.sh to launch server. "
echo "=========================================================="
