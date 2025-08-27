"""
공통 응답 유틸리티
API 응답 표준화, 에러 처리, 페이징 등을 담당
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import HTTPException, status
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class APIResponse(BaseModel):
    """표준 API 응답 포맷"""
    success: bool = True
    data: Optional[Any] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class PaginatedResponse(BaseModel):
    """페이징된 응답 포맷"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


def success_response(data: Any = None, message: str = "Success") -> APIResponse:
    """성공 응답 생성"""
    return APIResponse(
        success=True,
        data=data,
        message=message
    )


def error_response(
    message: str, 
    error_code: str = "INTERNAL_ERROR", 
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
) -> HTTPException:
    """에러 응답 생성"""
    logger.error(f"API Error: {error_code} - {message}")
    
    return HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "message": message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat()
        }
    )


def validation_error_response(errors: List[Dict[str, Any]]) -> HTTPException:
    """유효성 검사 에러 응답"""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "success": False,
            "message": "Validation failed",
            "error_code": "VALIDATION_ERROR",
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }
    )


def not_found_response(resource: str = "Resource") -> HTTPException:
    """404 에러 응답"""
    return error_response(
        message=f"{resource} not found",
        error_code="NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND
    )


def bad_request_response(message: str) -> HTTPException:
    """400 에러 응답"""
    return error_response(
        message=message,
        error_code="BAD_REQUEST", 
        status_code=status.HTTP_400_BAD_REQUEST
    )


def create_paginated_response(
    items: List[Any],
    total: int,
    page: int,
    size: int
) -> PaginatedResponse:
    """페이징된 응답 생성"""
    pages = (total + size - 1) // size if size > 0 else 1
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


def validate_date_range(start_date: date, end_date: date) -> None:
    """날짜 범위 유효성 검사"""
    if start_date > end_date:
        raise bad_request_response("start_date must be before or equal to end_date")
    
    # 최대 1년 범위 제한
    if (end_date - start_date).days > 365:
        raise bad_request_response("Date range cannot exceed 365 days")


def validate_day_type(day_type: str) -> None:
    """요일 타입 유효성 검사"""
    valid_day_types = ["weekday", "weekend", "all"]
    if day_type not in valid_day_types:
        raise bad_request_response(f"day_type must be one of: {valid_day_types}")


def validate_district_name(district_name: str) -> None:
    """자치구명 유효성 검사"""
    valid_districts = [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", 
        "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", 
        "종로구", "중구", "중랑구"
    ]
    
    if district_name not in valid_districts:
        raise bad_request_response(f"Invalid district_name: {district_name}")


def format_efficiency_grade(efficiency_ratio: float) -> str:
    """효율성 지수를 등급으로 변환"""
    if efficiency_ratio >= 20:
        return "A"
    elif efficiency_ratio >= 10:
        return "B"
    elif efficiency_ratio >= 5:
        return "C"
    elif efficiency_ratio >= 1:
        return "D"
    else:
        return "F"


def format_demand_level(total_passengers: int) -> str:
    """승객수를 수요 수준으로 변환"""
    if total_passengers >= 2000000:
        return "peak"
    elif total_passengers >= 1500000:
        return "high"
    elif total_passengers >= 1000000:
        return "medium"
    else:
        return "low"


def format_delay_level(avg_trip_time: float) -> str:
    """평균 운행시간을 지연 수준으로 변환"""
    # 기준 시간을 90분으로 가정
    base_time = 90.0
    delay_ratio = avg_trip_time / base_time
    
    if delay_ratio >= 1.5:
        return "heavy"
    elif delay_ratio >= 1.3:
        return "congested" 
    elif delay_ratio >= 1.1:
        return "normal"
    else:
        return "smooth"


def calculate_delay_index(avg_trip_time: float, base_time: float = 90.0) -> float:
    """지연 지수 계산 (기준 시간 대비 %)"""
    return min((avg_trip_time / base_time) * 100, 200.0)


def log_api_request(endpoint: str, params: Dict[str, Any], execution_time: float):
    """API 요청 로깅"""
    logger.info(
        f"API Request: {endpoint} | "
        f"Params: {params} | "
        f"Execution: {execution_time:.3f}s"
    )


def handle_database_error(error: Exception) -> HTTPException:
    """데이터베이스 에러 처리"""
    logger.error(f"Database error: {str(error)}")
    
    error_str = str(error).lower()
    
    if "connection" in error_str:
        return error_response(
            message="Database connection failed",
            error_code="DB_CONNECTION_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    elif "timeout" in error_str:
        return error_response(
            message="Database query timeout",
            error_code="DB_TIMEOUT_ERROR", 
            status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )
    else:
        return error_response(
            message="Database operation failed",
            error_code="DB_OPERATION_ERROR"
        )