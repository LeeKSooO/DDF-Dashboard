# Docker 실행 가이드

## 사전 준비사항

### 1. MST-GCN 모델 아카이브 생성

Docker Compose를 실행하기 전에 반드시 TorchServe용 모델 아카이브를 생성해야 합니다.

```bash
cd torchserve
chmod +x create_model_archive.sh
./create_model_archive.sh
```

**생성 확인:**
```bash
ls -la ai/torchserve/model-store/
# mstgcn.mar 파일이 있어야 함
```

### 2. 필요한 파일 구조 확인

```
DDF-MSTGCN/ai/
├── models/
│   └── mstgcn_architecture.py
├── ddf_model/
│   ├── mstgcn_model_v1.pt
│   ├── adj_mx.npy
│   └── stats.npz
│   └── valid_stop_ids.txt
├── torchserve/
    └── model-store/
        └── mstgcn.mar  # ← 이 파일이 반드시 있어야 함
```

## Docker Compose 실행

### 1. 전체 서비스 실행

```bash
# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 2. 개별 서비스 실행 (개발용)

```bash
# 1. 데이터베이스만 실행
docker-compose up -d postgres

# 2. TorchServe 실행
docker-compose up -d torchserve

# 3. 백엔드 실행
docker-compose up -d backend

# 4. 프론트엔드 실행
docker-compose up -d frontend
```

### 3. 서비스 상태 확인

```bash
# 모든 서비스 상태 확인
docker-compose ps

# 헬스체크 확인
docker-compose logs torchserve
docker-compose logs backend
```

## 서비스 엔드포인트

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **TorchServe Inference**: http://localhost:8080
- **TorchServe Management**: http://localhost:8081
- **TorchServe Metrics**: http://localhost:8082
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 테스트

### 1. TorchServe 테스트

```bash
# 헬스체크
curl http://localhost:8080/ping

# 모델 상태 확인
curl http://localhost:8081/models

# 예측 테스트 (예시)
curl -X POST http://localhost:8080/predictions/mstgcn \
  -H "Content-Type: application/json" \
  -d '{
    "hour_data": [[[...]]], 
    "day_data": [[[...]]], 
    "week_data": [[[[]]]]
  }'
```

### 2. Backend 테스트

```bash
# API 문서 확인
curl http://localhost:8000/docs

# 예측 요청
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "target_datetime": "2024-12-01T14:00:00",
    "stop_ids": ["GGB239000001"]
  }'
```

## 트러블슈팅

### 1. TorchServe 시작 실패

```bash
# 모델 아카이브 파일 확인
ls -la torchserve/model-store/mstgcn.mar

# 모델 아카이브 재생성
cd torchserve
./create_model_archive.sh
```

### 2. 백엔드 연결 실패

```bash
# TorchServe 헬스체크
docker-compose exec backend curl -f http://torchserve:8080/ping

# 데이터베이스 연결 확인
docker-compose exec backend python -c "from app.db.session import get_db; print('DB OK')"
```

### 3. 로그 확인

```bash
# 전체 로그
docker-compose logs

# 특정 서비스 로그
docker-compose logs torchserve
docker-compose logs backend
docker-compose logs postgres
```

## 개발 모드

개발 중에는 다음과 같이 실행할 수 있습니다:

```bash
# 데이터베이스와 TorchServe만 Docker로 실행
docker-compose up -d postgres torchserve redis

# 백엔드는 로컬에서 실행
cd backend
python main.py
```

## 정리

```bash
# 모든 컨테이너 정지 및 삭제
docker-compose down

# 볼륨까지 삭제 (데이터 초기화)
docker-compose down -v

# 이미지까지 삭제
docker-compose down --rmi all
```