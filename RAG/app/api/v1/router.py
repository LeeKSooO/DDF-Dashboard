"""
API v1 router
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, query

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(query.router)

# Root endpoint
@api_router.get("/")
async def api_root():
    """API root endpoint"""
    return {
        "message": "DDF RAG Service API v1",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "rag_query": "/query",
            "docs": "/docs"
        },
        "description": "RAG-based Q&A system with backend data integration"
    }