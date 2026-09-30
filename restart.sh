#!/bin/bash

# Define container and image names
CONTAINER_NAME="anta-web-gui"
IMAGE_NAME="anta-gui:v1.0"
VOLUME_NAME="anta-web-gui-data"

echo "🛑 Stopping and removing existing container ($CONTAINER_NAME)..."
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

echo "🏗️ Building the Docker image..."
docker build --no-cache -t $IMAGE_NAME .

echo "🚀 Starting container..."
# $VOLUME_NAME is a named Docker volume (created automatically if missing) so
# every browser's private settings/inventory (data/users/<id>/) survives this
# script removing and rebuilding the container on every redeploy.
docker run -d \
  -p 8501:8501 \
  --name $CONTAINER_NAME \
  --restart always \
  -v $VOLUME_NAME:/app/data \
  $IMAGE_NAME

echo "✅ Container restarted successfully on port 8501!"