"""합성 SQLite로 증례 대시보드만 띄운다. 전체 API 패키지는 불러오지 않는다."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path(r"C:\Tools\downloads\phase005-inspect\shared-libraries")
sys.path.insert(0, str(ROOT))
if SHARED.is_dir():
    sys.path.insert(0, str(SHARED))

from auth.jwt_handler import create_access_token
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from database import Base, get_db
from tests.test_clinical_case_dashboard import _TABLES, _seed

DB = ROOT / "data" / "synthetic-case-dashboard.sqlite"
DB.parent.mkdir(exist_ok=True)
if DB.exists():
    DB.unlink()
sync_engine = create_engine(f"sqlite:///{DB}")
event.listen(sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
Base.metadata.create_all(sync_engine, tables=_TABLES)
session = Session(sync_engine)
study, site, _first, _draft = _seed(session)
port = int(os.environ.get("DASHBOARD_PORT", "8766"))
print("DASHBOARD READY", flush=True)
print(f"URL: http://127.0.0.1:{port}/clinical-dashboard", flush=True)
print(f"STUDY: {study.id}", flush=True)
print(f"SITE: {site.id}", flush=True)
print(f"TOKEN: {create_access_token(subject='doc', role='doctor')}", flush=True)
print("Ctrl+C 로 종료합니다.", flush=True)
session.close()
sync_engine.dispose()

spec = importlib.util.spec_from_file_location("clinical_dashboard_api", ROOT / "api" / "clinical_dashboard.py")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
engine = create_async_engine(f"sqlite+aiosqlite:///{DB}")
factory = async_sessionmaker(engine, expire_on_commit=False)


async def _db():
    async with factory() as db:
        yield db


app = FastAPI()
app.include_router(module.page_router)
app.include_router(module.router, prefix="/api/v1/clinical-support")
app.dependency_overrides[get_db] = _db


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
