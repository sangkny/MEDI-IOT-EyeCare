# Dashboard 브라우저 E2E 수동 확인 체크리스트

> 최종 업데이트: 2026-06-11  
> 자동: `dashboard/scripts/check-portal-e2e.mjs` · SSOT: `projects/PORT-ALLOCATION.md`

## 사전 조건

| 항목 | URL / 명령 |
|------|------------|
| MEDI API | `http://localhost:8001/health` |
| Dashboard (Vite) | `http://localhost:5174` — **Windows**에서 `npm run dev` |
| LM Studio | `192.168.0.12:1234` (보고서 생성 시) |
| SVG-Stock | **중지** (8000 충돌 방지) |

```bash
cd projects
docker compose -f docker-compose.dev.yml ps | grep -E "medi-iot|dashboard"
node dashboard/scripts/check-portal-e2e.mjs
```

---

## Portal — Fundus Upload

**URL**: http://localhost:5174/dashboard/portal/fundus/upload

- [ ] 이미지 드래그앤드롭 업로드 (OD / OS 각각)
- [ ] Fast 모드 분석 (~6초)
- [ ] **ComprehensiveCard** 5질환 표시
  - [ ] DR grade=0 APPROVE
  - [ ] Glaucoma prob≈0.605 **REVISE** (주황색)
  - [ ] AMD / MYO APPROVE
  - [ ] Screening findings
- [ ] **overall_assessment**
  - [ ] `primary_concern=glaucoma`
  - [ ] `urgency=routine`
- [ ] `inference_mode=fast(v10)` 표시
- [ ] `inference_time_ms` 표시
- [ ] GradCAM 슬라이더 동작
- [ ] **BilateralView** 좌/우안 전환
- [ ] **Fast ↔ Precise** 토글
  - [ ] Precise: GL **APPROVE** (glaucoma_v2 독립모델)
  - [ ] 응답시간 ~42초 · 진행 오버레이
- [ ] **보고서 생성** 버튼 (AutoNoGaDa · `POST /api/v1/lab/fundus/report`)

---

## Admin — Models

**URL**: http://localhost:5174/dashboard/admin/models

- [ ] v10c 카드 (`composite=0.8842`)
- [ ] 독립 5모델 카드 (DR v4 · GL v2 · AMD · MYO · Multi)
- [ ] **운영중** 배지

---

## 자동 E2E 기대값 (`check-portal-e2e.mjs`)

| 모드 | GL decision | 비고 |
|------|-------------|------|
| fast | REVISE | v10c |
| precise | APPROVE | glaucoma_v2 |
