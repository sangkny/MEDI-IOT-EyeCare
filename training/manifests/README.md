# Training manifests

| File | Description |
|------|-------------|
| `unified_v4.json` | APTOS + Messidor + IDRiD (5,235) |
| `unified_eyeq_good.json` | EyeQ Good EyePACS (8,347) + v4 (5,235) ≈ **13,582** |

Build EyeQ Good manifest (GPU):

```bash
python3 scripts/build_unified_eyeq_good.py
```

v8 training:

```bash
bash scripts/start_v8_train.sh
```

Docker must mount `~/workspace/dataset:/dataset:ro` for EyePACS paths.
