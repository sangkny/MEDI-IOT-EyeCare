"""
파일명: inspect_v10_onnx.py
목적: inspect_v10_onnx.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
#!/usr/bin/env python3
import onnxruntime as ort
from pathlib import Path
from services.retinal_cnn import preprocess_fundus_bytes

img = Path("/app/fundus_right_sklee.jpg").read_bytes()
t = preprocess_fundus_bytes(img, preprocess_mode="none")
sess = ort.InferenceSession(
    "/app/models/retinal_v10.onnx",
    providers=["CPUExecutionProvider"],
)
outs = sess.run(None, {sess.get_inputs()[0].name: t.numpy()})
names = [o.name for o in sess.get_outputs()]
for name, arr in zip(names, outs):
    print(name, arr.shape, arr.reshape(-1)[:10])
