# DocumentETL - RAG 문서 임베딩 도구

RAG 시스템을 위한 독립적인 ETL(Extract, Transform, Load) 도구입니다.

## 기능

- **Extract**: `data/documents/` 디렉토리의 PDF 파일들을 읽어옴
- **Transform**: 문서를 청킹하고 HuggingFace 임베딩으로 벡터화
- **Load**: ChromaDB에 벡터 데이터 적재

## 사용법

### 방법 1: Docker 컨테이너
```bash
# 새/변경된 문서만 처리
cd RAG && ./etl/run_etl_docker.sh

# 모든 문서 강제 재로딩
cd RAG && ./etl/run_etl_docker.sh --force-reload
```

### 방법 2: 로컬 Python 실행
```bash
# 새/변경된 문서만 처리
cd RAG && python etl/document_etl.py

# 모든 문서 강제 재로딩
cd RAG && python etl/document_etl.py --force-reload

# 편의 스크립트 사용
cd RAG && ./etl/run_etl.sh --force-reload
```

## 📋 사전 요구사항

### Docker 방식
- ChromaDB 컨테이너 실행 중: `docker-compose up -d chromadb`
- RAG 이미지 빌드됨: `docker-compose build rag`

### 로컬 방식
- Python 3.11+
- 필요 라이브러리: `pip install -r requirements.txt`
- 환경변수: `.env` 파일 설정

## 🗂️ 파일 구조

```
etl/
├── README.md                 # 이 파일
├── document_etl.py          # 메인 ETL 스크립트
├── run_etl.sh              # 로컬 실행 스크립트
└── run_etl_docker.sh       # Docker 실행 스크립트
```

## ⚡ 효율적인 동작 방식

1. **기존 벡터 DB 없음** → 모든 PDF 파일 임베딩 수행
2. **PDF 파일 변경 감지** → 변경된 파일만 임베딩 추가
3. **변경사항 없음** → 임베딩 작업 스킵 (개발 효율성 ↑)

## 🔧 고급 옵션

### 환경변수 설정
```bash
# ChromaDB 연결
CHROMA_PERSIST_DIR="./chroma"

# 문서 로딩 제어
SKIP_INITIAL_DOCUMENT_LOAD="false"
FORCE_RELOAD_DOCUMENTS="false"
```

### 사용자 정의 ChromaDB URL
```bash
python etl/document_etl.py --chromadb-url http://custom-server:8003
```

## 📊 예시 출력

```
🚀 Document ETL Job Starting
📊 Configuration:
   • ChromaDB URL: http://localhost:8003
   • Documents Path: ./data/documents
   • Force Reload: false
   • Chroma Persist Dir: ./chroma

🔍 Loading documents from ./data/documents...
📚 Found 2190 documents to process
🔨 Creating vector store from documents...
✅ Vector store created with 2190 documents
📊 Final vector store contains 2190 document chunks
🎉 Document ETL Job Completed Successfully!
```

## 🆘 문제 해결

### ChromaDB 연결 실패
```bash
# ChromaDB 상태 확인
docker ps | grep chromadb
curl -f http://localhost:8003/api/v1/heartbeat
```

### 문서 로딩 실패
- `data/documents/` 디렉토리에 PDF 파일이 있는지 확인
- 파일 권한 문제가 없는지 확인

### 메모리 부족
- 대량 문서 처리 시 `--force-reload` 대신 증분 처리 권장