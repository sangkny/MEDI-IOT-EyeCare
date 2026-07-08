# MEDI-IOT 데이터셋 레지스트리

> SSOT 원칙: **새 데이터셋 추가 시 이 파일을 먼저 갱신**  
> 상세 훈련 이력: `docs/MODEL-VERSION-HISTORY.md` · `book/part7/ch41-model-version-history.md`

---

## GPU 서버 경로 매핑 (192.168.0.23)

| 호스트 경로 | 컨테이너 | 용도 |
|-------------|----------|------|
| `~/workspace/dataset/` | `/dataset` | GL/AMD/MYO/Multi + 한국인 임상 |
| `~/workspace/.../MEDI-IOT-EyeCare/data/` | `/data_dr` | DR resized_cache |
| `~/workspace/.../MEDI-IOT-EyeCare/models/` | `/workspace/models` | ONNX/체크포인트 |

---

## 공개 데이터셋

| ID | 질환 | 장수(대략) | 라이선스 | 다운로드/경로 | 훈련 사용 |
|----|------|-----------|----------|---------------|----------|
| APTOS 2019 | DR | 3,662 | Kaggle | `resized_cache/aptos2019_raw/` | ✅ v4~ |
| Messidor-2 | DR | 1,744 | 공개 | `resized_cache/Messidor-2_raw/` | ✅ v4~ |
| IDRiD | DR+AMD | 516 | 공개 | `resized_cache/IDRiD_raw/` | ✅ v4~ |
| EyeQ | 품질 | 28,792 | 공개 | `resized_cache/EyeQ/` | ✅ 필터링 |
| G1020 | GL | 1,020 | 연구용 | `Glaucoma_raw/G1020/` | ✅ v10~ |
| ORIGA | GL | 651 | 연구용 | `Glaucoma_raw/ORIGA/` | ✅ v10~ |
| REFUGE/REFUGE2 | GL | 1,200 | 챌린지 | `Glaucoma_raw/REFUGE/` | ✅ v10~ |
| ACRIMA | GL | 705 | CC BY | `Glaucoma_extra/` | ✅ v10~ |
| RIM-ONE | GL | 313 | 연구용 | `Glaucoma_extra/rimone/` | ✅ v10~ |
| AIROGS | GL | 8,770 | 연구용 | `Glaucoma_extra/airogs/` | ✅ v10~ |
| AMDNet23+ODIR+RFMiD | AMD | 3,915 | 혼합 | `AMD_raw/`, ODIR | ✅ v10~ |
| ODIR+RFMiD | MYO | 2,909 | 혼합 | `Multidisease_raw/` | ✅ v10~ |
| RFMiD+ODIR | Multi | 9,592 | 혼합 | `Multidisease_raw/` | ✅ v10~ |
| EyePACS | DR | 88,702 | Kaggle | 일부 manifest | ✅ 일부 |

---

## 임상 데이터셋 (IRB · 로컬 전용)

| ID | 질환 | 장수(예상) | IRB | 접근 | 훈련 |
|----|------|-----------|-----|------|------|
| Korean GL Modified | GL | ~600 | 국내 임상기관 2019 | GPU 로컬만 | ⏳ v14 |
| Korean GL Origin | GL+VF+OCT | ~800 안저 | 국내 임상기관 2019 | GPU 로컬만 | ⏳ v14 |
| Korean timeseries | GL | 60명 복수방문 | 동일 | 로컬만 | 예후 추적 설계 |

**금지**: Git 커밋 · 외부 반출 · 클라우드 업로드

경로: `/dataset/korean_glaucoma_fundus/`  
가이드: `scripts/KOREAN-GL-DATASET-GUIDE.md`

---

## manifest 파일

| 파일 | 장수 | Git | 비고 |
|------|------|-----|------|
| `unified_v10.json` | 27,546 | ❌ (GPU 로컬) | v10c 운영 |
| `unified_v14.json` | ~29,000 | ❌ | `build_v14_manifest.py` |
| `glaucoma_v2.json` | 11,725 | ✅ | GL 단독 |
| `labels_modified.csv` | — | ❌ | 한국인 라벨 |

---

## 새 데이터셋 추가 체크리스트

1. 이 레지스트리에 행 추가 (라이선스·경로·IRB)
2. `training/make_manifest.py` 또는 전용 빌더 스크립트
3. `docs/MODEL-VERSION-HISTORY.md` 갱신
4. `book/part7/ch41b-dataset-management.md` 갱신 (외부 공개 수준)
5. IRB 데이터면 `.gitignore` + GPU 로컬만

---

## 관련 스크립트

| 스크립트 | 용도 |
|----------|------|
| `scripts/download_indication_data.sh` | 공개 GL/AMD 다운로드 |
| `scripts/build_v10_manifest.sh` | unified_v10 생성 |
| `scripts/build_v14_manifest.py` | 한국인 통합 v14 |
| `scripts/run_all_korean_gl_gpu.sh` | 한국인 전처리 |
