# Build stage
FROM python:3.14-alpine3.21 AS builder

# Use Alpine Edge repositories for latest packages
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories

# Install build dependencies
RUN apk add --no-cache gcc musl-dev linux-headers

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.14-alpine3.21

# Use Alpine Edge repositories for latest packages
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories

# Install FFmpeg (runtime only) - should get latest version from Edge
RUN apk add --no-cache ffmpeg

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY app/ ./app/

# Copy default config (will be overridden by volume mount)
COPY config.yaml .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Expose API port and streaming port
EXPOSE 5000 8080

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "--timeout", "120", "app.main:app"]
