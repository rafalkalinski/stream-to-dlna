# syntax=docker/dockerfile:1
FROM python:3.14-slim

# Build arguments for versioning
ARG BUILD_HASH=dev
ARG BUILD_DATE=unknown

# Set as environment variables for runtime access
ENV BUILD_HASH=${BUILD_HASH}
ENV BUILD_DATE=${BUILD_DATE}

# Install FFmpeg with BuildKit cache mount for faster rebuilds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
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

# Expose API port and streaming port
EXPOSE 5000 8080

# Run the application with gunicorn
# CRITICAL: --workers MUST be 1 to prevent race conditions with state file
# See config.example.yaml performance.gunicorn_workers for details
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app.main:app"]
