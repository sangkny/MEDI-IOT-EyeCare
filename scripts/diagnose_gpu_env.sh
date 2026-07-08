#!/bin/bash
# GPU 컨테이너 내부 CUDA/cuDNN/ONNX 진단
set -e
docker run --rm --entrypoint bash --gpus all medi-train:gpu -c '
echo "=== CUDA 버전 ==="
nvcc --version 2>/dev/null || echo "nvcc 없음"
echo "=== cuDNN ldconfig ==="
ldconfig -p 2>/dev/null | grep -i cudnn | head -10 || true
python3 -c "import ctypes; ctypes.CDLL(\"libcudnn.so.9\")" 2>&1 || true
python3 -c "import ctypes; ctypes.CDLL(\"libcudnn.so.8\")" 2>&1 || true
echo "=== PyTorch CUDA ==="
python3 -c "
import torch
print(\"torch:\", torch.__version__)
print(\"CUDA available:\", torch.cuda.is_available())
print(\"cuDNN enabled:\", torch.backends.cudnn.enabled)
print(\"cuDNN version:\", torch.backends.cudnn.version() if torch.cuda.is_available() else \"N/A\")
print(\"GPU:\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"없음\")
"
echo "=== ONNX Runtime providers ==="
python3 -c "
import onnxruntime as ort
print(\"ort version:\", ort.__version__)
print(\"available providers:\", ort.get_available_providers())
" 2>&1 || echo "onnxruntime not installed"
echo "=== LD_LIBRARY_PATH ==="
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
'
