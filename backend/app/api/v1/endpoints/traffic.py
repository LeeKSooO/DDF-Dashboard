"""
시간대별 교통량 컴포넌트 API 엔드포인트
서울시/구별 월별 시간대별 승하차 패턴 제공
"""

from typing import Optional, Literal
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.db.session import get_db
from app.services.trafficService import HourlyTrafficService
from app.schemas.traffic import HourlyTrafficSchema
from app.utils.response import (
    success_response,
    bad_request_response,
    log_api_request
)

router = APIRouter()


@router.get("/hourly", response_model=HourlyTrafficSchema)
async def get_hourly_traffic(
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01, 프론트에서 -01 추가)"),
    region_type: Literal["seoul", "district"] = Query(..., description="지역 구분 ('seoul': 서울시 전체, 'district': 특정 구)"),
    district_name: Optional[str] = Query(None, description="구명 (region_type이 'district'일 때 필수)"),
    db: AsyncSession = Depends(get_db)
):
    """
    시간대별 교통량 컴포넌트 API
    
    월별 기준으로 시간대별(0-23시) 평균 승하차 인원을 평일/주말로 구분하여 제공합니다.
    서울시 전체 또는 특정 구 단위로 조회 가능합니다.
    
    **사용 예시**:
    - 서울시 전체: `?analysis_month=2025-07-01&region_type=seoul`
    - 강남구: `?analysis_month=2025-07-01&region_type=district&district_name=강남구`
    
    **응답 데이터**:
    - `weekday_patterns`: 평일 0-23시 시간별 승하차 패턴
    - `weekend_patterns`: 주말 0-23시 시간별 승하차 패턴  
    - `peak_hours`: 자동 계산된 피크 시간대 정보
    - 총 승객수 및 평일/주말 비율 통계
    
    **참고**: 현재 2025년 7월 16일~31일 데이터만 존재합니다.
    """
    start_time = time.time()
    
    print(f"[API DEBUG] ===== HOURLY TRAFFIC REQUEST STARTED =====")
    print(f"[API DEBUG] Request: {analysis_month}, {region_type}, {district_name}")
    
    try:
        # 서비스 호출
        service = HourlyTrafficService()
        
        print("[API DEBUG] Calling service method...")
        result = await service.get_hourly_traffic(
            db=db,
            analysis_month=analysis_month,
            region_type=region_type,
            district_name=district_name
        )
        
        print(f"[API DEBUG] Service returned: {type(result)}")
        if hasattr(result, 'weekday_patterns'):
            total = sum(p.avg_total_passengers for p in result.weekday_patterns)
            print(f"[API DEBUG] Weekday total: {total}")
        
        # 처리 시간
        processing_time = round((time.time() - start_time) * 1000, 2)
        print(f"[API DEBUG] Processing time: {processing_time}ms")
        
        # Pydantic 모델을 직접 반환
        return result
        
    except Exception as e:
        print(f"[API DEBUG] Error: {e}")
        import traceback
        print(f"[API DEBUG] Traceback: {traceback.format_exc()}")
        raise


@router.get("/hourly/health")
async def health_check():
    """
    시간대별 교통량 API 상태 확인
    """
    print("[API DEBUG] ===== HEALTH CHECK CALLED =====")
    return success_response(
        data={
            "status": "healthy",
            "service": "hourly-traffic-component",
            "endpoints": ["/hourly"],
            "description": "월별 시간대별 교통량 패턴 분석 API"
        },
        message="Hourly Traffic API is running"
    )


@router.get("/hourly/info")
async def api_info():
    """
    시간대별 교통량 API 정보
    """
    return success_response(
        data={
            "component_name": "시간대별 교통량 컴포넌트",
            "data_source": "station_passenger_history 테이블",
            "available_period": "2025-07 (2025년 7월 16일~31일)",
            "region_types": ["seoul", "district"],
            "seoul_districts": [
                "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
                "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구",
                "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
            ],
            "data_structure": {
                "weekday_patterns": "평일 0-23시 시간별 승하차 패턴 (24개 항목)",
                "weekend_patterns": "주말 0-23시 시간별 승하차 패턴 (24개 항목)",
                "peak_hours": "평일 아침/저녁, 주말 피크 시간 정보",
                "statistics": "총 승객수, 평일/주말 비율"
            }
        },
        message="Hourly Traffic Component API Information"
    )