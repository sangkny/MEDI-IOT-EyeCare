#!/bin/bash
# STEP 3: cuDNN 파일 위치 탐색
set -e
docker run --rm --entrypoint bash --gpus all medi-train:gpu -c '
echo "=== cudnn 파일 실제 존재 위치 ==="
find /usr -name "libcudnn*.so*" 2>/dev/null | head -20
find /opt -name "libcudnn*.so*" 2>/dev/null | head -10
echo "=== cuda 파일 위치 ==="
find /usr -name "libcuda*.so*" 2>/dev/null | head -10
echo "=== LD_LIBRARY_PATH ==="
echo "$LD_LIBRARY_PATH"
'
