#!/bin/bash
# Build script for DLNA Radio Streamer with version info

set -e

# Get git commit hash (short form)
BUILD_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")

# Get build date in ISO 8601 format
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Building stream-to-dlna:latest"
echo "  BUILD_HASH: ${BUILD_HASH}"
echo "  BUILD_DATE: ${BUILD_DATE}"
echo ""

# Create .env file for docker-compose
cat > .env <<EOF
BUILD_HASH=${BUILD_HASH}
BUILD_DATE=${BUILD_DATE}
EOF

echo "Created .env file with build info"

# Build using docker-compose (reads .env automatically)
docker-compose build

echo ""
echo "Build complete!"
echo "Image: stream-to-dlna:latest"
echo "Build: ${BUILD_HASH} (${BUILD_DATE})"
