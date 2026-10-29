"""Docker 내부 JWT 설문 흐름. 호스트 포트를 열지 않는다."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.clinical_records import add_site, add_site_member, create_study, enroll_subject, open_visit
from services.protocol_ecrf import register_protocol

BASE = "http://127.0.0.1:8000"
PG = "postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare"
SHA110 = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"
_RUN = datetime.now(timezone.utc).strftime("%H%M%S")


def token(username: str, password: str) -> str:
    body = urllib.parse.urlencode({"username": username, "password": password}).encode()
    payload = json.load(urllib.request.urlopen(
        urllib.request.Request(BASE + "/api/v1/auth/token", data=body), timeout=20,
    ))
    return payload["access_token"]


def call(path: str, *, method: str = "GET", token_value: str | None = None, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {}
    if token_value:
        headers["Authorization"] = f"Bearer {token_value}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"raw": raw}
        return exc.code, detail


def main() -> None:
    html = urllib.request.urlopen(BASE + "/questionnaire", timeout=10)
    page_body = html.read(200).decode("utf-8", errors="replace")
    print("PAGE", html.status, "html" if "<" in page_body else "other")
    assert html.status == 200

    noauth = call("/api/v1/clinical-support/architecture-evidence")[0]
    print("NOAUTH", noauth)
    assert noauth in {401, 403}
    doctor = token("doctor", "doc123")
    manager = token("manager", "mgr123")
    manager_status = call("/api/v1/clinical-support/architecture-evidence", token_value=manager)[0]
    print("MANAGER_EVIDENCE", manager_status)
    assert manager_status == 403

    engine = create_engine(PG)
    with Session(engine) as session:
        study = create_study(session, code=f"SYN-JWT-Q-{_RUN}", name="jwt questionnaire")
        site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id="doctor")
        add_site_member(session, site_id=site.id, user_id="doctor", role="doctor", actor_user_id="doctor")
        outsider = add_site(session, study_id=study.id, site_code="S2", name="Other", actor_user_id="doctor")
        add_site_member(session, site_id=outsider.id, user_id="staff", role="staff", actor_user_id="doctor")
        subject = enroll_subject(
            session, study_id=study.id, site_id=site.id, subject_code=f"SYN-JWT-{_RUN}", actor_user_id="doctor",
        )
        visit = open_visit(
            session, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 2), actor_user_id="doctor",
        )
        document = register_protocol(
            session, study_id=study.id, site_id=site.id, actor_user_id="doctor", actor_role="doctor",
            version_label="1.10", source_sha256=SHA110, document_date="2026-07-01",
            source_present=True, source_reference="local protocol pdf",
        )
        session.commit()
        study_id, site_id, visit_id, document_id = study.id, site.id, visit.id, document.id
        outsider_id = outsider.id

    status, draft = call(
        f"/api/v1/clinical-support/studies/{study_id}/questionnaire-drafts",
        method="POST", token_value=doctor,
        payload={"site_id": site_id, "document_id": document_id},
    )
    print("DRAFT", status, draft.get("lifecycle"), draft.get("item_count"))
    assert status == 200, draft

    cross = call(
        f"/api/v1/clinical-support/studies/{study_id}/questionnaire-stats?site_id={outsider_id}",
        token_value=doctor,
    )[0]
    print("CROSS_SITE", cross)
    assert cross == 403

    status, response = call(
        "/api/v1/clinical-support/questionnaire-engine/responses",
        method="POST", token_value=doctor,
        payload={"version_id": draft["version_id"], "visit_id": visit_id},
    )
    print("RESPONSE", status, response.get("status"))
    assert status == 200, response
    response_id = response["id"]

    for index in range(1, 6):
        status, _ = call(
            f"/api/v1/clinical-support/questionnaire-engine/responses/{response_id}/items",
            method="POST", token_value=doctor,
            payload={"item_code": f"OSQ{index}", "value": 2, "reason": "synthetic"},
        )
        assert status == 200, status
    for index in range(6, 13):
        status, _ = call(
            f"/api/v1/clinical-support/questionnaire-engine/responses/{response_id}/items",
            method="POST", token_value=doctor,
            payload={"item_code": f"OSQ{index}", "value": "NA", "reason": "synthetic"},
        )
        assert status == 200, status

    status, finalized = call(
        f"/api/v1/clinical-support/questionnaire-engine/responses/{response_id}/finalize",
        method="POST", token_value=doctor,
    )
    print("FINALIZE", status, finalized.get("status"))
    assert status == 200, finalized

    status, score = call(
        f"/api/v1/clinical-support/questionnaire-engine/responses/{response_id}/score",
        method="POST", token_value=doctor,
    )
    print("SCORE", status, score.get("status"), score.get("answered_count"), score.get("not_applicable_count"))
    assert status == 200, score
    assert score["answered_count"] == 5
    assert score["not_applicable_count"] == 7

    status, stats = call(
        f"/api/v1/clinical-support/studies/{study_id}/questionnaire-stats?site_id={site_id}",
        token_value=doctor,
    )
    print("STATS", status, stats.get("denominator_responses"), stats.get("score_distributions", {}).get("combined"))
    assert status == 200, stats

    status, evidence = call("/api/v1/clinical-support/architecture-evidence", token_value=doctor)
    print("EVIDENCE", status, evidence.get("schema"), len(evidence.get("modules", [])))
    assert status == 200, evidence
    assert evidence["schema"] == "eyecare-architecture-evidence/1"
    print("JWT_FLOW_OK")


if __name__ == "__main__":
    main()
