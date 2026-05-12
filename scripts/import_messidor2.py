"""Messidor-2 배치 임포트 스크립트 (D R2 Day 3, 2026-05-13).

ADCIS 의 Messidor-2 데이터셋 (1748장 fundus 사진 + DR/ME 라벨) 을 MEDI 의
``EyeImage`` 와 ``ClinicalStudyMembership`` 으로 일괄 등록한다.

데이터셋 디렉터리 레이아웃 (사용자가 별도 다운로드, 라이선스 ADCIS Free Research):
    {DATA_DIR}/
        images/
            20051019_38557_0100_PP.tif
            ...
        annotations/
            messidor_data.csv   # image_id,dr_grade,me_grade,laterality
            ...

사용법 (dev 컨테이너 내부 실행):
    docker exec -e DATA_DIR=/data/messidor2 -e STORAGE_BACKEND=local \\
        medi-iot-api-dev python scripts/import_messidor2.py --dry-run
    docker exec -e DATA_DIR=/data/messidor2 medi-iot-api-dev \\
        python scripts/import_messidor2.py --batch 100

--dry-run 모드는 디스크/S3 쓰기 없이 manifest 만 출력 (validation 용도).
S3 백엔드: ``STORAGE_BACKEND=s3`` + ``S3_BUCKET`` 환경변수 설정.

설계 결정:
    - 자체 patient_code 는 ``MSDR-{6자리}`` 로 합성 (실 환자 정보 절대 없음).
    - DR grade → ICD-10 매핑은 ``ClinicalStudy.label_schema`` (medi003 시드) 기준.
    - 중복 import 방지 — 동일 ``messidor_image_id`` 이미 등록 시 skip.
    - 큰 데이터셋이므로 ``--batch N`` 으로 progress 출력.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# config.get_settings 가 동기적이라 import 순서는 안전.
from config import get_settings  # noqa: E402
from models.clinical import (  # noqa: E402
    ClinicalStudy,
    ClinicalStudyMembership,
    StudyStatusEnum,
)
from models.medical import (  # noqa: E402
    EyeExam,
    EyeImage,
    ExamTypeEnum,
    ImageTypeEnum,
    Patient,
    ReportStatusEnum,
)
from services.image_storage import get_image_storage  # noqa: E402


# DR grade → ICD-10 (Messidor 라벨 스키마 §medi003 와 정합).
DR_TO_ICD10: dict[int, str | None] = {
    0: None,
    1: "H35.0",   # mild NPDR (background retinopathy)
    2: "H36.0",   # moderate NPDR (diabetes-related)
    3: "H36.0",
    4: "H36.0",   # PDR (proliferative)
}

DR_TO_SEVERITY: dict[int, str] = {
    0: "none",
    1: "mild",
    2: "moderate",
    3: "severe",
    4: "severe",
}


def _async_db_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


async def _get_or_create_messidor_study(s, *, dry_run: bool = False) -> ClinicalStudy:
    row = await s.scalar(select(ClinicalStudy).where(ClinicalStudy.code == "messidor-2"))
    if row is None:
        row = ClinicalStudy(
            id=str(uuid.uuid4()),
            code="messidor-2",
            name="Messidor-2",
            description="Public dataset (script-seeded).",
            license="ADCIS Free Research Use",
            image_count_total=1748,
            image_count_loaded=0,
            label_schema=json.dumps({"dr_grade": [0, 1, 2, 3, 4]}),
            status=StudyStatusEnum.DRAFT if dry_run else StudyStatusEnum.LOADING,
        )
        s.add(row)
        await s.flush()
    elif not dry_run:
        row.status = StudyStatusEnum.LOADING
        await s.flush()
    return row


async def _get_or_create_patient(s, patient_code: str) -> Patient:
    p = await s.scalar(select(Patient).where(Patient.patient_code == patient_code))
    if p is not None:
        return p
    p = Patient(
        id=str(uuid.uuid4()),
        patient_code=patient_code,
        date_of_birth=date(1960, 1, 1),
    )
    s.add(p)
    await s.flush()
    return p


def _parse_annotations(ann_csv: Path) -> list[dict]:
    """CSV header: image_id,dr_grade,me_grade,laterality."""
    rows: list[dict] = []
    with ann_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({
                    "image_id": r["image_id"].strip(),
                    "dr_grade": int(r.get("dr_grade", "0") or 0),
                    "me_grade": int(r.get("me_grade", "0") or 0),
                    "laterality": (r.get("laterality") or "OU").strip().upper(),
                })
            except (KeyError, ValueError):
                continue
    return rows


async def _import_one(
    s, *, study: ClinicalStudy, storage, ann: dict, image_path: Path,
    dry_run: bool,
) -> bool:
    """단일 이미지 등록 — 이미 존재하면 False."""
    code = f"MSDR-{ann['image_id'][:8].upper().replace('.', '')}"
    patient = await _get_or_create_patient(s, code)

    existing = await s.scalar(
        select(ClinicalStudyMembership)
        .where(ClinicalStudyMembership.study_id == study.id)
        .where(ClinicalStudyMembership.external_id == ann["image_id"])
    )
    if existing is not None:
        return False

    exam = EyeExam(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        exam_type=ExamTypeEnum.FUNDUS,
        exam_date=date.today(),
        raw_findings=f"Messidor-2 ground-truth: DR={ann['dr_grade']} ME={ann['me_grade']}",
        report_status=ReportStatusEnum.PENDING,
    )
    s.add(exam)
    await s.flush()

    if dry_run:
        file_path = f"DRYRUN/{patient.id}/{ann['image_id']}"
        file_size = 0
    else:
        data = image_path.read_bytes()
        file_size = len(data)
        file_path = await storage.save(
            data,
            patient_id=patient.id,
            filename_hint=image_path.name,
        )

    img = EyeImage(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        exam_id=exam.id,
        image_type=ImageTypeEnum.FUNDUS,
        file_path=file_path,
        file_name=image_path.name,
        file_size=file_size,
        mime_type="image/tiff" if image_path.suffix.lower() in {".tif", ".tiff"} else "image/jpeg",
        analyzed=False,
    )
    s.add(img)
    await s.flush()

    icd10 = DR_TO_ICD10.get(ann["dr_grade"])
    severity = DR_TO_SEVERITY.get(ann["dr_grade"], "none")
    ground_truth = json.dumps(
        {
            "dr_grade": ann["dr_grade"],
            "me_grade": ann["me_grade"],
            "laterality": ann["laterality"],
            "icd10": icd10,
            "severity": severity,
            "source": "messidor-2",
        },
        ensure_ascii=False,
    )

    mem = ClinicalStudyMembership(
        id=str(uuid.uuid4()),
        study_id=study.id,
        image_id=img.id,
        external_id=ann["image_id"],
        ground_truth_icd=icd10,
        ground_truth_severity=severity,
        ground_truth_meta_json=ground_truth,
        created_at=datetime.now(timezone.utc),
    )
    s.add(mem)
    study.image_count_loaded = (study.image_count_loaded or 0) + 1
    return True


async def run(args) -> int:
    data_dir = Path(args.data_dir).expanduser().resolve()
    annotations_csv = data_dir / "annotations" / "messidor_data.csv"
    images_dir = data_dir / "images"

    if not annotations_csv.exists():
        print(f"[messidor2] annotations csv not found: {annotations_csv}", file=sys.stderr)
        return 2
    if not images_dir.exists() and not args.dry_run:
        print(f"[messidor2] images dir not found: {images_dir}", file=sys.stderr)
        return 2

    annotations = _parse_annotations(annotations_csv)
    if args.limit:
        annotations = annotations[: args.limit]
    if not annotations:
        print("[messidor2] no annotation rows parsed.", file=sys.stderr)
        return 3

    storage = get_image_storage()
    print(
        f"[messidor2] start — dry_run={args.dry_run} backend={getattr(storage, 'backend_id', '?')} "
        f"n_total={len(annotations)} batch={args.batch}"
    )

    url = _async_db_url()
    eng = create_async_engine(url, poolclass=NullPool)
    SM = async_sessionmaker(eng, expire_on_commit=False)

    imported = 0
    skipped = 0
    failed = 0
    try:
        async with SM() as s:
            study = await _get_or_create_messidor_study(s, dry_run=args.dry_run)
            await s.commit()

        for i in range(0, len(annotations), args.batch):
            chunk = annotations[i : i + args.batch]
            async with SM() as s:
                study = await s.scalar(
                    select(ClinicalStudy).where(ClinicalStudy.code == "messidor-2")
                )
                for ann in chunk:
                    image_path = images_dir / ann["image_id"]
                    try:
                        ok = await _import_one(
                            s,
                            study=study,
                            storage=storage,
                            ann=ann,
                            image_path=image_path,
                            dry_run=args.dry_run,
                        )
                        if ok:
                            imported += 1
                        else:
                            skipped += 1
                    except FileNotFoundError:
                        skipped += 1
                    except Exception as e:
                        print(f"[messidor2] failed {ann['image_id']}: {e}", file=sys.stderr)
                        failed += 1
                await s.commit()
            print(
                f"[messidor2] progress imported={imported} skipped={skipped} failed={failed}/{len(annotations)}"
            )

        async with SM() as s:
            study = await s.scalar(
                select(ClinicalStudy).where(ClinicalStudy.code == "messidor-2")
            )
            if not args.dry_run and (study.image_count_loaded or 0) >= 1:
                study.status = StudyStatusEnum.READY
            await s.commit()
    finally:
        await eng.dispose()

    print(
        f"[messidor2] done — imported={imported} skipped={skipped} failed={failed} dry_run={args.dry_run}"
    )
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Messidor-2 batch importer (D R2 Day 3)")
    p.add_argument("--data-dir", default="/data/messidor2",
                   help="Messidor-2 root (images/, annotations/messidor_data.csv)")
    p.add_argument("--batch", type=int, default=100)
    p.add_argument("--limit", type=int, default=0, help="0 = no cap")
    p.add_argument("--dry-run", action="store_true",
                   help="parse + DB schema only, no image bytes written")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(run(args)))
