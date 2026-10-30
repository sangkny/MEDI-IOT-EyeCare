from __future__ import annotations

import json
from pathlib import Path

from services.architecture_evidence import CANONICAL_SCHEMA, build_architecture_evidence, validate_evidence

payload = build_architecture_evidence(
    test_results={
        "phase014_unit_regression": "91_passed",
        "phase014_browser_e2e": "10_passed",
        "migration_head": "medi012_questionnaire_engine",
    }
)
errors = validate_evidence(payload)
out = Path("docs/architecture-evidence-014.json")
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("SCHEMA", payload["schema"], payload["schema"] == CANONICAL_SCHEMA)
print("MODULES", len(payload["modules"]))
print("VALIDATE", errors or "OK")
print("WROTE", out)
