#!/bin/bash

# RAG Service Deployment Script

set -e

echo "🚀 Deploying DDF RAG Service..."

# Configuration
IMAGE_NAME="ddf-rag-service"
CONTAINER_NAME="ddf-rag-service"
PORT="8001"

# Parse command line arguments
ENVIRONMENT="development"
BUILD_FRESH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --fresh)
            BUILD_FRESH=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--env development|production] [--fresh]"
            echo "  --env: Environment to deploy (default: development)"
            echo "  --fresh: Force rebuild Docker image"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

echo "📋 Environment: $ENVIRONMENT"

# Stop existing container if running
if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
    echo "⏹️  Stopping existing container..."
    docker stop $CONTAINER_NAME
fi

# Remove existing container
if docker ps -aq -f name=$CONTAINER_NAME | grep -q .; then
    echo "🗑️  Removing existing container..."
    docker rm $CONTAINER_NAME
fi

# Build Docker image
if [ "$BUILD_FRESH" = true ] || ! docker images -q $IMAGE_NAME | grep -q .; then
    echo "🔨 Building Docker image..."
    docker build -t $IMAGE_NAME:latest -f docker/Dockerfile .
else
    echo "✅ Using existing Docker image"
fi

# Create network if it doesn't exist
if ! docker network ls | grep -q rag-network; then
    echo "🌐 Creating Docker network..."
    docker network create rag-network
fi

# Deploy based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    echo "🏭 Production deployment..."
    
    # Use docker-compose for production
    docker-compose -f docker-compose.yml up -d
    
    echo "✅ Production deployment complete!"
    echo "🌟 Service running at: http://localhost:$PORT"
    echo "📖 API Documentation: http://localhost:$PORT/api/v1/docs"
    echo "📊 Health Check: http://localhost:$PORT/api/v1/health"
    
else
    echo "🔧 Development deployment..."
    
    # Run single container for development
    docker run -d \
        --name $CONTAINER_NAME \
        --network rag-network \
        -p $PORT:8001 \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/logs:/app/logs" \
        -e DEBUG=true \
        -e LOG_LEVEL=DEBUG \
        --env-file .env \
        $IMAGE_NAME:latest
    
    echo "✅ Development deployment complete!"
    echo "🌟 Service running at: http://localhost:$PORT"
    echo "📖 API Documentation: http://localhost:$PORT/api/v1/docs"
fi

# Show container status
echo ""
echo "📋 Container Status:"
docker ps -f name=$CONTAINER_NAME

# Show logs
echo ""
echo "📝 Recent Logs:"
docker logs --tail 20 $CONTAINER_NAME