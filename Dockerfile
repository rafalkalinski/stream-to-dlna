# syntax=docker/dockerfile:1
FROM python:3.14-slim

# Install FFmpeg and apply all available security patches
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /tmp/* /var/tmp/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies with pip cache
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy example config as default (will be overridden by volume mount)
COPY config.example.yaml ./config.yaml

# Version injected at build time by CI / make / deploy.sh (see scripts/version.sh)
ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}

# Expose API port and streaming port
EXPOSE 5000 8080

# Run the application with gunicorn
# CRITICAL: --workers MUST be 1 - the streaming server and playback state live
# in-process and must not be split across workers
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "16", "--timeout", "120", "app.main:app"]
