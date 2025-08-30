"""
구별 교통 특이패턴 분석 API 엔드포인트
웹 대시보드에서 특정 구를 선택했을 때, 해당 구의 6가지 특이패턴 정류장을 제공
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_db
from app.services.anomalyPatternService import AnomalyPatternService
from app.schemas.anomalyPattern import (
    AnomalyPatternResponse,
    AnomalyPatternRequest,
    AnomalyPatternFilterSchema,
    WeekendDominantStationSchema,
    NightDemandStationSchema,
    RushHourStationSchema,
    LunchTimeStationSchema,
    AreaTypeStationSchema,
    HighVolatilityStationSchema
)
from pydantic import BaseModel
from app.utils.response import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


# ==========================================
# 개별 패턴 분석 엔드포인트들
# ==========================================

@router.get("/weekend-dominant")
async def get_weekend_dominant_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """1. 주말 우세 정류장 분석"""
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting weekend dominant stations for {district_name}")
        
        result = await service.get_weekend_dominant_stations(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result,
            message=f"Weekend dominant stations for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting weekend dominant stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/night-demand")
async def get_night_demand_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """2. 심야시간 고수요 정류장 분석 (23-03시)"""
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting night demand stations for {district_name}")
        
        result = await service.get_night_demand_stations(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result,
            message=f"Night demand stations for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting night demand stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rush-hour")
async def get_rush_hour_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """3. 러시아워 집중 정류장 분석 (구현 필요)"""
    return success_response(
        data=[],
        message="Rush hour analysis - coming soon"
    )


@router.get("/lunch-time")
async def get_lunch_time_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """4. 점심시간 스파이크 정류장 분석 (구현 필요)"""
    return success_response(
        data=[],
        message="Lunch time analysis - coming soon"
    )


@router.get("/area-type")
async def get_area_type_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """5. 지역 유형별 정류장 분석 (구현 필요)"""
    return success_response(
        data=[],
        message="Area type analysis - coming soon"
    )


@router.get("/high-volatility")
async def get_high_volatility_stations(
    district_name: str = Query(..., description="구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="상위 N개 정류장"),
    db: AsyncSession = Depends(get_db)
):
    """6. 고변동성 정류장 분석 (구현 필요)"""
    return success_response(
        data=[],
        message="High volatility analysis - coming soon"
    )


# ==========================================
# 종합 분석 엔드포인트 (기존 유지)
# ==========================================

@router.get("/analyze", response_model=AnomalyPatternResponse)
async def analyze_anomaly_patterns(
    district_name: str = Query(..., description="분석 대상 구명"),
    analysis_month: date = Query(..., description="분석월 (YYYY-MM-DD)"),
    top_n: int = Query(5, ge=1, le=10, description="각 패턴별 상위 N개"),
    db: AsyncSession = Depends(get_db)
):
    """구별 교통 특이패턴 종합 분석 (6개 패턴 모두)"""
    try:
        service = AnomalyPatternService()
        
        logger.info(f"Analyzing anomaly patterns for {district_name}")
        
        # Create filters object from query parameters
        from app.schemas.anomalyPattern import AnomalyPatternFilterSchema
        filters = AnomalyPatternFilterSchema(top_n=top_n)
        
        result = await service.analyze_district_anomaly_patterns(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            filters=filters
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing anomaly patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Anomaly Pattern API 상태 확인"""
    return success_response(
        data={
            "status": "healthy",
            "service": "anomaly-pattern-api",
            "endpoints": [
                "/weekend-dominant",
                "/night-demand", 
                "/rush-hour",
                "/lunch-time",
                "/area-type",
                "/high-volatility",
                "/analyze"
            ],
            "description": "구별 교통 특이패턴 분석 API - 6개 개별 엔드포인트 + 종합 분석"
        },
        message="Anomaly Pattern API is running"
    )