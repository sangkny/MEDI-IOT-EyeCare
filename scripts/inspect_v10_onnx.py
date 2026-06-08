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
