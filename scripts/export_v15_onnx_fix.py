import torch, sys
sys.path.insert(0, '/workspace')
from training.train_v10 import MultiTaskV10Model

ckpt = torch.load('models/retinal_v15/best.pt',
                  map_location='cpu', weights_only=False)
print('체크포인트 키:', list(ckpt.keys()))

state = ckpt['model_state']
model = MultiTaskV10Model(grade_head=True)
missing, unexpected = model.load_state_dict(state, strict=False)
print(f'missing={len(missing)} unexpected={len(unexpected)}')
model.eval()

# torch 추론 반응 확인
dummy = torch.randn(1,3,224,224)
with torch.no_grad():
    out = model(dummy)
    gl1 = out['glaucoma'].item()

dummy2 = torch.randn(1,3,224,224) * 5
with torch.no_grad():
    out2 = model(dummy2)
    gl2 = out2['glaucoma'].item()

print(f'torch 반응: {gl1:.4f} vs {gl2:.4f} 정상={abs(gl1-gl2)>0.01}')
assert abs(gl1-gl2) > 0.01, 'torch 모델도 반응 없음!'

# ONNX 재변환
torch.onnx.export(
    model, dummy,
    'models/retinal_v15/retinal_v15.onnx',
    input_names=['input'],
    output_names=['dr','glaucoma','amd','myopia','multidisease','glaucoma_grade'],
    dynamic_axes={'input': {0: 'batch'}},
    opset_version=17,
)
print('ONNX 재변환 완료')

# 반응 확인
import onnxruntime as ort, numpy as np
sess = ort.InferenceSession(
    'models/retinal_v15/retinal_v15.onnx',
    providers=['CPUExecutionProvider'])
x1 = np.random.randn(1,3,224,224).astype(np.float32)
x2 = np.random.randn(1,3,224,224).astype(np.float32) * 5
o1 = float(sess.run(None,{sess.get_inputs()[0].name:x1})[1].reshape(-1)[0])
o2 = float(sess.run(None,{sess.get_inputs()[0].name:x2})[1].reshape(-1)[0])
print(f'ONNX: {o1:.4f} vs {o2:.4f} 반응={abs(o1-o2)>0.01}')
