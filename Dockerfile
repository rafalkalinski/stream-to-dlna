FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy default config (will be overridden by volume mount)
COPY config.yaml .

# Expose API port and streaming port
EXPOSE 5000 8080

# Run the application
CMD ["python", "-m", "app.main"]
