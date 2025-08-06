# 🔧 Multi-step ETL 사용 가이드

## 🎯 구조 개요

ETL 프로세스가 2단계로 분리되어 개발/실험 효율성을 극대화했습니다.

```
ETL Pipeline:
1. etl-data     → 기본 데이터 적재 (bus_stops, routes, stop_usage)
2. etl-features → DRT Feature 생성 (drt_features 테이블)
```

## 🚀 사용법

### 1. 최초 전체 실행 (신규 환경)

```bash
cd infrastructure

# 1단계: PostgreSQL 시작 (필수)
docker-compose up -d postgres

# 2단계: ETL 파이프라인 실행 (순차적)
docker-compose -f docker-compose.etl.yml up

# 실행 순서:
# 1. etl-data 실행 → 2. etl-features 실행
```

### 2. 개발/실험 단계 (Feature 로직 수정)

```bash
# PostgreSQL 실행 상태 확인
docker-compose ps postgres

# Feature 생성만 재실행 (데이터 재적재 없이)
docker-compose -f docker-compose.etl.yml run --rm etl-features

# Feature 로직 수정 후 반복 테스트
# → 몇 분만에 완료 (전체 ETL 불필요)
```

### 3. 부분 실행 옵션

```bash
# 1단계만: 기본 데이터 적재
docker-compose -f docker-compose.etl.yml up etl-data

# 2단계만: Feature 생성 (1단계 완료 후)
docker-compose -f docker-compose.etl.yml up etl-features

# 특정 단계 재실행
docker-compose -f docker-compose.etl.yml restart etl-features
```

## 🔍 실행 로그 확인

```bash
# 전체 로그
docker-compose -f docker-compose.etl.yml logs

# 단계별 로그 확인
docker-compose -f docker-compose.etl.yml logs etl-data
docker-compose -f docker-compose.etl.yml logs etl-features

# 실시간 로그 모니터링
docker-compose -f docker-compose.etl.yml logs -f etl-features
```

## 🎯 개발 워크플로우

### Feature 실험 사이클:

```bash
# 1. Feature 로직 수정 (feature_generator.py)
vim ../data/etl/feature_generator.py

# 2. Feature만 재생성 (빠름)
docker-compose -f docker-compose.etl.yml run --rm etl-features

# 3. 결과 확인
docker exec -it ddf-postgres-etl psql -U ddf_user -d ddf_db -c "SELECT COUNT(*) FROM drt_features;"

# 4. 반복...
```

## ⚠️ 주의사항

### 의존성 관리:
- `etl-features`는 `etl-data` 완료 후에만 실행됨
- `condition: service_completed_successfully` 사용

### 컨테이너 이름:
- `ddf-etl-data`: 기본 데이터 적재
- `ddf-etl-features`: Feature 생성  
- `ddf-postgres`: 운영 환경과 공유하는 PostgreSQL

### DB 연결:
- ETL 컨테이너들이 `host.docker.internal`로 호스트의 PostgreSQL 연결
- 운영 환경과 동일한 데이터베이스 사용
- ETL 결과가 운영 서비스에서 바로 사용됨

## 🔧 문제 해결

### 중간 단계 실패시:
```bash
# 실패한 단계부터 재시작
docker-compose -f docker-compose.etl.yml up etl-features

# 전체 정리 후 재시작
docker-compose -f docker-compose.etl.yml down
docker-compose -f docker-compose.etl.yml up
```

### Feature 테이블 초기화:
```bash
docker exec -it ddf-postgres psql -U ddf_user -d ddf_db -c "TRUNCATE TABLE drt_features;"
docker-compose -f docker-compose.etl.yml run --rm etl-features
```

## 🚀 성능 팁

### 빠른 Feature 실험:
```bash
# DB 연결 확인
docker-compose -f docker-compose.etl.yml ps postgres

# Feature만 빠르게 재실행 (PostgreSQL이 이미 실행 중인 경우)
docker-compose -f docker-compose.etl.yml run --rm etl-features
```

### 메모리 사용량 확인:
```bash
docker stats ddf-etl-data ddf-etl-features
```

## 📊 결과 확인

### 데이터 적재 확인:
```bash
# 기본 테이블 확인
docker exec -it ddf-postgres psql -U ddf_user -d ddf_db -c "
SELECT 
  'bus_stops' as table_name, COUNT(*) as count FROM bus_stops
UNION ALL
SELECT 'stop_usage', COUNT(*) FROM stop_usage  
UNION ALL
SELECT 'drt_features', COUNT(*) FROM drt_features;
"
```

### Feature 품질 확인:
```bash
docker exec -it ddf-postgres psql -U ddf_user -d ddf_db -c "
SELECT 
  MIN(drt_prob) as min_drt_prob,
  MAX(drt_prob) as max_drt_prob,
  AVG(drt_prob) as avg_drt_prob,
  COUNT(*) as total_features
FROM drt_features;
"
```