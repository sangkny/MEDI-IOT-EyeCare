# 훈련 전·외부 수령 체크리스트

## A–B. 훈련 전 준비 — ✅ 완료

합성 데이터 · `medi-train:gpu` · E2E · 호스트 curl · FHIR · MinIO 경로 — `docs/PRE_TRAINING_TASKS.md` 이전 버전 참고.

## C. 외부 훈련 결과 수령 (연습 + 실전) — ✅ 파이프라인 검증

| 단계 | 명령 | 상태 |
|------|------|------|
| C0 | 1 epoch dry-run → `models/retinal_v3.*` | ✅ (합성, QWK~0.49 — **실전 전 연습용**) |
| C1 | `verify_external_model.py --stem retinal_v3` | ✅ |
| C2 | `receive_external_model.py --from-dir models/incoming` | ✅ |
| C3 | `deploy_model.py --target minio` | ✅ MinIO 객체 존재 |
| C4 | `download_model.py --dry-run` | ✅ |
| C5 | API auto → `retinal_v3.onnx` | ✅ |
| C6 | `host_fundus_partner_smoke.ps1` | ✅ v3 추론 |
| C7 | eval (실데이터 manifest) | ⏳ Messidor 수동 다운로드 후 |

**SSOT**: [`docs/external-model-receive.md`](./external-model-receive.md)

```bash
# 외부 서버에서 받은 뒤
python scripts/receive_external_model.py --from-dir models/incoming --stem retinal_v3 --upload-minio
cd ../.. && docker compose -f docker-compose.dev.yml up -d medi-iot-api --force-recreate
scripts/host_fundus_partner_smoke.ps1
```

## D. 실데이터 훈련 (24h 후 · GPU 서버)

1. Messidor-2 → `data/messidor2/images/...` (`data/README.md`)
2. `build_messidor2_manifest.py` → `data/messidor2_manifest.json`
3. `train-gpu` 50 epoch → **실제** `retinal_v3.*` (dry-run 파일 덮어쓰기)
4. eval QWK ≥ 0.85 → C절 수령 파이프라인 반복
