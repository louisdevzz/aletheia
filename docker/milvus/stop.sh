#!/bin/bash
# Milvus Stop Script
set -e
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[INFO] Stopping Milvus..."
docker compose down
echo "[INFO] Milvus stopped. Data preserved in Docker volume 'milvus-data'"
echo "[INFO] To view volumes: docker volume ls | grep milvus"
