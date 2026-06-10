# SaMD 인증 준비 체크리스트

> MEDI-IOT-EyeCare · 2등급 SaMD · ch45 SSOT  
> 최종 업데이트: 2026-06-10

| # | 항목 | 현재 상태 | 담당 | 기한 |
|---|------|----------|------|------|
| 1 | 소프트웨어 명세서 (기술문서) | 📋 | TBD | Phase 1 |
| 2 | ch41 모델 계보 · 성능표 정리 | ✅ | — | 완료 |
| 3 | 알고리즘 설명서 (5질환 + 스크리닝) | ⚠️ ch44·ch39 기반 초안 | TBD | Phase 1 |
| 4 | audit_trail / decision gate 문서 | ✅ API 구현 | TBD | Phase 1 |
| 5 | Git 버전관리 · 릴리스 태그 정책 | ✅ | TBD | Phase 1 |
| 6 | IEC 62304 SW 생명주기 문서 | 📋 | TBD | Phase 2 |
| 7 | ISO 14971 위험관리 파일 | 📋 | TBD | Phase 2 |
| 8 | IEC 62366 사용적합성 (Portal UX) | 📋 | TBD | Phase 2 |
| 9 | IMDRF AI/ML 변경관리 계획 | 📋 | TBD | Phase 2 |
| 10 | ISO 27001 / 사이bersecurity | ⚠️ HTTPS·JWT 기본 | TBD | Phase 2 |
| 11 | DR 임상 500건 설계 | 📋 | TBD | Phase 2 |
| 12 | Glaucoma 임상 (Sens≥90%) | ⚠️ v10c GL AUC **0.835** · 목표 0.90 미달 | TBD | Phase 2 |
| 13 | AMD 임상 | ✅ 벤치 충족 | TBD | Phase 2 |
| 14 | Myopia 임상 (Sens≥85%) | ⚠️ 현재 80.7% | TBD | Phase 2 |
| 15 | Multidisease 스크리닝 임상 설계 | 📋 | TBD | Phase 3 |
| 16 | 병원 MOU / 파일럿 계약 | 📋 | TBD | Phase 2 |
| 17 | 환자 동의서 · 익명화 SOP | 📋 | TBD | Phase 2 |
| 18 | FHIR 임상 데이터 저장 검증 | ⚠️ export API만 | TBD | Phase 2 |
| 19 | 임상 성능 보고서 (500건+) | 📋 | TBD | Phase 3 |
| 20 | 식약처 사전 상담 예약 | 📋 | TBD | Phase 4 |
| 21 | 허가 신청 서류 패키지 | 📋 | TBD | Phase 5 |
| 22 | v10 fast/precise 모드 (임상 유연성) | ✅ API + Dashboard | TBD | Phase 1 |
| 23 | v10c 단일모델 SaMD 영향 분석 | ⚠️ GL 미달 → precise(5-model) 권장 | TBD | Phase 1 |

**완료 항목 (2026-06-10 · v10c)**

- ✅ 감사 추적 (`audit_trail` API)
- ✅ 버전 관리 (Git + ch41)
- ✅ 알고리즘 성능 문서 (AUC/QWK/Sens/Spec · ch45 §45.4)
- ✅ fast/precise comprehensive 모드
- ✅ v10c 운영: composite **0.8842** · GL AUC **0.835** (v10 0.804 대비 개선)
- ✅ ONNX export: `scripts/export_v10.py` (5-head, opset 17)
- ⚠️ fast mode: 콜드 **~6s** / 웜 **~340ms** — GL SaMD 0.90 미달 유지
- 📋 임상 데이터 500건 (병원 협력)
- 📋 IEC 62304 · ISO 14971

**범례**: ✅ 완료 · ⚠️ 부분/주의 · 📋 미착수

**참고**: `book/part7/ch45-samd-certification.md` · `CURSOR_HANDOVER.md`
