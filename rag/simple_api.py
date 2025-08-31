#!/usr/bin/env python3
"""
Simple RAG API to test container functionality
"""
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
import uvicorn

# FastAPI 앱 초기화
app = FastAPI(
    title="DDF-MSTGCN RAG API (Simple)",
    description="Simple version for testing",
    version="1.0.0"
)

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    status: str

@app.get("/")
async def root():
    """헬스체크 엔드포인트"""
    return {"message": "DDF-MSTGCN RAG API (Simple)", "status": "running"}

@app.get("/health")
async def health_check():
    """상세 헬스체크"""
    return {
        "status": "healthy",
        "service": "DDF-MSTGCN RAG (Simple)",
        "message": "Container is working properly"
    }

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Simple RAG 질의 처리"""
    return QueryResponse(
        answer=f"This is a test response for: {request.question}",
        status="success"
    )

if __name__ == "__main__":
    # 서버 실행
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        log_level="info"
    )