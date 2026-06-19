#!/bin/bash
# DINOv2 로드 확인 (GPU)
set -euo pipefail
docker run --rm --entrypoint bash medi-train:gpu -c '
  pip install timm --break-system-packages -q
  pip show timm | head -3
  python3 -c "
import torch
try:
    m = torch.hub.load(\"facebookresearch/dinov2\", \"dinov2_vits14\")
    n = sum(p.numel() for p in m.parameters())
    print(\"DINOv2 OK (hub)\", n)
except Exception as e:
    print(\"hub failed:\", e)
    import timm
    m = timm.create_model(\"vit_small_patch14_dinov2.lvd142m\", pretrained=True)
    print(\"DINOv2 OK (timm)\", sum(p.numel() for p in m.parameters()))
" 2>&1 | tail -8
'
