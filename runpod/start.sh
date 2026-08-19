#!/bin/bash
set -e

echo "=========================================================="
echo " Starting Personal AI Image Editor Server on RunPod       "
echo "=========================================================="

export HF_HOME=/workspace/cache/huggingface
export TORCH_HOME=/workspace/cache/torch
export PYTHONUNBUFFERED=1

# Launch uvicorn on port 8000
python3 -m uvicorn runpod.api:app --host 0.0.0.0 --port 8000 --workers 1
