#!/bin/bash

# RAG Service Start Script

set -e

echo "🚀 Starting DDF RAG Service..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please update .env file with your Watson AI credentials"
fi

# Create data directories
mkdir -p chroma logs data/documents

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Install dependencies if requirements.txt is newer than last install
if [ requirements.txt -nt .last_install ] || [ ! -f .last_install ]; then
    echo "📦 Installing/updating dependencies..."
    pip install -r requirements.txt
    touch .last_install
else
    echo "✅ Dependencies up to date"
fi

# Run database migrations (if any)
if [ -f "scripts/migrate.py" ]; then
    echo "🔄 Running database migrations..."
    python scripts/migrate.py
fi

# Start the application
echo "🌟 Starting RAG API server on http://localhost:8001"
echo "📖 API Documentation: http://localhost:8001/api/v1/docs"

uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --reload \
    --log-level info