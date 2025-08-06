# 🐳 Infrastructure - Docker Compose 가이드

## 📁 구성 파일

### 1. `docker-compose.yml` - 운영 환경
**ETL을 제외한 모든 운영 서비스**
- PostgreSQL (데이터베이스)
- Backend (FastAPI)
- Frontend (React + Nginx)  
- TorchServe (AI 모델)
- Redis (캐시)

### 2. `docker-compose.etl.yml` - ETL 전용
**데이터 적재 전용**
- PostgreSQL (동일한 볼륨 사용)
- ETL (일회성 실행)

## 🚀 사용법

### 🔄 최초 환경 구성 (팀원)

```bash
cd infrastructure

# 1단계: PostgreSQL 먼저 시작 (필수)
docker-compose up -d postgres

# 2단계: Multi-step ETL 실행 (데이터 적재 + Feature 생성)
docker-compose -f docker-compose.etl.yml up

# 실행 순서: etl-data → etl-features
# 완료 후 자동 종료됨

# 3단계: 나머지 서비스 시작 (postgres는 이미 실행중이므로 제외)
docker-compose up -d backend frontend torchserve redis
```

### 🏃‍♂️ 일반 개발/운영

```bash
# 서비스 시작 (ETL 제외)
docker-compose up -d

# 서비스 중지
docker-compose down

# 특정 서비스만 시작할 경우
docker-compose up -d postgres backend frontend
```

### 📊 데이터 업데이트

```bash
# 새로운 데이터 파일을 data/raw/usages/에 추가 후

# PostgreSQL이 실행중인지 확인
docker-compose ps postgres

# 전체 ETL 재실행 (PostgreSQL 실행 중이어야 함)
docker-compose -f docker-compose.etl.yml up

# 또는 Feature만 재생성 (개발/실험시)
docker-compose -f docker-compose.etl.yml run --rm etl-features

# 필요시 백엔드 재시작 (캐시 클리어)
docker-compose restart backend
```

## 🌐 접속 정보

|    서비스    |              URL               |  포트 |
|-------------|-------------------------------|------|
| Frontend    |    http://localhost:3000      | 3000 |
| Backend API |    http://localhost:8000      | 8000 |
| API 문서     |    http://localhost:8000/docs |  -   |
| PostgreSQL  |    localhost:5432 | 5432      |
| TorchServe  |    http://localhost:8080      | 8080-8082 |
| Redis       |    localhost:6379 | 6379      |

## 🔍 상태 확인

```bash
# 실행 중인 서비스 확인
docker-compose ps

# 로그 확인
docker-compose logs -f [service_name]

# 헬스체크
curl http://localhost:8000/health
curl http://localhost:8080/ping
```

## ⚠️ 주의사항

### ETL 실행시
- **PostgreSQL을 미리 시작해야 함**: `docker-compose up -d postgres`
- ETL 컨테이너가 `host.docker.internal`로 호스트의 PostgreSQL에 연결
- ETL은 `restart: "no"` 설정으로 1회성 실행
- 실행 완료 후 자동 종료됨

### 볼륨 관리
```bash
# 모든 데이터 삭제 (주의!)
docker-compose down -v

# 볼륨 현황 확인
docker volume ls
```

## 🛠️ 개발 팁

### 개별 서비스 재시작
```bash
docker-compose restart backend
docker-compose restart frontend
```

### 로그 실시간 확인
```bash
docker-compose logs -f backend
docker-compose logs -f etl
```

### 컨테이너 내부 접속
```bash
docker exec -it ddf-postgres psql -U ddf_user -d ddf_db
docker exec -it ddf-backend bash
```