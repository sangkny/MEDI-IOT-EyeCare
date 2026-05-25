#!/usr/bin/env python3
"""ViT-Large batch=4 VRAM 스모크 (GPU 서버)."""
import torch

print("CUDA", torch.cuda.is_available())
if torch.cuda.is_available():
    print("VRAM GB", torch.cuda.get_device_properties(0).total_memory / 1e9)

try:
    import timm

    model = timm.create_model("vit_large_patch16_224", pretrained=False).cuda()
    x = torch.randn(4, 3, 224, 224).cuda()
    y = model(x)
    torch.cuda.synchronize()
    print("ViT-Large batch=4 OK", tuple(y.shape))
    print("alloc GB", torch.cuda.memory_allocated() / 1e9)
except RuntimeError as exc:
    print("OOM", exc)
