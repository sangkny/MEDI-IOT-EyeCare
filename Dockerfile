# ============================================================
# MEDI-IOT EyeCare — Dockerfile (Multi-stage)
# ============================================================
# Stage 1: builder — 의존성 설치
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# shared-libraries 의존성 먼저 설치 (볼륨 마운트 전 빌드 시점)
# 실제 파일은 볼륨 마운트로 주입됨
COPY shared-libs-requirements.txt ./shared-libs-requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    -r shared-libs-requirements.txt \
    -r requirements.txt

# ============================================================
# Stage 2: runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# builder에서 설치된 패키지 복사
COPY --from=builder /install /usr/local

# shared-libraries는 볼륨 마운트로 주입됨 (/app/shared-libraries)
# PYTHONPATH에 추가하여 `from llm.client import ...` 사용 가능
ENV PYTHONPATH="/app/shared-libraries:/app"
ENV PYTHONUNBUFFERED=1

# 앱 소스 복사 (볼륨 마운트로 덮어써짐 — 이미지 내 fallback용)
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
