"""
Query endpoints for RAG-based Q&A
"""

import logging
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_rag_service
from app.services.rag_service import RAGService
from app.core.config import settings


router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


class RAGQueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str = Field(..., description="사용자 질문", example="DRT 시스템이 무엇인가요?")
    max_results: int = Field(default=10, description="검색할 문서 개수", example=10)
    similarity_threshold: float = Field(default=0.5, description="유사도 임계값", example=0.5)
    include_sources: bool = Field(default=True, description="참조 문서 포함 여부", example=True)
    backend_data: bool = Field(default=True, description="백엔드 데이터 포함 여부", example=True)
    summary_only: bool = Field(default=False, description="4단계 종합 답변만 반환", example=False)

    class Config:
        schema_extra = {
            "example": {
                "query": "DRT 시스템이 무엇인가요?",
                "max_results": 10,
                "similarity_threshold": 0.5,
                "include_sources": True,
                "backend_data": True,
                "summary_only": False
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
    question_classification: Optional[Dict[str, Any]] = Field(None, description="질문 분류 결과", example={
        "type": "qualitative",
        "confidence": 0.85,
        "reasoning": "정성적 키워드 우세",
        "keywords": ["정의", "무엇"],
        "needs_sql": False,
        "needs_rag": True
    })
    sql_info: Optional[Dict[str, Any]] = Field(None, description="SQL 쿼리 정보 (정량적/혼합 질문인 경우)", example={
        "sql_query": "SELECT COUNT(*) FROM bus_stops WHERE is_active = true",
        "sql_confidence": 0.92,
        "sql_reasoning": "활성화된 정류장 개수 조회",
        "execution_success": True,
        "row_count": 1,
        "hybrid_mode": False
    })


@router.post(
    "/", 
    response_model=RAGQueryResponse,
    summary="CoT 강화 RAG 기반 질의응답",
    description="""
    **지능형 RAG + Text-to-SQL 하이브리드 질의응답 시스템**

    ## 자동 적응형 작동 방식
    1. **질문 분류**: 정성적/정량적/무관/혼합 유형 자동 분류
    2. **최적화된 처리**:
       - **정성적 질문** → RAG (문서 검색 및 분석)
       - **정량적 질문** → Text-to-SQL (데이터베이스 조회)
       - **혼합 질문** → SQL + RAG 결합 처리
       - **무관 질문** → 적절한 거부 응답
    3. **자동 최적화**: 질문 유형에 따라 최적의 처리 방식 자동 선택
    4. **CoT 추론**: 단계별 논리적 답변 생성
    5. **투명성**: 처리 과정과 근거 제공

    ## 예시 질문
    **정성적 (RAG)**: "DRT 시스템이 무엇인가요?", "수요응답형 교통의 장점은?"
    **정량적 (SQL)**: "강남구 정류장 개수는?", "시간대별 승차 인원 통계"
    **혼합형**: "DRT 도입 효과를 데이터와 함께 분석해주세요"
    """,
    response_description="CoT 추론 과정이 포함된 RAG 답변"
)
async def process_rag_query(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):

    try:
        logger.info(f"Processing RAG query: {request.query}")

        # Step 1: 질문 분류를 먼저 수행하여 최적의 처리 방식 결정
        from app.services.question_classifier_service import QuestionType
        classification_result = await rag_service.question_classifier.classify_question(request.query)

        logger.info(f"🏷️ Question classified as: {classification_result.question_type.value} (confidence: {classification_result.confidence:.2f})")

        # Step 2: 표준 RAG 처리
        result = await rag_service.query(request.query)
        message = "CoT RAG query processed successfully"
        
        # 4단계 종합 답변만 추출하는 옵션
        # AIMessage 객체를 문자열로 변환
        raw_answer = result["answer"]
        if hasattr(raw_answer, 'content'):
            final_answer = raw_answer.content
        else:
            final_answer = str(raw_answer)

        if request.summary_only:
            final_answer = extract_summary_answer(final_answer)
        
        # 소스 정보 준비
        sources_data = []
        if request.include_sources:
            sources_data.append({"reasoning_steps": result["reasoning_steps"]})
        
        # 백엔드 데이터 준비
        backend_info = {"cot_enabled": result["cot_enabled"]}
        
        return RAGQueryResponse(
            status="success",
            message=message,
            query=result["question"],
            answer=final_answer,
            sources=sources_data if request.include_sources else None,
            backend_data=backend_info if request.backend_data else None,
            confidence=result["confidence"],
            question_classification=result.get("question_classification"),
            sql_info=result.get("sql_info")
        )
        
    except Exception as e:
        logger.error(f"CoT RAG query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CoT RAG query processing failed: {str(e)}"
        )


def extract_summary_answer(cot_response) -> str:
    """Extract only the summary answer from 4th step of CoT response"""

    # AIMessage 객체를 문자열로 변환
    if hasattr(cot_response, 'content'):
        response_text = cot_response.content
    else:
        response_text = str(cot_response)

    # "✅ 4단계: 종합 답변" 이후의 내용만 정확히 추출
    if "✅ 4단계: 종합 답변" in response_text:
        parts = response_text.split("✅ 4단계: 종합 답변")
        if len(parts) > 1:
            summary_part = parts[-1].strip()
            # 줄바꿈 이후의 실제 답변 내용만 반환 (첫 번째 줄은 보통 비어있음)
            lines = summary_part.split('\n')
            # 빈 줄 제거하고 실제 내용만 추출
            content_lines = [line for line in lines if line.strip()]
            return '\n'.join(content_lines).strip()
    
    # 4단계가 없으면 전체 응답 반환
    return response_text.strip()


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


@router.post("/reload-vectorstore")
async def reload_vectorstore(
    rag_service: RAGService = Depends(get_rag_service)
):
    """벡터 저장소를 다시 로드합니다 (읽기 전용 - ETL은 별도 실행 필요)"""
    
    try:
        logger.info("Starting vectorstore reload process...")
        success = await rag_service.reload_vectorstore()
        
        if success:
            return {
                "status": "success",
                "message": "Vector store reloaded successfully (read-only mode)",
                "note": "To add/update documents, run DocumentETL job separately"
            }
        else:
            return {
                "status": "error", 
                "message": "Failed to reload vector store"
            }
            
    except Exception as e:
        logger.error(f"Vector store reload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector store reload failed: {str(e)}"
        )


@router.get("/cot/{mode}")
async def set_cot_mode(
    mode: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """CoT 모드를 설정합니다 (on/off)"""
    
    try:
        if mode.lower() not in ["on", "off"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'on' or 'off'"
            )
        
        enable_cot = mode.lower() == "on"
        await rag_service.set_cot_mode(enable_cot)
        
        return {
            "status": "success",
            "message": f"CoT mode set to {mode}",
            "cot_enabled": enable_cot
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CoT mode setting failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CoT mode setting failed: {str(e)}"
        )


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
        "cot_endpoints": {
            "set_cot_on": "/api/v1/query/cot/on",
            "set_cot_off": "/api/v1/query/cot/off",
            "reload_vectorstore": "/api/v1/query/reload-vectorstore"
        },
        "etl_info": {
            "note": "This service is read-only. To add/update documents, use DocumentETL job:",
            "etl_command": "cd RAG && python etl/document_etl.py --force-reload",
            "etl_script": "cd RAG && ./etl/run_etl.sh --force-reload"
        },
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