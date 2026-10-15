#!/bin/bash
# CutStock Docker-Image bauen und auf Unraid deployen
set -e

cd "$(dirname "$0")"

VERSION=$(cat VERSION)
IMAGE="cutstock:${VERSION}"
UNRAID="root@10.10.20.20"
CONTAINER="cutstock"
DATA_DIR="/mnt/user/appdata/cutstock"

echo "==> Baue Docker-Image ${IMAGE} (linux/amd64) ..."
docker build --platform linux/amd64 -t "${IMAGE}" .

echo "==> Übertrage Image auf Unraid ..."
docker save "${IMAGE}" | ssh "${UNRAID}" 'docker load'

echo "==> Starte Container auf Unraid ..."
ssh "${UNRAID}" bash -s <<REMOTE
  docker stop ${CONTAINER} 2>/dev/null || true
  docker rm ${CONTAINER} 2>/dev/null || true
  mkdir -p ${DATA_DIR}
  docker run -d \
    --name ${CONTAINER} \
    --restart unless-stopped \
    -p 8420:8000 \
    -v ${DATA_DIR}:/data \
    ${IMAGE}
  echo "==> CutStock ${VERSION} läuft auf Port 8420"
REMOTE
