"""
Request schemas for RAG system
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class RAGQueryRequest(BaseModel):
    """RAG query request"""
    
    query: str = Field(..., min_length=1, max_length=1000, description="User question")
    k: Optional[int] = Field(
        default=5, 
        ge=1, 
        le=20, 
        description="Number of similar documents to retrieve"
    )
    confidence_threshold: Optional[float] = Field(
        default=0.7, 
        ge=0.0, 
        le=1.0, 
        description="Minimum similarity threshold"
    )
    include_sources: Optional[bool] = Field(
        default=True, 
        description="Whether to include source documents in response"
    )
    backend_data: Optional[bool] = Field(
        default=True,
        description="Whether to fetch backend data"
    )
    
    @validator("query")
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class VectorStoreQuery(BaseModel):
    """Vector store similarity search request"""
    
    query: str = Field(..., min_length=1, max_length=1000)
    k: Optional[int] = Field(default=5, ge=1, le=50, description="Number of similar documents to return")
    similarity_threshold: Optional[float] = Field(
        default=0.7, 
        ge=0.0, 
        le=1.0, 
        description="Similarity threshold for filtering results"
    )
    metadata_filter: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadata filters for search"
    )


class DocumentIngest(BaseModel):
    """Document ingestion request"""
    
    content: str = Field(..., min_length=1, description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Document metadata"
    )
    document_type: Optional[str] = Field(default="text", description="Type of document")
    source: Optional[str] = Field(None, description="Document source")
    
    @validator("content")
    def content_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()


class DatabaseConnectionTest(BaseModel):
    """Database connection test request"""
    
    query: Optional[str] = Field(
        default="SELECT 1",
        description="Test query to execute"
    )
    timeout: Optional[int] = Field(
        default=30,
        ge=1,
        le=300,
        description="Query timeout in seconds"
    )