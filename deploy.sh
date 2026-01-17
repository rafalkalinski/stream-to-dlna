#!/bin/bash

# Update the local repository with changes from the remote server
echo "Running git pull..."
git pull

# Check if the previous command was successful
if [ $? -eq 0 ]; then
    echo "Git pull successful. Building Docker image with version info..."

    # Get git commit hash and build date
    BUILD_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
    BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "  BUILD_HASH: ${BUILD_HASH}"
    echo "  BUILD_DATE: ${BUILD_DATE}"
    echo ""

    # Build the docker images with build arguments
    sudo docker compose build \
        --build-arg BUILD_HASH="${BUILD_HASH}" \
        --build-arg BUILD_DATE="${BUILD_DATE}"

    if [ $? -eq 0 ]; then
        echo ""
        echo "Build successful!"
        echo "Image built with: ${BUILD_HASH} @ ${BUILD_DATE}"
    else
        echo "Docker build failed!"
        exit 1
    fi
else
    echo "Git pull failed. Aborting build."
    exit 1
fi

echo "Process completed."
