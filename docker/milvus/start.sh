#!/bin/bash

# Milvus Standalone Startup Script
# https://milvus.io/docs/install_standalone-docker.md

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed."
        exit 1
    fi
}

main() {
    log_info "Starting Milvus Standalone..."
    check_docker

    if docker ps | grep -q "milvus-standalone.*healthy"; then
        log_info "Milvus is already running!"
        show_status
        exit 0
    fi

    docker compose up -d
}

show_status() {
    echo ""
    log_info "Endpoints:"
    echo "  📡 gRPC:   localhost:19530"
    echo "  🌐 WebUI:  http://localhost:9091/webui/"
    echo "  🔧 etcd:   localhost:2379"
    echo ""
    log_info "Commands:"
    echo "  Stop:   ./stop.sh"
    echo "  Reset:  ./reset.sh"
    echo "  Logs:   docker logs -f milvus-standalone"
}

main "$@"
