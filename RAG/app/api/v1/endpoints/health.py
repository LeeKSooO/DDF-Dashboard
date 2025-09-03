"""
Health check endpoints
"""

import time
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_database, 
    get_redis, 
    get_llm_service,
    get_embedding_service,
    get_vector_store_service
)
from app.core.config import settings
from app.models.schemas.response import HealthResponse, ResponseStatus, DatabaseTestResponse
from app.models.schemas.request import DatabaseConnectionTest


router = APIRouter(prefix="/health", tags=["health"])

# Application start time
start_time = time.time()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check"""
    
    return HealthResponse(
        status=ResponseStatus.SUCCESS,
        message="Service is healthy",
        services={},
        uptime=time.time() - start_time
    )


@router.get("/detailed", response_model=HealthResponse)
async def detailed_health_check(
    db: Session = Depends(get_database),
    redis = Depends(get_redis)
):
    """Detailed health check with all services"""
    
    services_status = {}
    overall_status = ResponseStatus.SUCCESS
    
    # Check database
    try:
        db.execute("SELECT 1")
        services_status["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        services_status["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        overall_status = ResponseStatus.PARTIAL
    
    # Check Redis
    if redis:
        try:
            await redis.ping()
            services_status["redis"] = {
                "status": "healthy",
                "message": "Redis connection successful"
            }
        except Exception as e:
            services_status["redis"] = {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}"
            }
            overall_status = ResponseStatus.PARTIAL
    else:
        services_status["redis"] = {
            "status": "disabled",
            "message": "Redis not configured"
        }
    
    # Check LLM service
    try:
        llm_service = get_llm_service()
        health_status = await llm_service.health_check()
        services_status["llm_service"] = {
            "status": "healthy" if health_status else "unhealthy",
            "message": "LLM service operational" if health_status else "LLM service unavailable"
        }
    except Exception as e:
        services_status["llm_service"] = {
            "status": "unhealthy",
            "message": f"LLM service error: {str(e)}"
        }
        overall_status = ResponseStatus.PARTIAL
    
    # Check embedding service
    try:
        embedding_service = get_embedding_service()
        health_status = await embedding_service.health_check()
        services_status["embedding_service"] = {
            "status": "healthy" if health_status else "unhealthy",
            "message": "Embedding service operational" if health_status else "Embedding service unavailable"
        }
    except Exception as e:
        services_status["embedding_service"] = {
            "status": "unhealthy",
            "message": f"Embedding service error: {str(e)}"
        }
        overall_status = ResponseStatus.PARTIAL
    
    # Check vector store
    try:
        vector_store_service = get_vector_store_service()
        health_status = await vector_store_service.health_check()
        services_status["vector_store"] = {
            "status": "healthy" if health_status else "unhealthy",
            "message": "Vector store operational" if health_status else "Vector store unavailable"
        }
    except Exception as e:
        services_status["vector_store"] = {
            "status": "unhealthy",
            "message": f"Vector store error: {str(e)}"
        }
        overall_status = ResponseStatus.PARTIAL
    
    return HealthResponse(
        status=overall_status,
        message="Detailed health check completed",
        services=services_status,
        uptime=time.time() - start_time
    )


@router.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe"""
    
    try:
        # Check critical services
        llm_service = get_llm_service()
        
        # Quick health checks
        if not await llm_service.health_check():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service not ready"
            )
        
        return {"status": "ready"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe"""
    
    return {"status": "alive", "uptime": time.time() - start_time}


@router.post("/database", response_model=DatabaseTestResponse)
async def test_database_connection(
    request: DatabaseConnectionTest,
    db: Session = Depends(get_database)
):
    """Test database connection with custom query"""
    
    try:
        start_time_db = time.time()
        result = db.execute(request.query).fetchall()
        response_time = time.time() - start_time_db
        
        # Convert result to dict format
        result_dict = [dict(row) for row in result] if result else []
        
        return DatabaseTestResponse(
            status=ResponseStatus.SUCCESS,
            message="Database query executed successfully",
            connected=True,
            response_time=response_time,
            result=result_dict
        )
        
    except Exception as e:
        return DatabaseTestResponse(
            status=ResponseStatus.ERROR,
            message="Database query failed",
            connected=False,
            error_details=str(e)
        )