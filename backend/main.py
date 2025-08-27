from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.session import close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Starting DRT Dashboard API...")
    yield
    # Shutdown
    logger.info("Shutting down DRT Dashboard API...")
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="""
        DRT Dashboard API
        
        이 API는 서울시 교통 데이터를 활용하여 실시간 교통 현황 대시보드를 제공합니다.
        
        ## 주요 기능
        
        * **Overview**: 서울시 교통 현황 개요 (실시간 수요 패턴, 지연 분석, 효율성 지표)
        * **Comparison**: 평일/주말 교통 패턴 비교 분석
        * **District-level**: 지역구별 교통 현황 분석
        
        ## 데이터 소스
        
        * 구간별 승객수 데이터 (API 2)
        * 구간별 운행시간 데이터 (API 4)
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    app.include_router(api_router, prefix="/api/v1")
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "DRT Dashboard API",
            "version": "1.0.0",
            "docs": "/docs",
            "status": "active"
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "DRT Dashboard API",
            "version": "1.0.0"
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )