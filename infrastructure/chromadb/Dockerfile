FROM chromadb/chroma:latest

# 작업 디렉토리 설정
WORKDIR /chroma

# ChromaDB 데이터 디렉토리 생성
RUN mkdir -p /chroma/data

# 포트 노출
EXPOSE 8003

# ChromaDB 실행 명령
CMD ["chroma", "run", "--host", "0.0.0.0", "--port", "8003", "--path", "/chroma/data"]