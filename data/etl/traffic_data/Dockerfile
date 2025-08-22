# traffic_etl/Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치 (traffic ETL 전용 패키지)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Traffic ETL 스크립트 복사
COPY etl_trafficData.py /app/

# 실행 권한 부여
RUN chmod +x /app/etl_trafficData.py

# Traffic ETL 실행
CMD ["python", "/app/etl_trafficData.py"]