"""
Response schemas
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    """Response status enumeration"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class BaseResponse(BaseModel):
    """Base response model"""
    
    status: ResponseStatus = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")


class HealthResponse(BaseResponse):
    """Health check response"""
    
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    services: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Status of various services"
    )
    version: str = Field(default="1.0.0", description="Application version")
    uptime: Optional[float] = Field(None, description="Application uptime in seconds")


class ExtractedTag(BaseModel):
    """Extracted tag information"""
    
    category: str = Field(..., description="Tag category")
    subcategory: Optional[str] = Field(None, description="Tag subcategory")
    value: str = Field(..., description="Tag value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Tag extraction confidence")
    span: Optional[Dict[str, int]] = Field(None, description="Text span information")


class SQLMetadata(BaseModel):
    """SQL generation metadata"""
    
    pattern: str = Field(..., description="Matched pattern")
    template_used: Optional[str] = Field(None, description="SQL template used")
    extracted_tags: List[ExtractedTag] = Field(default_factory=list)
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    model_used: Optional[str] = Field(None, description="LLM model used")


class QueryResponse(BaseResponse):
    """SQL query generation response"""
    
    query: str = Field(..., description="Original natural language query")
    sql: Optional[str] = Field(None, description="Generated SQL query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Generation confidence")
    explanation: Optional[str] = Field(None, description="Query explanation")
    metadata: Optional[SQLMetadata] = Field(None, description="Generation metadata")
    similar_queries: Optional[List[str]] = Field(
        default_factory=list,
        description="Similar queries from knowledge base"
    )


class ChatMessage(BaseModel):
    """Chat message model"""
    
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseResponse):
    """Conversational chat response"""
    
    message: str = Field(..., description="Original user message")
    response: str = Field(..., description="Assistant response")
    conversation_id: str = Field(..., description="Conversation ID")
    sql: Optional[str] = Field(None, description="Generated SQL if requested")
    confidence: Optional[float] = Field(None, description="Response confidence")
    conversation_history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Conversation history"
    )


class SimilarDocument(BaseModel):
    """Similar document from vector search"""
    
    content: str = Field(..., description="Document content")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    source: Optional[str] = Field(None, description="Document source")


class VectorSearchResponse(BaseResponse):
    """Vector similarity search response"""
    
    query: str = Field(..., description="Search query")
    results: List[SimilarDocument] = Field(default_factory=list)
    total_results: int = Field(default=0, description="Total number of results")
    search_time: Optional[float] = Field(None, description="Search time in seconds")


class DocumentIngestResponse(BaseResponse):
    """Document ingestion response"""
    
    document_id: str = Field(..., description="Ingested document ID")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    embeddings_generated: int = Field(default=0, description="Number of embeddings generated")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")


class DatabaseTestResponse(BaseResponse):
    """Database connection test response"""
    
    connected: bool = Field(..., description="Connection status")
    response_time: Optional[float] = Field(None, description="Query response time")
    result: Optional[List[Dict[str, Any]]] = Field(None, description="Query result")
    error_details: Optional[str] = Field(None, description="Error details if failed")


class ErrorResponse(BaseResponse):
    """Error response"""
    
    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error_code: Optional[str] = Field(None, description="Error code")
    error_type: Optional[str] = Field(None, description="Error type")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    traceback: Optional[str] = Field(None, description="Error traceback (debug mode only)")


class MetricsResponse(BaseResponse):
    """System metrics response"""
    
    total_requests: int = Field(default=0)
    successful_requests: int = Field(default=0)
    failed_requests: int = Field(default=0)
    average_response_time: float = Field(default=0.0)
    active_connections: int = Field(default=0)
    memory_usage: Optional[Dict[str, Union[int, float]]] = Field(None)
    cpu_usage: Optional[float] = Field(None)