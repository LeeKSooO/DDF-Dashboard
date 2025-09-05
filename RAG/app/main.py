"""
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.dependencies import setup_dependencies, cleanup_dependencies
from app.api.v1.router import api_router
from app.api.middleware.logging import setup_logging_middleware


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=f"""{settings.PROJECT_DESCRIPTION}

## 🚀 RAG API 사용법

### 1. 기본 질의 응답
- **엔드포인트**: `POST /api/v1/query/`
- **기능**: 문서 기반 RAG와 백엔드 데이터를 결합하여 답변 생성

### 2. 지원하는 질문 유형
- DRT 시스템 관련 질문
- 교통 데이터 분석 방법론
- ASTGCN 모델 특징
- 수요응답형 교통 서비스

### 3. 테스트 방법
1. 아래 `/query/` 엔드포인트에서 "Try it out" 클릭
2. 예시 질문 입력 또는 직접 질문 작성
3. "Execute" 버튼으로 실행
4. LLM 응답과 참조 문서 확인

### 📚 예시 질문들
- "DRT 시스템이 무엇인가요?"
- "수요응답형 교통의 장점은 무엇인가요?"
- "ASTGCN 모델의 특징을 알려주세요"
""",
        version=settings.VERSION,
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        contact={
            "name": "DDF Team",
            "url": "https://github.com/your-org/ddf-project",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        }
    )

    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_hosts_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup logging middleware
    setup_logging_middleware(app)
    
    # Setup startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Initialize all services on startup"""
        await setup_dependencies(app)
    
    @app.on_event("shutdown") 
    async def shutdown_event():
        """Cleanup all services on shutdown"""
        await cleanup_dependencies()
    
    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    return app


# Create app instance
app = create_application()