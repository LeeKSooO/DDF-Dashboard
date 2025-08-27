# OPTIMIZED - Code-only cache invalidation version
FROM python:3.10-slim

WORKDIR /backend

# Install system dependencies (캐시 유지)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    libpq-dev \
    binutils \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies (캐시 유지)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (캐시 유지)
ENV PYTHONPATH=/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 코드 복사 부분만 캐시 무효화를 위한 ARG 추가
ARG CACHEBUST=1
COPY . ./

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# BACKUP - Original Dockerfile (주석 제거하면 원래대로 복원 가능)
# FROM python:3.10-slim
# 
# WORKDIR /backend
# 
# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc \
#     g++ \
#     git \
#     libpq-dev \
#     binutils \
#     gdal-bin \
#     libgdal-dev \
#     libproj-dev \
#     libgeos-dev \
#     && rm -rf /var/lib/apt/lists/*
# 
# # Copy requirements and install dependencies
# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt
# 
# # Copy backend source code to current directory
# COPY . ./
# 
# # Set environment variables
# ENV PYTHONPATH=/backend
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1
# 
# EXPOSE 8000
# 
# CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]