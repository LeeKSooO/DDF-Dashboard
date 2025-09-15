"""
SQL 실행 API 엔드포인트
RAG Text-to-SQL 기능을 위한 안전한 SQL 실행
"""

import time
import logging
import re
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db
from app.schemas.sql import SQLExecuteRequest, SQLExecuteResponse, SQLValidateRequest, SQLValidateResponse

router = APIRouter()
logger = logging.getLogger(__name__)


class SQLSafetyValidator:
    """SQL 안전성 검증 클래스"""

    # 허용되지 않는 SQL 명령어들
    FORBIDDEN_COMMANDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
        'EXEC', 'EXECUTE', 'CALL', 'DECLARE'
    ]

    # 허용되지 않는 함수들
    FORBIDDEN_FUNCTIONS = [
        'pg_sleep', 'pg_read_file', 'pg_write_file', 'pg_ls_dir',
        'copy', 'lo_import', 'lo_export'
    ]

    @classmethod
    def validate_sql(cls, sql: str) -> SQLValidateResponse:
        """SQL 쿼리 안전성 검증"""
        sql_upper = sql.upper().strip()
        warnings = []

        # 빈 쿼리 검사
        if not sql.strip():
            return SQLValidateResponse(
                is_valid=False,
                is_safe=False,
                error="빈 SQL 쿼리입니다."
            )

        # 금지된 명령어 검사
        for cmd in cls.FORBIDDEN_COMMANDS:
            if re.search(rf'\b{cmd}\b', sql_upper):
                return SQLValidateResponse(
                    is_valid=False,
                    is_safe=False,
                    error=f"허용되지 않는 SQL 명령어입니다: {cmd}"
                )

        # 금지된 함수 검사
        for func in cls.FORBIDDEN_FUNCTIONS:
            if re.search(rf'\b{func}\b', sql_upper):
                return SQLValidateResponse(
                    is_valid=False,
                    is_safe=False,
                    error=f"허용되지 않는 함수입니다: {func}"
                )

        # SELECT 문인지 확인
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            warnings.append("SELECT 또는 WITH 문만 권장됩니다.")

        # 세미콜론 다중 명령어 검사
        if sql.count(';') > 1:
            warnings.append("다중 명령어는 권장되지 않습니다.")

        return SQLValidateResponse(
            is_valid=True,
            is_safe=True,
            warnings=warnings
        )


@router.post("/validate", response_model=SQLValidateResponse)
async def validate_sql(request: SQLValidateRequest) -> SQLValidateResponse:
    """
    SQL 쿼리 유효성 및 안전성 검증
    """
    try:
        return SQLSafetyValidator.validate_sql(request.sql)
    except Exception as e:
        logger.error(f"SQL validation error: {e}")
        return SQLValidateResponse(
            is_valid=False,
            is_safe=False,
            error=f"검증 중 오류 발생: {str(e)}"
        )


@router.post("/execute", response_model=SQLExecuteResponse)
async def execute_sql(
    request: SQLExecuteRequest,
    db: AsyncSession = Depends(get_db)
) -> SQLExecuteResponse:
    """
    안전한 SQL 쿼리 실행 (읽기 전용)
    """
    start_time = time.time()

    try:
        # SQL 안전성 검증
        validation = SQLSafetyValidator.validate_sql(request.sql)
        if not validation.is_valid or not validation.is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"안전하지 않은 SQL 쿼리: {validation.error}"
            )

        # LIMIT 강제 적용 (성능 보호)
        sql_to_execute = request.sql.strip()
        if request.limit and request.limit > 0:
            if not re.search(r'\bLIMIT\s+\d+\b', sql_to_execute.upper()):
                sql_to_execute = f"SELECT * FROM ({sql_to_execute}) subquery LIMIT {request.limit}"

        logger.info(f"Executing SQL: {sql_to_execute[:100]}...")

        # SQL 실행
        result = await db.execute(text(sql_to_execute))
        rows = result.fetchall()

        # 결과 처리
        if rows:
            columns = list(rows[0]._mapping.keys())
            data = [dict(row._mapping) for row in rows]
        else:
            columns = []
            data = []

        execution_time = time.time() - start_time

        logger.info(f"SQL executed successfully: {len(data)} rows in {execution_time:.3f}s")

        return SQLExecuteResponse(
            success=True,
            data=data,
            columns=columns,
            row_count=len(data),
            execution_time=execution_time
        )

    except HTTPException:
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"SQL execution failed: {error_msg}")

        return SQLExecuteResponse(
            success=False,
            data=[],
            columns=[],
            row_count=0,
            execution_time=execution_time,
            error=error_msg
        )


@router.get("/health")
async def sql_health_check(db: AsyncSession = Depends(get_db)):
    """SQL 실행 엔드포인트 헬스 체크"""
    try:
        result = await db.execute(text("SELECT 1 as health_check"))
        result.fetchone()
        return {"status": "healthy", "service": "sql-executor"}
    except Exception as e:
        logger.error(f"SQL health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")