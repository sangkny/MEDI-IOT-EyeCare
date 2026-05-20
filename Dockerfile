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

# GPU torch 먼저 설치 (CPU 버전 덮어쓰기 방지)
RUN pip install torch==2.6.0 torchvision \
    --index-url https://download.pytorch.org/whl/cu124 \
    --no-cache-dir --prefix=/install

# 나머지 의존성 설치
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

ENV PYTHONPATH="/app/shared-libraries:/app"
ENV PYTHONUNBUFFERED=1

COPY . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
