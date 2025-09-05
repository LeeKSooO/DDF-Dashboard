#!/bin/bash

# Document ETL Job Runner Script
# Makes it easy to run document embedding ETL process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
FORCE_RELOAD=false
CHROMADB_URL="http://localhost:8003"
DOCUMENTS_PATH="./data/documents"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Document ETL Job Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --force-reload     Force reload all documents (clears existing vector store)"
    echo "  -u, --chromadb-url URL ChromaDB server URL (default: http://localhost:8003)"
    echo "  -d, --documents-path   Path to documents directory (default: ./data/documents)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Normal ETL (only new/changed docs)"
    echo "  $0 --force-reload                    # Force reload all documents"
    echo "  $0 --chromadb-url http://localhost:8003  # Custom ChromaDB URL"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force-reload)
            FORCE_RELOAD=true
            shift
            ;;
        -u|--chromadb-url)
            CHROMADB_URL="$2"
            shift 2
            ;;
        -d|--documents-path)
            DOCUMENTS_PATH="$2"
            shift 2
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

# Check if we're in the correct directory
if [ ! -f "etl/document_etl.py" ]; then
    print_error "Please run this script from the RAG directory (parent of etl/)"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not found"
    exit 1
fi

# Check if documents directory exists
if [ ! -d "$DOCUMENTS_PATH" ]; then
    print_warning "Documents directory does not exist: $DOCUMENTS_PATH"
    read -p "Do you want to continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Prepare arguments
ARGS=()
if [ "$FORCE_RELOAD" = true ]; then
    ARGS+=("--force-reload")
fi
ARGS+=("--chromadb-url" "$CHROMADB_URL")
ARGS+=("--documents-path" "$DOCUMENTS_PATH")

# Show configuration
print_info "Starting Document ETL Job"
print_info "Configuration:"
print_info "  • ChromaDB URL: $CHROMADB_URL"
print_info "  • Documents Path: $DOCUMENTS_PATH"
print_info "  • Force Reload: $FORCE_RELOAD"

# Check if ChromaDB is accessible (optional)
if command -v curl &> /dev/null; then
    if curl -f -s "$CHROMADB_URL/api/v1/heartbeat" > /dev/null 2>&1; then
        print_success "ChromaDB server is accessible at $CHROMADB_URL"
    else
        print_warning "ChromaDB server might not be running at $CHROMADB_URL"
        print_warning "Make sure to start ChromaDB before running ETL"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Run the ETL job
print_info "Running ETL job..."
if python3 etl/document_etl.py "${ARGS[@]}"; then
    print_success "Document ETL Job completed successfully!"
else
    print_error "Document ETL Job failed!"
    exit 1
fi