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

# --no-cache means every rebuild produces a full new image, and retagging
# the same name (anta-gui:v1.0) just orphans the previous one as a dangling,
# untagged image instead of removing it - those silently accumulate disk
# space across repeated deploys until the disk fills up entirely (this took
# the app down once already: 15GB disk at 100% full, 9.3GB of it reclaimable
# dangling images). `docker image prune -f` only removes dangling images,
# never anything tagged/in-use, so this is safe to run unconditionally.
echo "🧹 Cleaning up old dangling images..."
docker image prune -f

echo "🚀 Starting container..."
# $VOLUME_NAME is a named Docker volume (created automatically if missing) so
# every browser's private settings/inventory (data/users/<id>/) survives this
# script removing and rebuilding the container on every redeploy.
#
# --network host: the switches this tool talks to often sit on a management
# VLAN/subnet reachable from the host's own routing table/interfaces but NOT
# from Docker's isolated bridge network (its NAT only egresses via the
# host's default route). Host networking makes the container use the host's
# network stack directly, so it can reach anything the host can - this is
# why -p is no longer needed (the app binds straight to the host's own
# 8501). Linux-only; doesn't work this way on Docker Desktop for Mac/Windows.
docker run -d \
  --network host \
  --name $CONTAINER_NAME \
  --restart always \
  -v $VOLUME_NAME:/app/data \
  $IMAGE_NAME

echo "✅ Container restarted successfully on port 8501!"