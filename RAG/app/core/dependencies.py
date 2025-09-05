"""
Application dependencies setup
"""

import logging
from typing import Generator, Optional
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from redis import Redis

from app.core.config import settings
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService


# Database setup
engine = None
SessionLocal = None

if settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
redis_client: Optional[Redis] = None
if settings.REDIS_URL:
    try:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        logging.warning(f"Redis connection failed: {e}")

# Service instances (will be initialized on startup)
llm_service: Optional[LLMService] = None
embedding_service: Optional[EmbeddingService] = None
rag_service: Optional[RAGService] = None


def get_database() -> Generator[Session, None, None]:
    """Get database session"""
    if not SessionLocal:
        raise RuntimeError("Database not configured")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Optional[Redis]:
    """Get Redis client"""
    return redis_client


def get_llm_service() -> LLMService:
    """Get LLM service instance"""
    if not llm_service:
        raise RuntimeError("LLM service not initialized")
    return llm_service


def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance"""
    if not embedding_service:
        raise RuntimeError("Embedding service not initialized")
    return embedding_service






def get_rag_service() -> RAGService:
    """Get RAG service instance"""
    if not rag_service:
        raise RuntimeError("RAG service not initialized")
    return rag_service


async def setup_dependencies(app: FastAPI) -> None:
    """Setup all application dependencies"""
    global rag_service
    
    logging.info("🚀 Initializing RAG service...")
    
    try:
        # Initialize unified RAG service
        rag_service = RAGService()
        success = await rag_service.initialize()
        
        if success:
            logging.info("✅ RAG service initialized successfully")
        else:
            raise RuntimeError("RAG service initialization failed")
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize RAG service: {e}")
        raise e


async def cleanup_dependencies() -> None:
    """Cleanup application dependencies"""
    global rag_service
    
    logging.info("🧹 Cleaning up RAG service...")
    
    if rag_service:
        await rag_service.cleanup()
    
    if redis_client:
        await redis_client.close()
    
    logging.info("✅ RAG service cleanup completed")