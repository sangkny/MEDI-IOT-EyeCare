#!/usr/bin/env python3
# MEDI-IOT-EyeCare/scripts/load_knowledge.py
"""
안과 의료 지식베이스 초기 문서 로드 스크립트

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        python scripts/load_knowledge.py

로드되는 문서 (5개):
  1. 당뇨망막병증(H36.0) 진단 기준 및 분류
  2. 황반변성(H35.3) 분류 및 치료 가이드
  3. 녹내장(H40.1) 진단 프로토콜
  4. ICD-10 안과 주요 코드 목록
  5. 안과 AI 진단 안전 지침 (PII 보호)
"""
import asyncio
import sys
import logging

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("load_knowledge")

# ════════════════════════════════════════════════════════════
# 초기 의료 문서 정의
# ════════════════════════════════════════════════════════════

MEDICAL_DOCUMENTS = [
    {
        "title":    "당뇨망막병증(H36.0) 진단 기준 및 분류",
        "category": "diagnosis_criteria",
        "icd_codes": ["H36.0", "H35.0"],
        "source":   "대한안과학회 당뇨망막병증 진료지침 2024",
        "content":  """
## 당뇨망막병증(Diabetic Retinopathy) 진단 기준

### 분류
당뇨망막병증은 비증식성(NPDR)과 증식성(PDR)으로 나뉩니다.

**비증식성 당뇨망막병증 (NPDR)**
- 경증(Mild): 미세동맥류(microaneurysm)만 존재
- 중등도(Moderate): 미세동맥류 외 점상출혈, 경성삼출물, 면화반 중 일부 동반
- 중증(Severe): 4사분면 점상출혈 ≥20개, 2사분면 정맥 이상, 1사분면 IRMA

**증식성 당뇨망막병증 (PDR)**
- 신생혈관(NVD/NVE), 유리체출혈, 견인성 망막박리

### 주요 소견
- 점상출혈(dot hemorrhage): 미세혈관에서 출혈
- 경성삼출물(hard exudate): 지질 단백질 침착
- 신생혈관(neovascularization): 허혈 반응으로 형성
- 황반부종(macular edema): 시력 저하의 주원인

### 치료 기준
- 경증 NPDR: 혈당 조절 + 6개월 추적
- 중등도 NPDR: 3~4개월 추적, 황반부종 시 Anti-VEGF
- 중증 NPDR: 즉시 범망막광응고술(PRP) 고려
- PDR: PRP 필수, 유리체절제술 고려

### HbA1c와 망막병증 위험도
- HbA1c < 7%: 위험도 낮음
- HbA1c 7~9%: 중등도 위험
- HbA1c > 9%: 고위험 — 즉각 안과 협진 필요
""".strip(),
    },
    {
        "title":    "황반변성(H35.3) 분류 및 치료 가이드",
        "category": "treatment",
        "icd_codes": ["H35.3", "H35.31", "H35.32"],
        "source":   "대한안과학회 황반변성 진료지침 2024",
        "content":  """
## 나이관련황반변성(AMD) 분류 및 치료

### 분류
**건성 AMD (Dry AMD, 비삼출성)**
- 드루젠(drusen): 망막하 노폐물 침착
- 지도상 위축(geographic atrophy, GA): 광수용체 손실
- 치료: 항산화 비타민(AREDS2 포뮬러) 복용

**습성 AMD (Wet AMD, 삼출성, H35.32)**
- 맥락막신생혈관(CNV): 황반하 출혈/삼출
- 급격한 시력 저하 — 응급 치료 필요
- 1차 치료: Anti-VEGF 주사(ranibizumab, bevacizumab, aflibercept)

### OCT 소견 해석
- SRF(subretinal fluid): 망막하액 — 활동성 CNV 지표
- IRF(intraretinal fluid): 망막내액 — 예후 불량 지표
- PED(pigment epithelium detachment): 색소상피박리
- EZ(ellipsoid zone) 손상: 광수용체 손상 정도

### Anti-VEGF 치료 프로토콜
- 초기 로딩: 매월 3회 주사
- 유지: PRN(필요 시) 또는 Treat-and-Extend
- 반응 평가: OCT로 액체(fluid) 소실 여부 확인

### 황반원공(H35.34)
- 전층 황반원공: 유리체절제술 + 내경계막 제거
- 층판 황반원공: 보존적 치료 후 경과 관찰
""".strip(),
    },
    {
        "title":    "녹내장(H40.1) 진단 프로토콜",
        "category": "protocol",
        "icd_codes": ["H40.0", "H40.1", "H40.2"],
        "source":   "대한녹내장학회 진료지침 2024",
        "content":  """
## 녹내장 진단 프로토콜

### 정의 및 분류
녹내장은 시신경 손상으로 시야 결손이 진행되는 질환입니다.

**개방각 녹내장 (H40.1)**
- 가장 흔한 유형 (전체 녹내장의 70%)
- 안압 상승 또는 정상 안압에서도 발생(정상안압 녹내장)
- 서서히 진행 — 말기까지 증상 없을 수 있음

**폐쇄각 녹내장 (H40.2)**
- 급성: 갑작스런 안압 상승, 두통, 구역질
- 즉각 레이저 홍채절개술(LPI) 필요

### 진단 기준
**안압 (IOP)**
- 정상: 10~21 mmHg
- 21 mmHg 초과: 고안압증
- 녹내장 의심: 24 mmHg 이상 또는 양안 차이 4 mmHg 이상

**시신경 소견 (시신경유두)**
- CDR(cup-to-disc ratio) ≥ 0.7: 이상
- 시신경유두 함몰(excavation) 진행
- RNFL(망막신경섬유층) 결손

**시야 검사 (Humphrey)**
- MD(Mean Deviation) -6dB 이하: 중기 녹내장
- MD -12dB 이하: 말기 녹내장
- Arcuate scotoma, nasal step, altitudinal defect: 특징적 패턴

### 치료
- 1차: 안압 하강 점안액(prostaglandin 유사체)
- 2차: 레이저 섬유주성형술(SLT)
- 3차: 수술(섬유주절제술, 방수유출장치)

### 추적 관찰
- 3~6개월마다 안압 측정
- 6~12개월마다 시야 검사
- 1~2년마다 시신경 OCT
""".strip(),
    },
    {
        "title":    "안과 ICD-10 주요 코드 목록",
        "category": "icd_codes",
        "icd_codes": [
            "H36.0", "H35.3", "H35.34", "H40.0", "H40.1",
            "H18.6", "H26.0", "H04.1", "H35.0",
        ],
        "source":   "WHO ICD-10 안과 코드 참조",
        "content":  """
## 안과 주요 ICD-10 코드

### 망막 질환
- H35.0: 배경 당뇨망막병증 및 망막혈관 변화
- H35.3: 황반 변성 (AMD)
  - H35.31: 비삼출성 AMD (건성)
  - H35.32: 삼출성 AMD (습성)
  - H35.33: 혈관신생망막병증
  - H35.34: 황반원공
- H36.0: 당뇨병에서의 망막 장애 (당뇨망막병증)

### 녹내장
- H40.0: 녹내장 의심 (glaucoma suspect)
- H40.1: 개방각 녹내장 (open-angle glaucoma)
- H40.2: 원발성 폐쇄각 녹내장

### 각막 질환
- H18.6: 원추각막 (keratoconus)
- H18.7: 각막 변성

### 수정체 질환
- H25: 노인성 백내장
  - H25.0: 피질 노인성 백내장
  - H25.1: 핵 노인성 백내장
- H26.0: 유아성 및 소아성 백내장

### 기타
- H04.1: 눈물막 기능 이상 (건성안/안구건조증)
- H57.9: 눈 및 눈부속기의 기타 상세불명 장애
""".strip(),
    },
    {
        "title":    "안과 AI 진단 안전 지침 및 PII 보호",
        "category": "protocol",
        "icd_codes": [],
        "source":   "MEDI-IOT EyeCare 내부 AI 안전 정책 v1.0",
        "content":  """
## 안과 AI 진단 안전 지침

### 1. PII(개인식별정보) 보호 원칙

**AI 진단 보고서에 절대 포함 금지 항목**
- 환자 이름, 주민등록번호, 생년월일
- 전화번호, 주소, 이메일
- 보험 정보, 의료 기관 정보(개인 식별 가능 시)

**PII 처리 방식**
- 저장: AES-256 암호화 (name_encrypted 컬럼)
- 표시: 첫 글자만 노출 (홍길동 → 홍**)
- 보고서: 환자 코드만 사용 (P123456)

### 2. OntologyValidator 검증 필수 항목

AI 생성 보고서는 반드시 다음을 통과해야 합니다:
- Semantic: ICD 코드 ↔ 진단명 일치
- Structural: 필수 임상 필드 존재 (검사날짜, 진단코드)
- Constraint: PII 미포함 확인
- Dependency: 진단별 필수 수치 (당뇨 → 혈당, 녹내장 → 안압)

### 3. 신뢰도 및 의사 검토 기준

| ontology_passed | confidence | 처리 |
|-----------------|------------|------|
| True | ≥ 0.85 | 자동 저장, 의사 확인 권고 |
| True | 0.6~0.85 | 저장, 의사 검토 필요 |
| False | any | 저장, 의사 필수 검토 + 재생성 고려 |

### 4. CONSENSUS 전략 권고

중증 질환(H36.0, H40.1, H35.34)은 반드시 CONSENSUS 전략을 사용하여
FAST + HEAVY 두 모델이 합의한 결과만 최종 보고서로 채택합니다.

### 5. Circuit Breaker

- 최대 2회 반복 후 현재 최선 보고서 반환
- 3회 이상 실패 시: AI 분석 불가 → 의사 수동 작성 요청
""".strip(),
    },
]


# ════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════

async def main() -> None:
    from database import AsyncSessionLocal
    from services.knowledge_base import KnowledgeBase

    log.info("=== 안과 의료 지식베이스 초기 문서 로드 ===")
    log.info(f"로드할 문서 수: {len(MEDICAL_DOCUMENTS)}개")

    async with AsyncSessionLocal() as db:
        kb = KnowledgeBase(db)

        for i, doc_data in enumerate(MEDICAL_DOCUMENTS, 1):
            log.info(f"[{i}/{len(MEDICAL_DOCUMENTS)}] {doc_data['title'][:50]}")
            try:
                doc = await kb.add_document(**doc_data)
                log.info(f"  → 완료: {doc.id[:8]}...")
            except Exception as e:
                log.error(f"  → 실패: {e}")

        await db.commit()

        # 결과 확인
        counts = await kb.count_documents()
        log.info("\n=== 로드 완료 ===")
        for cat, cnt in counts.items():
            log.info(f"  {cat}: {cnt}개")

        total = sum(counts.values())
        log.info(f"  총계: {total}개 문서")

    log.info("✅ 지식베이스 초기화 완료")


if __name__ == "__main__":
    asyncio.run(main())
