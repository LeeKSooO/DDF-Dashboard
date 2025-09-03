"""
Application configuration settings
"""

import os
from typing import List, Optional, Any, Dict
from pydantic import validator
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    
    # Project info
    PROJECT_NAME: str = "DDF RAG Service"
    PROJECT_DESCRIPTION: str = "Enterprise-grade RAG system for natural language to SQL conversion"
    VERSION: str = "1.0.0"
    
    # API settings
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    
    # CORS settings
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Watson AI settings
    WATSON_API_KEY: Optional[str] = os.getenv('WATSON_API_KEY')
    WATSON_URL: Optional[str] = os.getenv('WATSON_URL')
    WATSON_PROJECT_ID: Optional[str] = os.getenv('WATSON_PROJECT_ID')
    WATSON_MODEL_ID: str = os.getenv('WATSON_MODEL_ID', "ibm/granite-3-8b-instruct")
    
    # Database settings
    DATABASE_URL: Optional[str] = None
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    
    # Redis settings (for caching)
    REDIS_URL: Optional[str] = "redis://localhost:6379"
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # Vector store settings
    VECTOR_STORE_TYPE: str = "chroma"  # chroma, pinecone, weaviate
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # RAG settings
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5
    MAX_RESULTS: int = 10
    SIMILARITY_THRESHOLD: float = 0.7
    MAX_CONTEXT_LENGTH: int = 4000
    
    # Backend API settings
    BACKEND_API_URL: str = "http://localhost:8000"
    
    # Document loading settings
    DOCUMENT_PATHS: List[Dict[str, Any]] = [
        {
            "type": "directory",
            "path": "./data/documents",
            "pattern": "**/*.pdf",
            "chunk_size": 1500,
            "chunk_overlap": 300
        }
        # 추가 문서 경로는 여기에 설정
        # {
        #     "type": "file",
        #     "path": "./data/manual.pdf",
        #     "chunk_size": 1000,
        #     "chunk_overlap": 200
        # }
    ]
    
    # LangChain settings
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    @validator("ALLOWED_HOSTS", pre=True)
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()