# MEDI Sensitive Data Classification — MVP-04C (TB-04)

Date: 2026-09-16  
Scope: eyecare screening → MEDI clinical-screening path (+ /patients API note)

## Verdict

| Path | Identifiable patient data stored by MEDI? | TB-04 case |
|---|---|---|
| `POST /api/v1/mvp/clinical-screening` | **NO** | **CASE A** — data minimization |
| `POST /api/v1/patients` (separate) | **YES** (name field) | **CASE B** — Fernet encryption-at-rest when key set |

## Classification table (screening path)

| Field | Source | Sent to MEDI? | Stored by MEDI? | Logged? | Sensitive? | Protection | Change |
|---|---|---|---|---|---|---|---|
| patient name | eyecare Consumer | No | No | No | Yes | Not forwarded | None for MEDI |
| phone/email | eyecare Consumer | No | No | No | Yes | Not forwarded | None for MEDI |
| patient_id Form | optional | ignored | No | No | If present | Discarded | Keep ignore |
| tenant_id / location_id | JWT/org | Yes | Echo only | No | Low | Technical IDs | OK |
| image_id / trace_id | UUID | Yes / created | Echo only | On error | Low | Correlation | OK |
| fundus bytes | upload | Yes | **No** (RAM) | No | Biometric | In-memory only | Keep |
| clinical result | inference | Response | No on MEDI; Yes on eyecare | Truncated errors | Health | Role filter | OK |

## Image handling

| Path | Persistence | Cleanup |
|---|---|---|
| clinical-screening | Memory only | GC after request |
| LocalImageStorage `/images` | `/app/uploads/{patient_id}/` | Explicit delete API |

## Transport (factual)

| Hop | Protocol | TLS |
|---|---|---|
| eyecare-api → eyecare-ai-inference | HTTP docker DNS | **No** |
| inference → MEDI (`host.docker.internal:8001`) | HTTP | **No** |
| integrated-demo API bind | `127.0.0.1:8211` | N/A (local) |

**Future deployment requirement:** TLS or mTLS for any non-local eyecare↔MEDI hop. Do not claim TLS exists today.

## Encryption implementation (patients API only)

- Library: `cryptography.fernet` (AES)
- Env: `MEDI_PATIENT_ENCRYPTION_KEY` (never commit)
- Dev without key: `plaintext:dev:` marker + warning (not claimed encrypted)
- Prod/pilot/staging without key: refuse write
