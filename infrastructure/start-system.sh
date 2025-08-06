#!/bin/bash
set -e

echo "🚀 Starting DDF-ASTGCN System..."

# 1. PostgreSQL 시작
echo "📊 Step 1: Starting PostgreSQL..."
docker-compose up -d postgres

# PostgreSQL 헬스체크 대기
echo "⏳ Waiting for PostgreSQL to be healthy..."
while ! docker-compose ps postgres | grep -q "healthy"; do
    sleep 2
    echo "   Still waiting for PostgreSQL..."
done
echo "✅ PostgreSQL is ready!"

# 2. ETL 실행
echo "📈 Step 2: Running ETL process..."
docker-compose -f docker-compose.etl.yml up

# ETL 완료 확인
if [ $? -eq 0 ]; then
    echo "✅ ETL completed successfully!"
else
    echo "❌ ETL failed!"
    exit 1
fi

# 3. TorchServe 시작 (모델 로딩)
echo "🤖 Step 3: Starting TorchServe..."
docker-compose up -d torchserve

# TorchServe 헬스체크 대기
echo "⏳ Waiting for TorchServe to be ready..."
while ! docker-compose ps torchserve | grep -q "healthy"; do
    sleep 5
    echo "   Still waiting for TorchServe..."
done
echo "✅ TorchServe is ready!"

# 4. 모델 등록 (TorchServe Management API 활용)
echo "📝 Step 4: Registering AI models from TorchServe..."
docker-compose --profile registration up model-registration

# 모델 등록 완료 확인
if [ $? -eq 0 ]; then
    echo "✅ Model registration completed!"
else
    echo "❌ Model registration failed!"
    exit 1
fi

# 5. 나머지 서비스 시작
echo "🌐 Step 5: Starting remaining services..."
docker-compose up -d backend frontend redis

# 서비스 상태 확인
echo "📋 Final status check:"
docker-compose ps

echo ""
echo "🎉 System startup completed!"
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "🧠 TorchServe: http://localhost:8080"