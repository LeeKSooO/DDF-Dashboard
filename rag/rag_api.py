"""
DDF-MSTGCN RAG API Service
FastAPI 기반 RAG 질의응답 서비스
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn

# RAG 애플리케이션 import
try:
    from rag_app_4_watson_2 import TrafficRAGApp
except ImportError:
    logging.error("RAG 애플리케이션을 import할 수 없습니다.")
    raise

# FastAPI 앱 초기화
app = FastAPI(
    title="DDF-MSTGCN RAG API",
    description="교통 연구 논문 기반 RAG 질의응답 시스템",
    version="1.0.0"
)

# RAG 앱 인스턴스
rag_app = None

# Request/Response 모델
class QueryRequest(BaseModel):
    question: str
    max_results: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.7

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    metadata: Dict

@app.on_event("startup")
async def startup_event():
    """서버 시작시 RAG 앱 초기화"""
    global rag_app
    try:
        logging.info("RAG 애플리케이션 초기화 중...")
        rag_app = TrafficRAGApp()
        await rag_app.initialize()
        logging.info("RAG 애플리케이션 초기화 완료")
    except Exception as e:
        logging.error(f"RAG 앱 초기화 실패: {e}")
        raise

@app.get("/")
async def root():
    """헬스체크 엔드포인트"""
    return {"message": "DDF-MSTGCN RAG API", "status": "running"}

@app.get("/health")
async def health_check():
    """상세 헬스체크"""
    if rag_app is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    return {
        "status": "healthy",
        "service": "DDF-MSTGCN RAG",
        "vector_db_status": "connected" if rag_app.vector_store else "disconnected"
    }

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """RAG 질의 처리"""
    if rag_app is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        # RAG 질의 실행
        result = await rag_app.process_query(
            question=request.question,
            max_results=request.max_results,
            similarity_threshold=request.similarity_threshold
        )
        
        return QueryResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            metadata=result.get("metadata", {})
        )
        
    except Exception as e:
        logging.error(f"RAG 질의 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

@app.get("/papers")
async def list_papers():
    """등록된 논문 목록 조회"""
    if rag_app is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        papers = await rag_app.get_paper_list()
        return {"papers": papers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paper list: {str(e)}")

@app.get("/embeddings/status")
async def embedding_status():
    """임베딩 상태 조회"""
    if rag_app is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        status = await rag_app.get_embedding_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get embedding status: {str(e)}")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 서버 실행
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        log_level="info"
    )