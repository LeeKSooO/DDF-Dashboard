#!/bin/bash

# Docker를 사용한 ETL 실행 스크립트
# 기존 RAG 이미지를 일회용 컨테이너로 사용

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
FORCE_RELOAD=false
RAG_IMAGE="infrastructure-rag:latest"
NETWORK="infrastructure_ddf-network"
PROJECT_ROOT="/Users/leekyoungsoo/teamProject/DDF-ASTGCN"

show_usage() {
    echo "Docker ETL Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --force-reload     Force reload all documents"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Normal ETL (only new/changed docs)"
    echo "  $0 --force-reload      # Force reload all documents"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force-reload)
            FORCE_RELOAD=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [ ! -f "etl/document_etl.py" ]; then
    print_error "Please run this script from the RAG directory"
    exit 1
fi

# Check if RAG image exists
if ! docker image inspect "$RAG_IMAGE" >/dev/null 2>&1; then
    print_error "RAG image '$RAG_IMAGE' not found"
    print_info "Please build the RAG service first: docker-compose build rag"
    exit 1
fi

# Check if network exists
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
    print_error "Docker network '$NETWORK' not found"
    print_info "Please start the infrastructure services first: docker-compose up -d"
    exit 1
fi

# Check if ChromaDB is running
if ! docker ps --format "table {{.Names}}" | grep -q "ddf-chromadb"; then
    print_error "ChromaDB container not running"
    print_info "Please start ChromaDB first: docker-compose up -d chromadb"
    exit 1
fi

# Prepare Docker command
DOCKER_CMD="docker run --rm"
DOCKER_CMD="$DOCKER_CMD --network $NETWORK"
DOCKER_CMD="$DOCKER_CMD -v $PROJECT_ROOT/RAG:/rag"
DOCKER_CMD="$DOCKER_CMD -w /rag"
DOCKER_CMD="$DOCKER_CMD --env-file $PROJECT_ROOT/.env"
DOCKER_CMD="$DOCKER_CMD $RAG_IMAGE"

# Prepare ETL command
ETL_CMD="python etl/document_etl.py"
if [ "$FORCE_RELOAD" = true ]; then
    ETL_CMD="$ETL_CMD --force-reload"
fi

print_info "Starting Docker ETL Process..."
print_info "Image: $RAG_IMAGE"
print_info "Network: $NETWORK"
print_info "Force Reload: $FORCE_RELOAD"
print_info "Command: $ETL_CMD"
echo ""

# Run ETL
if eval "$DOCKER_CMD $ETL_CMD"; then
    echo ""
    print_success "🎉 ETL Process completed successfully!"
else
    echo ""
    print_error "❌ ETL Process failed!"
    exit 1
fi