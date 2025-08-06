# 🚀 Docker Compose 빠른 시작 가이드

## 📋 사전 요구사항

### 1. 필수 소프트웨어
- Docker Desktop (v20.10+)
- Docker Compose (v2.0+)

### 2. 데이터 준비
`data/raw/` 디렉토리에 다음 파일들이 있어야 합니다:

```
data/raw/
├── routes/
│   ├── route_info.csv
│   ├── route_stops.csv
│   └── routes.csv
└── usages/
    ├── 01_20241101_20241114.csv
    ├── 02_20241115_20241128.csv
    ├── ... (모든 사용량 데이터 파일들)
    └── 17_20250613_20250625.csv
```

## 🔧 실행 단계

### 1. 프로젝트 디렉토리로 이동
```bash
cd /Users/leekyoungsoo/teamProject/DDF-ASTGCN
```

### 2. 최초 환경 구성 (팀원)
```bash
# infrastructure 디렉토리에서 실행
cd infrastructure

# 1단계: ETL로 데이터 적재
docker-compose -f docker-compose.etl.yml up

# ETL 완료 확인 후 Ctrl+C로 종료

# 2단계: 운영 서비스 시작
docker-compose up -d
```

### 3. 일반 개발/운영 사용
```bash
# 데이터가 이미 적재된 상태에서
cd infrastructure
docker-compose up -d
```

### 4. 실행 순서 확인
서비스들이 다음 순서로 시작됩니다:

**ETL 단계 (최초/업데이트시):**
1. **PostgreSQL** (5432 포트) - 데이터베이스 초기화
2. **ETL** - 원본 데이터 처리 및 데이터베이스 적재

**운영 단계:**
1. **PostgreSQL** (5432 포트) - 기존 데이터 사용
2. **TorchServe** (8080-8082 포트) - AI 모델 서빙  
3. **Backend** (8000 포트) - FastAPI 서버
4. **Frontend** (3000 포트) - React 웹 대시보드
5. **Redis** (6379 포트) - 캐시 서버

## 🔍 상태 확인

### 서비스 상태 확인
```bash
docker-compose ps
```

### 로그 확인
```bash
# 전체 로그
docker-compose logs

# 특정 서비스 로그
docker-compose logs postgres
docker-compose logs etl
docker-compose logs backend
docker-compose logs frontend
docker-compose logs torchserve
```

### 헬스체크 확인
```bash
# PostgreSQL
docker exec ddf-postgres pg_isready -U ddf_user -d ddf_db

# Backend API
curl http://localhost:8000/health

# TorchServe
curl http://localhost:8080/ping

# Frontend
curl http://localhost:3000
```

## 🌐 접속 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| Frontend | http://localhost:3000 | 웹 대시보드 |
| Backend API | http://localhost:8000 | FastAPI 서버 |
| API 문서 | http://localhost:8000/docs | Swagger UI |
| TorchServe | http://localhost:8080 | AI 모델 API |
| TorchServe 관리 | http://localhost:8081 | 모델 관리 API |

## 🛠️ 문제 해결

### 일반적인 문제들

#### 1. 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :5432  # PostgreSQL
lsof -i :8000  # Backend
lsof -i :3000  # Frontend
lsof -i :8080  # TorchServe
```

#### 2. 데이터 볼륨 초기화
```bash
# 모든 컨테이너 및 볼륨 삭제
docker-compose down -v
docker system prune -f

# 다시 시작
docker-compose up -d
```

#### 3. ETL 프로세스 재실행 (데이터 업데이트시)
```bash
# 새 데이터를 data/raw/usages/에 추가한 후
cd infrastructure
docker-compose -f docker-compose.etl.yml up etl

# 필요시 백엔드 재시작 (캐시 클리어)
docker-compose restart backend
```

#### 4. 모델 파일 확인
```bash
# TorchServe 모델 확인
curl http://localhost:8081/models
```

### 개별 서비스 디버깅

#### PostgreSQL 연결 테스트
```bash
docker exec -it ddf-postgres psql -U ddf_user -d ddf_db
```

#### Backend 개발 모드
```bash
# Backend만 로컬에서 실행
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

#### Frontend 개발 모드
```bash
# Frontend만 로컬에서 실행
cd frontend
npm install
npm start
```

## 🔄 데이터 업데이트

새로운 데이터를 추가하려면:

1. `data/raw/usages/` 에 새 CSV 파일 추가
2. ETL 컨테이너 재시작:
```bash
docker-compose restart etl
```

## 🛑 중지 및 정리

```bash
# 서비스 중지 (데이터 보존)
docker-compose stop

# 서비스 및 네트워크 삭제 (데이터 보존)
docker-compose down

# 모든 것 삭제 (데이터 포함)
docker-compose down -v
```

## 📊 모니터링

### 시스템 리소스 확인
```bash
docker stats
```

### 디스크 사용량
```bash
docker system df
```

### 네트워크 확인
```bash
docker network ls
docker network inspect infrastructure_ddf-network
```