# SVG-Analyzer 연동 계약

## 정식 스키마 식별자

정식: `eyecare-architecture-evidence/1`  
출처: SVG-Analyzer `svg_analyzer/architecture_review.py` 의 `ADAPTER_SCHEMA`

거절된 초안: `eyecare-architecture-evidence/v1`  
상태: REJECTED. 자동 매핑하지 않는다. `resolve_schema_id()`가 거절 사유를 반환한다.

## 필수 필드

```json
{
  "schema": "eyecare-architecture-evidence/1",
  "modules": [
    {
      "module_id": "…",
      "paths": ["…"],
      "owner": "…",
      "critical": true,
      "interfaces": ["http:/…"],
      "db_owns": ["…"],
      "audit_covered": true,
      "test_paths": ["tests/…"]
    }
  ],
  "edges": [
    {"source": "…", "target": "…", "kind": "declared"}
  ]
}
```

`eyecare_meta`는 선택 메타데이터다. Analyzer는 알 수 없는 최상위 키를 무시한다.

## 내보내기

- 오프라인: `services.architecture_evidence.write_offline_evidence()` → `docs/architecture-evidence.json`
- API: `GET /api/v1/clinical-support/architecture-evidence` (`clinical_audit_read`)
- 분석은 오프라인 JSON을 우선한다. 새 호스트 포트를 열지 않는다.

## 제외

환자 기록, 자격 증명, 눈가림 배정, 응답 값, 계획서 PDF 본문.

## 쓰기 금지

SVG-Analyzer는 EYECARE 임상 DB에 쓰지 않는다. 발견은 `improvement_findings`로만 제안한다.
