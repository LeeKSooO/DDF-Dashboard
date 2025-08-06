#!/bin/bash
set -e

echo "🚀 Starting DDF-ASTGCN Services (ETL 건너뛰기)..."

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

# 2. 데이터 존재 확인
echo "📈 Step 2: Checking existing data..."
data_count=$(docker exec ddf-postgres psql -U ddf_user -d ddf_db -t -c "SELECT COUNT(*) FROM bus_stops;" | tr -d ' ')

if [ "$data_count" -gt 0 ]; then
    echo "✅ Found $data_count bus stops - data already exists, skipping ETL"
else
    echo "⚠️  No data found - you may need to run ETL first:"
    echo "   docker-compose -f docker-compose.etl.yml up"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
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
echo "🎉 Services started successfully!"
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "🧠 TorchServe: http://localhost:8080"