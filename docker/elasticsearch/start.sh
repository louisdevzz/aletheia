#!/bin/bash

# Elasticsearch Single Node Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed."
        exit 1
    fi
}

check_requirements() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        local max_map_count
        max_map_count=$(sysctl vm.max_map_count 2>/dev/null | awk '{print $3}' || echo "0")
        if [ "$max_map_count" -lt 262144 ]; then
            log_warn "vm.max_map_count is $max_map_count (recommended: 262144)"
            read -p "Set it now? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sudo sysctl -w vm.max_map_count=262144
                log_info "vm.max_map_count set successfully"
            fi
        fi
    fi
}

wait_for_healthy() {
    log_info "Waiting for Elasticsearch to be ready..."
    local retries=0
    local max_retries=60
    
    while [ $retries -lt $max_retries ]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' elasticsearch 2>/dev/null || echo "starting")
        
        if [ "$status" = "healthy" ]; then
            echo ""
            log_info "Elasticsearch is healthy!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        retries=$((retries + 1))
        
        # Show status every 30 seconds
        if [ $((retries % 15)) -eq 0 ]; then
            echo ""
            log_info "Still waiting... ($((retries * 2))s elapsed)"
        fi
    done
    
    echo ""
    log_error "Elasticsearch failed to become healthy within $((max_retries * 2)) seconds"
    log_error "Check logs: docker logs elasticsearch"
    return 1
}

usage() {
    echo "Usage: $0 [--with-kibana]"
    echo "  --with-kibana  Also start Kibana (http://localhost:5601)"
    exit 0
}

main() {
    local with_kibana=""
    
    if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
        usage
    fi
    
    if [ "$1" == "--with-kibana" ]; then
        with_kibana="true"
        log_info "Starting Elasticsearch + Kibana..."
    else
        log_info "Starting Elasticsearch..."
    fi
    
    check_docker
    check_requirements

    if docker ps | grep -q "elasticsearch.*healthy"; then
        log_info "Elasticsearch is already running!"
        show_status "$with_kibana"
        exit 0
    fi

    log_step "Pulling images..."
    if [ "$with_kibana" == "true" ]; then
        docker compose --profile kibana pull
        log_step "Starting services..."
        docker compose --profile kibana up -d
    else
        docker compose pull
        log_step "Starting Elasticsearch..."
        docker compose up -d
    fi

    # Wait for Elasticsearch to be healthy
    if wait_for_healthy; then
        show_status "$with_kibana"
    else
        exit 1
    fi
}

show_status() {
    local with_kibana="$1"
    local es_version
    es_version=$(docker exec elasticsearch curl -s http://localhost:9200 2>/dev/null | grep -o '"number" : "[^"]*"' | cut -d'"' -f4 || echo "unknown")
    
    echo ""
    log_info "========================================"
    log_info "🎉 Elasticsearch started successfully!"
    log_info "========================================"
    echo ""
    echo "  🔍 Elasticsearch: http://localhost:9200 (v$es_version)"
    if [ "$with_kibana" == "true" ]; then
        echo "  📊 Kibana:         http://localhost:5601"
    fi
    echo ""
    log_info "Commands:"
    echo "  Stop:        ./stop.sh"
    echo "  Reset:       ./reset.sh"
    echo "  Logs:        docker logs -f elasticsearch"
    echo "  With Kibana: ./start.sh --with-kibana"
}

main "$@"
