"""
SQL 실행을 위한 Pydantic 스키마
"""

from pydantic import BaseModel, Field
from typing import List, Any, Optional


class SQLExecuteRequest(BaseModel):
    """SQL 실행 요청 스키마"""
    sql: str = Field(..., description="실행할 SQL 쿼리")
    read_only: bool = Field(True, description="읽기 전용 모드 (기본값: True)")
    limit: Optional[int] = Field(default=1000, description="결과 행 수 제한")


class SQLExecuteResponse(BaseModel):
    """SQL 실행 응답 스키마"""
    success: bool = Field(..., description="실행 성공 여부")
    data: List[dict] = Field(..., description="조회 결과 데이터")
    columns: List[str] = Field(..., description="컬럼명 목록")
    row_count: int = Field(..., description="결과 행 수")
    execution_time: float = Field(..., description="실행 시간 (초)")
    error: Optional[str] = Field(None, description="오류 메시지 (실패 시)")


class SQLValidateRequest(BaseModel):
    """SQL 검증 요청 스키마"""
    sql: str = Field(..., description="검증할 SQL 쿼리")


class SQLValidateResponse(BaseModel):
    """SQL 검증 응답 스키마"""
    is_valid: bool = Field(..., description="SQL 유효성")
    is_safe: bool = Field(..., description="안전한 쿼리인지 여부 (읽기 전용)")
    error: Optional[str] = Field(None, description="검증 오류 메시지")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지 목록")