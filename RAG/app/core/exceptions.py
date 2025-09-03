"""
Custom application exceptions
"""

from typing import Any, Dict, Optional


class RAGServiceException(Exception):
    """Base exception for RAG service"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class LLMServiceException(RAGServiceException):
    """Exception raised by LLM service"""
    pass


class EmbeddingServiceException(RAGServiceException):
    """Exception raised by embedding service"""
    pass


class VectorStoreException(RAGServiceException):
    """Exception raised by vector store operations"""
    pass


class SQLGenerationException(RAGServiceException):
    """Exception raised during SQL generation"""
    pass


class ConfigurationException(RAGServiceException):
    """Exception raised for configuration errors"""
    pass


class DatabaseException(RAGServiceException):
    """Exception raised for database operations"""
    pass


class AuthenticationException(RAGServiceException):
    """Exception raised for authentication errors"""
    pass


class ValidationException(RAGServiceException):
    """Exception raised for validation errors"""
    pass


class RateLimitException(RAGServiceException):
    """Exception raised when rate limit is exceeded"""
    pass


class DocumentLoaderException(RAGServiceException):
    """Exception raised by document loader service"""
    pass