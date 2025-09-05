# RAG API Server Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /rag

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install CPU-only PyTorch first
RUN pip install --no-cache-dir torch==2.4.0+cpu --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies (excluding torch from requirements.txt)
RUN grep -v "torch==" requirements.txt | pip install --no-cache-dir -r /dev/stdin

# Copy application code
COPY . .

# Create data directory for ChromaDB and documents
RUN mkdir -p /rag/chroma /rag/data/documents

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/api/v1/health/ || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]