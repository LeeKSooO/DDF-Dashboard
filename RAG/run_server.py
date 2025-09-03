#!/usr/bin/env python3
"""
RAG Server 실행 스크립트

사용법:
    python run_server.py

Swagger UI 접속:
    http://localhost:8001/api/v1/docs
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """RAG 서버 실행"""
    
    print("🚀 DDF RAG Server 시작 중...")
    print("📝 Swagger UI: http://localhost:8001/api/v1/docs")
    print("📖 ReDoc: http://localhost:8001/api/v1/redoc")
    print("🔄 서버를 중지하려면 Ctrl+C를 누르세요")
    print("-" * 60)
    
    # 환경변수 설정 (선택사항)
    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("PORT", "8001") 
    os.environ.setdefault("LOG_LEVEL", "info")
    
    # 서버 실행
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8001)),
        reload=True,  # 개발용 자동 재시작
        log_level=os.getenv("LOG_LEVEL", "info"),
        access_log=True
    )

if __name__ == "__main__":
    main()