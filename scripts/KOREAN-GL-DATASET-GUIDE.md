# MEDI-IoT 한국인 녹내장 데이터셋 관리 가이드

## ⚠️ 보안 및 법적 요구사항

| 항목 | 내용 |
|------|------|
| **IRB 승인** | 국내 임상기관 IRB 승인 (**2019년**) |
| **보관 정책** | **GPU 서버(192.168.0.23) 로컬 전용** |
| **외부 반출** | **금지** (클라우드, GitHub, 외부망 전송 불가) |
| **Git 커밋** | **금지** (.gitignore 자동 설정됨) |
| **마스킹** | 모든 이미지 개인정보 마스킹 처리 완료 |

---

## 1. 데이터셋 개요

| 항목 | 내용 |
|------|------|
| 환자 수 | 173명 (수정본) + 원본 폴더 173 (시계열 포함) |
| 안구 수 | 최대 ~600안 (수정본 컬러) + ~800안 (원본 안저) |
| 예상 이미지 | 수정본 컬러+IR ~600장, 원본 안저+시야+OCT ~1,200장+ |
| 진단 | NTG, POAG, CNAG, PEX, PACG, NVG, Secondary |
| Grade | 1(경증), 2(중등도), 3(중증) |

### 한국인 NTG 데이터의 특별한 가치

```
한국인 NTG 유병률: 높음 (국내 임상 코호트 기준)
기존 공개 데이터셋: 서양/싱가포르 기반, NTG 비율 낮음
→ v10c가 한국인 NTG에서 성능 저하 가능성
→ 이 데이터로 한국인 특화 모델 개선 기대
```

---

## 2. 디렉토리 구조

```
GPU 서버 (192.168.0.23)

/dataset/
├── korean_fundus_input/          ← 원본 보관 (읽기 전용으로 마운트)
│   ├── glaucoma_modified/
│   │   ├── 1.jpg ~ 173.jpg
│   │   └── glaucoma_modified_info.xlsx
│   └── glaucoma_origin/
│       ├── {folder_no}/*.jpg
│       └── glaucoma_origin_info.xlsx
│
└── korean_glaucoma_fundus/       ← 처리 결과 (Git 추적 금지)
    ├── .gitignore                ← * (전체 추적 금지)
    ├── modified/
    │   ├── color/OD|OS/
    │   └── ir/OD|OS/
    ├── origin/
    │   ├── fundus/OD|OS/
    │   ├── vf/OD|OS/
    │   └── oct/
    ├── labels_modified.csv
    ├── labels_origin.csv
    ├── manifest_modified.json
    ├── manifest_origin.json
    ├── timeseries_analysis.json
    └── timeseries_labels.csv

기존 공개 데이터셋 (변경 없음):
/dataset/resized_cache/           ← APTOS, IDRiD 등
/dataset/disc_cup_masks/          ← G1020, ORIGA 마스크
```

---

## 3. 파일명 규칙

```
수정본: MEDI_KR_GL_modified_{img_no:04d}_{eye}_{modality}.jpg
원본:   MEDI_KR_GL_orig_{folder:04d}_{date}_{eye}_{mod}.jpg

예:
  MEDI_KR_GL_modified_0019_R_color.jpg
  MEDI_KR_GL_orig_0019_20190503_R_color.jpg

접두사 MEDI_KR_GL_ → 공개 데이터셋과 혼동 불가
```

---

## 4. 마스킹 처리 내용

```
대상: 이미지 내 초록색 텍스트 (환자 식별 정보)

방법:
  G > 80 AND G > R×1.4 AND G > B×1.4 감지
  감지 픽셀 + 8px 팽창(dilate) → 검은색으로 덮음

CSV 컬럼 _unit_no, _age_raw, _sex:
  관리 목적으로만 보관
  AI 모델 입력으로 절대 사용하지 않음 (컬럼명에 _ 접두사)
```

---

## 5. 실행 절차

### 5-1. 전체 파이프라인 (개발 PC WSL)

```bash
cd projects/MEDI-IOT-EyeCare
bash scripts/run_all_korean_gl_gpu.sh           # 실제 전처리
bash scripts/run_all_korean_gl_gpu.sh --dry-run # 확인만
```

### 5-2. 개별 단계

```bash
bash scripts/run_preprocess_korean_gl_gpu.sh
bash scripts/run_preprocess_korean_gl_origin_gpu.sh
bash scripts/run_verify_korean_gl_gpu.sh
```

### 5-3. v10c 성능 검증

```bash
bash scripts/run_eval_korean_gl_gpu.sh
```

---

## 6. 훈련 활용 계획

### v10c 성능 검증

```bash
python3 scripts/eval_korean_gl.py
# 출력: /dataset/korean_glaucoma_fundus/eval_v10c_korean.json
```

### v14 훈련 데이터 추가

```
기존 unified_v10: 27,546장
추가 예상:        ~1,400장 (한국인 임상)
라벨:             glaucoma=1, glaucoma_grade, is_ntg, korean_clinical=true
빌드:             python3 scripts/build_v14_manifest.py
```

---

## 7. 금지 사항 체크리스트

```
❌ GitHub/GitLab 등 원격 저장소에 이미지/CSV 업로드
❌ 클라우드 스토리지(S3, GCS 등)에 업로드
❌ 외부 연구기관 공유 (IRB 범위 외)
❌ 공개 데이터셋과 혼합하여 재배포
❌ 원본 이미지(마스킹 전)를 처리 결과 경로에 보관
❌ unit_no를 모델 입력 피처로 사용
```

---

*주식회사 메디아이오티 (MEDI-IoT Co., Ltd.) | 내부 전용 문서*  
*IRB: 국내 임상기관 승인 (2019)*
