#!/bin/bash
# Elasticsearch Stop Script
set -e
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[INFO] Stopping Elasticsearch..."
docker compose --profile kibana down 2>/dev/null || docker compose down
echo "[INFO] Elasticsearch stopped. Data preserved in Docker volume 'es-data'"
echo "[INFO] To view volumes: docker volume ls | grep es-data"
