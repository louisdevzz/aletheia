#!/bin/bash
# Start all Aletheia services in correct order

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 1. Start Elasticsearch
log_step "Starting Elasticsearch..."
if [ ! "$(docker ps -q -f name=elasticsearch 2>/dev/null)" ]; then
    ./docker/elasticsearch/start.sh
fi

# 2. Start Milvus
log_step "Starting Milvus..."
if [ ! "$(docker ps -q -f name=milvus-standalone 2>/dev/null)" ]; then
    ./docker/milvus/start.sh
fi

# 3. Wait for backend services
log_step "Waiting for backend services..."
until curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo " ✅ ES ready"

# 4. Start Aletheia Daemon
log_step "Starting Aletheia Daemon..."
if lsof -ti:8000 > /dev/null 2>&1; then
    log_info "Daemon already running on port 8000"
else
    nohup uv run aletheia daemon --host 0.0.0.0 --port 8000 > /tmp/aletheia.log 2>&1 &
    
    # Wait for daemon
    log_info "Waiting for daemon to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
            echo " ✅ Daemon ready"
            break
        fi
        echo -n "."
        sleep 1
    done
fi

# 5. Start Web Frontend
log_step "Starting Web Frontend..."
cd web
if lsof -ti:3000 > /dev/null 2>&1; then
    log_info "Web already running on port 3000"
else
    nohup pnpm dev > /tmp/web.log 2>&1 &
    log_info "Web starting on http://localhost:3000"
fi

echo ""
log_info "========================================"
log_info "🎉 All services started!"
log_info "========================================"
echo ""
echo "  🔗 Web UI:    http://localhost:3000"
echo "  🔌 API:       http://localhost:8000"
echo "  📊 ES:        http://localhost:9200"
echo "  🧠 Milvus:    http://localhost:19530"
echo ""
echo "  Logs:"
echo "    Daemon:    tail -f /tmp/aletheia.log"
echo "    Web:       tail -f /tmp/web.log"
