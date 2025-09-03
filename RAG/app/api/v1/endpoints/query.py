"""
Query endpoints for RAG-based Q&A
"""

import logging
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_llm_service, get_vector_store_service
from app.services.llm_service import LLMService  
from app.services.vector_store_service import VectorStoreService
from app.core.config import settings


router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


class RAGQueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str = Field(..., description="사용자 질문", example="DRT 시스템이 무엇인가요?")
    k: int = Field(default=5, description="검색할 문서 개수", example=5)
    confidence_threshold: float = Field(default=0.7, description="유사도 임계값", example=0.7)
    include_sources: bool = Field(default=True, description="참조 문서 포함 여부", example=True)
    backend_data: bool = Field(default=True, description="백엔드 데이터 포함 여부", example=True)

    class Config:
        schema_extra = {
            "example": {
                "query": "DRT 시스템이 무엇인가요?",
                "k": 5,
                "confidence_threshold": 0.7,
                "include_sources": True,
                "backend_data": True
            }
        }


class RAGQueryResponse(BaseModel):
    """Response model for RAG query"""
    status: str = Field(..., description="응답 상태", example="success")
    message: str = Field(..., description="응답 메시지", example="RAG query processed successfully")
    query: str = Field(..., description="사용자 질문", example="DRT 시스템이 무엇인가요?")
    answer: str = Field(..., description="LLM 생성 답변", example="DRT는 수요응답형 교통서비스로...")
    sources: Optional[list] = Field(None, description="참조한 문서들")
    backend_data: Optional[Dict[str, Any]] = Field(None, description="백엔드에서 가져온 데이터")
    confidence: Optional[float] = Field(None, description="평균 유사도 점수", example=0.85)


@router.post(
    "/", 
    response_model=RAGQueryResponse,
    summary="RAG 기반 질의응답",
    description="""
    **RAG(Retrieval-Augmented Generation)를 사용하여 질문에 답변합니다.**
    
    ## 작동 방식
    1. 벡터 데이터베이스에서 관련 문서 검색
    2. 백엔드 API에서 추가 데이터 수집
    3. Watson AI LLM이 통합된 정보로 답변 생성
    
    ## 사용법
    - **query**: 질문을 한국어로 입력하세요
    - **k**: 검색할 문서 개수 (기본값: 5)
    - **confidence_threshold**: 유사도 임계값 (기본값: 0.7)
    - **include_sources**: 참고한 문서 포함 여부
    - **backend_data**: 백엔드 데이터 포함 여부
    
    ## 예시 질문
    - "DRT 시스템이 무엇인가요?"
    - "수요응답형 교통의 장점은?"
    - "ASTGCN 모델에 대해 설명해주세요"
    """,
    response_description="RAG 기반 답변과 참조 소스들"
)
async def process_rag_query(
    request: RAGQueryRequest,
    llm_service: LLMService = Depends(get_llm_service),
    vector_service: VectorStoreService = Depends(get_vector_store_service)
):
    
    try:
        logger.info(f"Processing RAG query: {request.query}")
        
        # 1. Retrieve similar documents from vector store
        similar_docs = await vector_service.search_similar(
            query=request.query,
            k=request.k,
            similarity_threshold=request.confidence_threshold
        )
        
        # 2. Fetch backend data if requested
        backend_data = None
        if request.backend_data:
            backend_data = await fetch_backend_data(request.query)
        
        # 3. Construct context from similar documents
        context_docs = []
        sources = []
        for doc, similarity, metadata in similar_docs:
            context_docs.append(doc)
            if request.include_sources:
                sources.append({
                    "content": doc,  # 전체 내용 표시
                    "similarity": similarity,
                    "source": metadata.get("source", "unknown"),
                    "metadata": metadata
                })
        
        # 4. Create RAG prompt
        context = "\n\n".join(context_docs) if context_docs else "관련 문서를 찾을 수 없습니다."
        
        backend_context = ""
        if backend_data:
            backend_context = f"\n\n백엔드 데이터:\n{format_backend_data(backend_data)}"
        
        prompt = f"""
다음 문서들을 참고하여 사용자의 질문에 답변해주세요.

참고 문서:
{context}{backend_context}

사용자 질문: {request.query}

답변은 다음 조건을 지켜주세요:
1. 참고 문서의 내용을 바탕으로 정확하고 구체적으로 답변
2. 한국어로 자연스럽게 작성
3. 백엔드 데이터가 있다면 이를 활용하여 더 풍부한 답변 제공
4. 확실하지 않은 내용은 추측하지 말고 "확실하지 않습니다"라고 표현

답변:
"""
        
        # LLM 프롬프트 로깅 (디버깅용)
        logger.info(f"=== LLM PROMPT ===\n{prompt}\n=== END PROMPT ===")
        logger.info(f"Found {len(context_docs)} context documents with total length: {len(context)} characters")
        
        # 5. Generate answer using LLM
        answer = await llm_service.generate_text(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.1
        )
        
        # 6. Calculate average confidence
        avg_confidence = None
        if similar_docs:
            avg_confidence = sum([sim for _, sim, _ in similar_docs]) / len(similar_docs)
        
        return RAGQueryResponse(
            status="success",
            message="RAG query processed successfully", 
            query=request.query,
            answer=answer.strip(),
            sources=sources if request.include_sources else None,
            backend_data=backend_data,
            confidence=avg_confidence
        )
        
    except Exception as e:
        logger.error(f"RAG query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query processing failed: {str(e)}"
        )


async def fetch_backend_data(query: str) -> Optional[Dict[str, Any]]:
    """Fetch relevant data from backend API"""
    
    try:
        # Backend API URL (adjust as needed)
        backend_url = getattr(settings, 'BACKEND_API_URL', 'http://localhost:8000')
        
        # Example: Make request to backend API
        async with httpx.AsyncClient(timeout=10.0) as client:
            # You can customize this endpoint based on your backend API
            response = await client.get(f"{backend_url}/api/search", params={"q": query})
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Backend API returned status {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to fetch backend data: {e}")
        return None


def format_backend_data(data: Dict[str, Any]) -> str:
    """Format backend data for inclusion in prompt"""
    
    if not data:
        return "백엔드 데이터가 없습니다."
    
    # Customize this formatting based on your backend data structure
    formatted = []
    
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            formatted.append(f"{key}: {str(value)}")
        else:
            formatted.append(f"{key}: {value}")
    
    return "\n".join(formatted)


@router.get("/examples")
async def get_query_examples():
    """Get example queries for RAG system"""
    
    return {
        "examples": [
            "DRT 시스템이 무엇인가요?",
            "수요응답형 교통의 장점은 무엇인가요?",
            "버스 노선 최적화 방법을 알려주세요",
            "교통 데이터 분석 방법론에 대해 설명해주세요",
            "ASTGCN 모델의 특징은 무엇인가요?",
            "교통 수요 예측 모델의 종류를 알려주세요",
            "스마트 교통 시스템의 구성요소는?",
            "교통 빅데이터 활용 사례를 알려주세요"
        ],
        "usage": {
            "endpoint": "/api/v1/query/",
            "method": "POST",
            "request_body": {
                "query": "사용자 질문",
                "k": 5,
                "confidence_threshold": 0.7,
                "include_sources": True,
                "backend_data": True
            }
        }
    }