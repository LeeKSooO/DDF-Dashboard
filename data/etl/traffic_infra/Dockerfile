# etl/Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
RUN pip install --no-cache-dir \
    pandas==2.0.3 \
    psycopg2-binary==2.9.7 \
    numpy==1.24.3

# ETL 스크립트 복사
COPY etl_trafficInfra.py /app/
COPY feature_generator.py /app/

# 실행 권한 부여
RUN chmod +x /app/etl_trafficInfra.py /app/feature_generator.py

CMD ["python", "/app/etl_trafficInfra.py"]