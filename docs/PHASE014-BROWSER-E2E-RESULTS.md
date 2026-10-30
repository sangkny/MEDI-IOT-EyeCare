# PHASE 014 — Browser E2E Results

## Environment (completion validation)

| 항목 | 값 |
| --- | --- |
| Timestamp (KST) | 2026-10-30 (PC2 completion run; see docker log) |
| Host | SVG-SKLEE (PC2) |
| Worktree | `C:\Office_Automation\MEDI-IOT-EyeCare-ops-014` |
| Branch | `feat/clinical-operations-ui-014` @ `aff373ae1c3a807e91cba69ae88cd65689f2dba8` |
| Docker net | `ops014c-net` (internal only; **no host port publish**) |
| App image | `python:3.12-slim` + uvicorn `:8000` internal |
| DB | `pgvector/pgvector:pg15` → Alembic head `medi012_questionnaire_engine` |
| Seed | `scripts/seed_ops014_synthetic.py` → `docs/ops014-seed-manifest.json` (2× unique suffix runs) |
| Browser | Playwright Chromium |
| Unit/regression | **91 passed** |
| Seeded + shell E2E | **13 passed** (`test_clinical_ops_seeded_playwright.py` 9 + `test_clinical_ops_playwright_e2e.py` 4) |

## Synthetic seed design

- DES: study/site/subject/visit, TBUT+Schirmer finalized, OSDI draft version, eCRF schema, resolved query history, Schirmer lock `READY_FOR_REVIEW`
- AMD: DRAFT schema BCVA/OCT/STUDY_EYE, **no OSDI**, unresolved conflicts retained, `rules_active=false`
- Codes: `MEDI-DES-001-{suffix}` / `MEDI-AMD-001-{suffix}` — unique per seed; second seed confirms no UniqueViolation

## Workflow matrix (browser unless noted)

| # | Workflow | Result |
| --- | --- | --- |
| 1 | Valid login | PASS |
| 2 | Invalid login | PASS |
| 3 | JWT expiration | PASS |
| 4 | Logout + clear | PASS |
| 5 | Role-aware nav | PASS |
| 6 | Study/site select | PASS |
| 7 | DES eCRF | PASS |
| 8 | DES OSDI entry | PASS |
| 9 | OSDI save/correct/score | PASS |
| 10 | AMD BCVA/OCT form access | PASS |
| 11 | AMD OSDI absence | PASS |
| 12 | Query create | PASS |
| 13 | Query response + close | PASS |
| 14 | Lock apply / unlock request+approve | PASS |
| 15 | Locked-record edit rejection | PASS |
| 16 | Audit Trail read | PASS |
| 17 | Unauthorized audit/cross-study | PASS |
| 18–19 | Cross-site denial | PASS |
| 20 | 401/403 clear | PASS (harness + browser) |
| 21 | Stale/race protection | PASS |
| 22 | Refresh → re-login | PASS |

## Audit integrity (browser-visible)

- Labels only: `HASH_CHAINED` / `EVENT_HASH_ONLY` / `LEGACY_HASH_ONLY`
- No blanket cryptographic-coverage claim in UI
- Lock/query actions use existing append-only audit services

## Logs

- `docs/ops014-completion-docker-log.txt`
- `docs/ops014-seed-manifest.json` (synthetic IDs only)
