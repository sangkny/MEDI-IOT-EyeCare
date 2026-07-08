"""
파일명: services/prognosis_tracker.py
목적:   녹내장 환자 예후 추적 DB 인터페이스
        시계열 안저사진 → 진행도(progression) 추적 → 예후 리포트 생성

설계 원칙:
  - entity(환자) 기반 — folder_no 또는 unit_no로 식별
  - 방문별 스냅샷 저장 (visit_snapshot)
  - AI 추론 결과 + 임상 Grade를 함께 기록
  - 진행도 판정: progression / stable / improvement
  - 향후 medi-audit-engine의 audit_events와 연동 가능한 구조

미구현 상태 (stub):
  실제 DB 연결은 medi-audit-engine 구축 후 연동 예정
  지금은 인터페이스(클래스/메서드 서명)와 스키마만 정의

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
}

PROGNOSIS_SCHEMA = """
-- 녹내장 환자 예후 추적 테이블 (향후 구현)

-- 1. 환자 엔티티 (medi-audit-engine entities 테이블과 호환)
CREATE TABLE IF NOT EXISTS gl_patients (
    patient_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folder_no       INTEGER UNIQUE,
    entity_type     VARCHAR(50) DEFAULT 'glaucoma_patient',
    diagnosis       VARCHAR(100),
    is_ntg          BOOLEAN,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 2. 방문별 스냅샷 (시계열 핵심 테이블)
CREATE TABLE IF NOT EXISTS gl_visit_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID REFERENCES gl_patients(patient_id),
    visit_idx       INTEGER,
    visit_date      DATE,
    days_from_first INTEGER,

    clinical_grade       INTEGER,
    vf_md_od             NUMERIC,
    vf_md_os             NUMERIC,
    vf_psd_od            NUMERIC,
    vf_psd_os            NUMERIC,
    oct_rnfl_od          NUMERIC,
    oct_rnfl_os          NUMERIC,
    oct_cdr_od           NUMERIC,
    oct_cdr_os           NUMERIC,

    ai_gl_prob_od        NUMERIC,
    ai_gl_prob_os        NUMERIC,
    ai_cdr_od            NUMERIC,
    ai_cdr_os            NUMERIC,
    ai_model_version     VARCHAR(50),

    fundus_file_od       VARCHAR(200),
    fundus_file_os       VARCHAR(200),

    created_at           TIMESTAMPTZ DEFAULT now()
);

-- 3. 예후 판정 이력 (append-only, audit trail과 호환)
CREATE TABLE IF NOT EXISTS gl_prognosis_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID REFERENCES gl_patients(patient_id),
    from_snapshot   UUID REFERENCES gl_visit_snapshots(snapshot_id),
    to_snapshot     UUID REFERENCES gl_visit_snapshots(snapshot_id),
    progression     VARCHAR(30),
    grade_change    INTEGER,
    vf_md_change_od NUMERIC,
    days_interval   INTEGER,
    flagged         BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 4. 예후 리포트
CREATE TABLE IF NOT EXISTS gl_prognosis_reports (
    report_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID REFERENCES gl_patients(patient_id),
    generated_at    TIMESTAMPTZ DEFAULT now(),
    report_type     VARCHAR(50),
    n_visits        INTEGER,
    observation_days INTEGER,
    overall_trend   VARCHAR(30),
    predicted_grade_1y NUMERIC,
    report_json     JSONB
);
"""


class PrognosisTracker:
    """
    녹내장 환자 예후 추적 인터페이스 (현재 stub — DB 미연결)
    향후 medi-audit-engine 연동 시 구현 예정
    """

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url
        self._stub = db_url is None

    def register_patient(
        self,
        folder_no: int,
        diagnosis: str,
        is_ntg: bool,
    ) -> str:
        """환자 등록 → patient_id 반환 (stub: UUID 생성만)"""
        raise NotImplementedError("DB 연결 후 구현 예정")

    def add_visit_snapshot(
        self,
        patient_id: str,
        visit_idx: int,
        visit_date: str,
        clinical_grade: int,
        vf_md_od: float | None,
        vf_md_os: float | None,
        oct_cdr_od: float | None,
        oct_cdr_os: float | None,
        ai_gl_prob_od: float | None,
        ai_gl_prob_os: float | None,
        ai_model_version: str,
        fundus_file_od: str,
        fundus_file_os: str,
    ) -> str:
        """방문 스냅샷 기록 → snapshot_id 반환"""
        raise NotImplementedError("DB 연결 후 구현 예정")

    def compute_progression(self, patient_id: str) -> list[dict]:
        """
        모든 방문 스냅샷 → progression 이벤트 생성
        반환: [{from_visit, to_visit, progression, grade_change, ...}]
        """
        raise NotImplementedError("DB 연결 후 구현 예정")

    def generate_report(
        self,
        patient_id: str,
        report_type: str = "summary",
    ) -> dict:
        """
        예후 리포트 생성
        report_type: 'summary' / 'clinical' / 'dsmb'
        """
        raise NotImplementedError("DB 연결 후 구현 예정")

    def load_from_timeseries_csv(self, csv_path: str) -> list[dict]:
        """
        timeseries_labels.csv → PrognosisTracker 일괄 등록
        (전처리 완료된 한국인 데이터 → DB 마이그레이션 시 사용)
        """
        raise NotImplementedError("DB 연결 후 구현 예정")

    @staticmethod
    def get_schema_sql() -> str:
        """DB 초기화용 SQL 반환"""
        return PROGNOSIS_SCHEMA
