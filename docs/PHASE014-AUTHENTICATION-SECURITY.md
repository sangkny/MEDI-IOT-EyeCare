# PHASE 014 — Authentication & Frontend Security

## 설계

- 인증 백엔드 신규 없음. `POST /api/v1/auth/token` 재사용.
- JWT는 `ClinicalOpsSession` 메모리에만 보관. `localStorage` / `sessionStorage` 미사용.
- URL·콘솔·에러 메시지에 토큰/비밀번호를 넣지 않음.
- 로그인 실패 시 password 입력 필드를 즉시 비움.

## 세션 종료·만료

401/403 또는 로그아웃 시:

1. `clearSensitive()` — token/user/role/scope 제거
2. `requestSeq` 증가 — 진행 중 fetch 결과를 STALE로 버림
3. 패널 DOM의 임상 표시 내용 제거
4. 로그인 화면으로 복귀

## 권한

- UI 내비 가시성은 UX용. 실제 ACL은 서버 `policy_require` + study/site membership.
- Audit 읽기: `clinical_audit_read`
- Query/Lock: 기존 clinical_* 정책 그대로

## 새로고침

메모리 JWT이므로 새로고침 후 재로그인 필요. 이는 의도된 복구 경로이다.

## 2026-10-31 KST completion notes

- `clearSensitive()`는 in-flight 무효화를 위해 `requestSeq`만 증가시키며, 이후 정상 API 호출을 영구 차단하지 않는다.
- Playwright: storage에 JWT 없음; expired JWT → AUTH + token clear 확인.
- Lock unlock 승인 UI는 기존 `/locks/unlock-requests/{id}/approvals|rejections`만 호출한다 (전자서명 없음).
