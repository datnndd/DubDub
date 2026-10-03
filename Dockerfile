# ============================================================
# pyVideoTrans (DubDub) WebUI Dockerfile
#
# CPU:  docker build -t pyvideotrans-webui .
# GPU:  docker build --build-arg USE_CUDA=true -t pyvideotrans-webui:gpu .
# ============================================================

# Global build argument to toggle CUDA support (false = CPU, true = GPU)
ARG USE_CUDA=false

# Stage 1: Build modern frontend assets with Bun
FROM oven/bun:1 AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build

# Base stages corresponding to USE_CUDA boolean values
FROM python:3.10-slim AS base-false
FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04 AS base-true

# Dynamically inherit the base image according to USE_CUDA
FROM base-${USE_CUDA} AS final-base

# Re-declare ARG in this stage so it is accessible in RUN instructions
ARG USE_CUDA

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV FONTCONFIG_PATH=/etc/fonts

WORKDIR /app

# Install system dependencies, fonts, and static ffmpeg binaries
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig fonts-noto-cjk fonts-liberation fonts-dejavu wget \
    xz-utils git libglib2.0-0 libgl1 libsm6 libxext6 libxrender-dev \
    libsndfile1 python3 python3-dev python-is-python3 rubberband-cli libsndfile1-dev \
    && (which python >/dev/null 2>&1 || ln -s $(which python3) /usr/local/bin/python) \
    && wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -Jxf ffmpeg-release-amd64-static.tar.xz \
    && cp ffmpeg-*-static/ffmpeg /usr/local/bin/ \
    && cp ffmpeg-*-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy dependency specification first to leverage Docker layer caching
COPY pyproject.toml ./

# Install Python dependencies based on runtime target (CUDA vs CPU)
RUN if [ "${USE_CUDA}" = "true" ]; then \
        echo ">>> Installing dependencies for CUDA (GPU)..." && \
        uv pip install --system torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128 && \
        uv pip install --system nvidia-cublas-cu12 nvidia-cudnn-cu12 && \
        uv pip install --system -r pyproject.toml; \
    else \
        echo ">>> Installing dependencies for CPU..." && \
        uv pip install --system torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu && \
        uv pip install --system -r pyproject.toml; \
    fi && \
    rm -rf /root/.cache/uv /tmp/*

# Copy application source code and built frontend distribution
COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist

EXPOSE 7860

CMD ["python", "webui.py", "--host", "0.0.0.0", "--port", "7860"]
