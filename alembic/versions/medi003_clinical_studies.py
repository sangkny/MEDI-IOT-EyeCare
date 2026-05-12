"""medi003 — 임상 연구 코호트 + 의사 검토 큐 + Messidor-2 시드 (D 트랙, 2026-05-12).

신규 테이블:
    - ``clinical_studies`` — 외부/내부 데이터셋 메타 (라이선스/출처/스키마)
    - ``clinical_study_memberships`` — 이미지 ↔ 연구 매핑 + ground-truth 라벨
    - ``diagnosis_reviews`` — Diagnosis 의 의사 검토 큐 (1:1 sidecar)

설계 결정 — column type 으로 PostgreSQL ENUM 대신 ``String`` 을 사용한다:
ENUM 타입 추가/변경이 까다롭고, app-level (Pydantic + Python Enum) 검증이 이미
충분하다. ORM 에서도 ``SAEnum`` 대신 ``String(N)`` + Python Enum 으로 표현 가능.

시드:
    Messidor-2 메타 한 행 (라이선스: ADCIS Free Research Use,
    이미지 다운로드는 ADCIS 사이트 수동 신청 — 백로그).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi003_clinical_studies"
down_revision: Union[str, None] = "c45bcf9c73f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clinical_studies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("license", sa.String(length=64), nullable=True),
        sa.Column(
            "image_count_total", sa.Integer(), nullable=False,
            server_default="0",
        ),
        sa.Column(
            "image_count_loaded", sa.Integer(), nullable=False,
            server_default="0",
        ),
        sa.Column("label_schema_json", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_clinical_studies_code"),
    )
    op.create_index("ix_clinical_studies_code", "clinical_studies", ["code"])
    op.create_index("ix_clinical_studies_status", "clinical_studies", ["status"])

    op.create_table(
        "clinical_study_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("image_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("ground_truth_icd", sa.String(length=16), nullable=True),
        sa.Column("ground_truth_severity", sa.String(length=20), nullable=True),
        sa.Column("ground_truth_meta_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["study_id"], ["clinical_studies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["eye_images.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_study_memberships_study_id",
        "clinical_study_memberships", ["study_id"],
    )
    op.create_index(
        "ix_study_memberships_image_id",
        "clinical_study_memberships", ["image_id"],
    )

    op.create_table(
        "diagnosis_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status", sa.String(length=24), nullable=False,
            server_default="pending_review",
        ),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "diagnosis_id", name="uq_diagnosis_reviews_diagnosis_id"
        ),
    )
    op.create_index(
        "ix_diagnosis_reviews_status",
        "diagnosis_reviews", ["status"],
    )

    op.execute(
        """
        INSERT INTO clinical_studies (
            id, code, name, description, source_url, license,
            image_count_total, image_count_loaded, label_schema_json, status,
            created_at, updated_at
        ) VALUES (
            '11111111-1111-4111-8111-111111111111',
            'messidor-2',
            'Messidor-2',
            'Public dataset for diabetic retinopathy detection. 1748 fundus '
            'photographs of 874 examinations, graded for DR (0-4) and '
            'macular edema (0-2). Used for AI eye-disease research worldwide.',
            'https://www.adcis.net/en/third-party/messidor2/',
            'ADCIS Free Research Use',
            1748, 0,
            '{"dr_grade": [0, 1, 2, 3, 4], "me_grade": [0, 1, 2], '
            '"icd10_map": {"0": null, "1": "H35.0", "2": "H36.0", '
            '"3": "H36.0", "4": "H36.0"}}',
            'draft',
            now(), now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM clinical_studies WHERE code = 'messidor-2'")
    op.drop_index("ix_diagnosis_reviews_status", table_name="diagnosis_reviews")
    op.drop_table("diagnosis_reviews")
    op.drop_index(
        "ix_study_memberships_image_id", table_name="clinical_study_memberships"
    )
    op.drop_index(
        "ix_study_memberships_study_id", table_name="clinical_study_memberships"
    )
    op.drop_table("clinical_study_memberships")
    op.drop_index("ix_clinical_studies_status", table_name="clinical_studies")
    op.drop_index("ix_clinical_studies_code", table_name="clinical_studies")
    op.drop_table("clinical_studies")
