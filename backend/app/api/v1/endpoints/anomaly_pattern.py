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
    IntegratedAnomalyPatternResponse,
    AnomalyPatternRequest,
    AnomalyPatternFilterSchema,
    WeekendDominantStationSchema,
    NightDemandStationSchema,
    RushHourStationSchema,
    LunchTimeStationSchema,
    AreaTypeAnalysisSchema,
    UnderutilizedStationSchema
)
from pydantic import BaseModel
from app.utils.response import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


# ==========================================
# 개별 패턴 분석 엔드포인트들
# ==========================================

@router.get(
    "/weekend-dominant",
    summary="주말 우세 정류장 분석",
    description="""
    **주말 고수요 정류장 패턴 분석**
    
    특정 구의 주말(토요일, 일요일) 총 교통량 기준으로 상위 정류장을 선별하고,
    각 정류장의 시간대별 교통량 분석을 통해 주말 피크 시간대를 추출합니다.
    
    **분석 기준:**
    - 주말 총 교통량(승차 + 하차) 기준 정렬
    - 시간대별 교통량 분석으로 피크 시간대 TOP 3 추출
    - 구 평균 대비 주말 수요 배수 계산
    
    **활용 사례:**
    - 관광지/명소 근처 정류장 식별
    - 주말 특화 버스 노선 운영 계획
    - 레저/쇼핑 지역 대중교통 수요 파악
    """,
    response_description="주말 우세 정류장 목록과 상세 분석 데이터",
)
async def get_weekend_dominant_stations(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="조회할 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
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


@router.get(
    "/night-demand",
    summary="심야시간 고수요 정류장 분석",
    description="""
    **심야시간 고수요 정류장 패턴 분석 (23:00-03:00)**
    
    심야시간대(23시-03시) 총 승차인원 기준으로 상위 정류장을 선별하고,
    시간대별 세부 승차량 분석을 통해 심야 교통 패턴을 파악합니다.
    
    **분석 기준:**
    - 심야시간(23,0,1,2,3시) 총 승차인원 기준 정렬
    - 시간대별 세부 승차량 [23시, 0시, 1시, 2시, 3시] 제공
    - 구 평균 대비 심야수요 배수 계산
    
    **활용 사례:**
    - 야간 버스 노선 운영 계획 수립
    - 심야 교통수요가 높은 상업지역 파악
    - 24시간 운영 시설 근처 정류장 식별
    - 야간 치안 및 안전 관리 우선 지역 선정
    """,
    response_description="심야시간 고수요 정류장 목록과 시간대별 승차량 데이터",
)
async def get_night_demand_stations(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="조회할 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
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


@router.get(
    "/rush-hour",
    summary="러시아워 고수요 정류장 분석",
    description="""
    **러시아워 고수요 정류장 패턴 분석**
    
    출퇴근 러시아워(오전 06-09시, 오후 17-19시) 승차인원 기준으로 
    오전/오후 각각 상위 정류장을 선별하여 출퇴근 교통 패턴을 분석합니다.
    
    **분석 기준:**
    - 오전 러시아워: 06-08시 총 승차인원 (평일만)
    - 오후 러시아워: 17-19시 총 승차인원 (평일만)  
    - 구 평균 대비 러시아워 수요 배수 계산
    - 시간대별 세부 승차량 제공
    
    **활용 사례:**
    - 출퇴근 시간대 버스 증편 계획
    - 업무지구 및 주거지역 교통 패턴 파악
    - 교통 혼잡 완화를 위한 배차 간격 조정
    - 직장인 밀집 지역 식별
    """,
    response_description="오전/오후 러시아워 고수요 정류장 분석 결과",
)
async def get_rush_hour_stations(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="조회할 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting rush hour stations for {district_name}")
        
        result = await service.get_rush_hour_stations(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result,
            message=f"Rush hour stations for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting rush hour stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/lunch-time",
    summary="점심시간 특화 정류장 분석",
    description="""
    **점심시간 특화 정류장 패턴 분석 (11:00-13:00)**
    
    점심시간대(11-13시) 하차인원 기준으로 상위 정류장을 선별하여
    음식점가, 상업지구 등 점심 목적지 정류장을 식별합니다.
    
    **분석 기준:**
    - 점심시간(11,12,13시) 총 하차인원 기준 정렬 (평일만)
    - 시간대별 하차량 [11시, 12시, 13시] 제공
    - 구 평균 대비 점심시간 하차인원 배수 계산
    
    **활용 사례:**
    - 음식점가 및 상업지구 식별
    - 점심시간 셔틀버스 운영 계획
    - 업무지구 내 식음료 인프라 파악
    - 점심시간 교통 집중도 관리
    """,
    response_description="점심시간 특화 정류장 목록과 시간대별 하차량 데이터",
)
async def get_lunch_time_stations(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="조회할 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting lunch time stations for {district_name}")
        
        result = await service.get_lunch_time_stations(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result,
            message=f"Lunch time stations for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting lunch time stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/area-type", 
    summary="지역 특성별 정류장 분석",
    description="""
    **지역 특성별 정류장 분석 (주거지역/업무지역)**
    
    출퇴근시간대 승하차 불균형 비율을 통해 주거지역과 업무지역 특성을 가진 
    정류장을 각각 식별하여 도시 기능별 교통 패턴을 분석합니다.
    
    **분석 기준:**
    - 출퇴근 시간대: 06-09시(출근), 17-19시(퇴근) 평일만
    - 1000명 이상 교통량 필터링으로 신뢰성 확보
    - 주거지역: (출근승차/출근하차) × (퇴근하차/퇴근승차) > 1.0
    - 업무지역: (출근하차/출근승차) × (퇴근승차/퇴근하차) > 1.0
    
    **활용 사례:**
    - 도시계획 및 토지이용 패턴 파악
    - 주거지역 vs 업무지역 대중교통 수요 특성 분석
    - 지역별 맞춤형 교통정책 수립
    - 도시 기능 분석을 통한 인프라 개발 계획
    """,
    response_description="주거지역 정류장과 업무지역 정류장 분석 결과",
)
async def get_area_type_analysis(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="조회할 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting area type analysis for {district_name}")
        
        result = await service.get_area_type_analysis(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result.dict(),
            message=f"Area type analysis for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting area type analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/underutilized",
    summary="저활용 정류장 분석",
    description="""
    **저활용 정류장 분석 (운영 최적화 대상)**
    
    구별 하위 25% 교통량 기준으로 저활용 정류장을 선별하고,
    연결 노선수와 교통량 효율성을 분석하여 운영 최적화 방안을 제시합니다.
    
    **분석 기준:**
    - 구별 하위 25% 교통량 기준으로 저활용 정류장 선별
    - 일평균 승하차 인원 기준 오름차순 정렬 (가장 적은 승객부터)
    - 구 평균 대비 활용률 (%) 계산
    - 효율성 점수: 일평균 승객수 ÷ 연결된 버스 노선수
    
    **활용 사례:**
    - 버스 노선 통폐합 검토 대상 식별  
    - 운영비용 대비 효과가 낮은 정류장 파악
    - 대중교통 서비스 효율성 개선 계획
    - 지역별 교통 인프라 재배치 전략 수립
    """,
    response_description="저활용 정류장 목록과 운영 효율성 지표",
)
async def get_underutilized_stations(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(10, ge=1, le=20, description="조회할 상위 정류장 수 (1-20개)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = AnomalyPatternService()
        logger.info(f"Getting underutilized stations for {district_name}")
        
        result = await service.get_underutilized_stations(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=[station.dict() for station in result],
            message=f"Underutilized stations for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting underutilized stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 종합 분석 엔드포인트 (기존 유지)
# ==========================================

@router.get(
    "/integration",
    summary="교통 특이패턴 통합 분석",
    description="""
    **구별 교통 특이패턴 통합 분석 (6개 패턴 종합)**
    
    한 번의 호출로 특정 구의 모든 교통 특이패턴을 종합 분석하여
    완전한 교통 패턴 인사이트를 제공합니다.
    
    **포함되는 6가지 패턴:**
    1. **주말 우세 정류장**: 주말 고수요 관광지/레저 정류장
    2. **심야시간 고수요**: 24시간 활성화된 상업지역 정류장  
    3. **러시아워 고수요**: 출퇴근 시간대 집중 정류장
    4. **점심시간 특화**: 음식점가/상업지구 점심 정류장
    5. **지역 특성별**: 주거지역 vs 업무지역 정류장 구분
    6. **저활용 정류장**: 운영 최적화 대상 정류장
    
    **분석 장점:**
    - 한 번의 API 호출로 전체 패턴 파악
    - 구별 교통 특성의 종합적 이해
    - 다양한 시간대별/목적별 교통 패턴 동시 제공
    
    **활용 사례:**
    - 구별 종합 교통정책 수립
    - 대중교통 운영 전략 수립
    - 도시계획 및 인프라 개발 계획
    - 교통 데이터 기반 의사결정 지원
    """,
    response_description="6개 패턴의 통합 분석 결과와 메타 정보",
)
async def get_integrated_anomaly_patterns(
    district_name: str = Query(..., description="분석 대상 구명 (예: 강남구, 마포구)"),
    analysis_month: date = Query(..., description="분석 기준월 (YYYY-MM-DD 형식, 월 첫째 날)"),
    top_n: int = Query(5, ge=1, le=10, description="각 패턴별 상위 정류장 수 (1-10개)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = AnomalyPatternService()
        
        logger.info(f"Getting integrated anomaly patterns for {district_name}")
        
        result = await service.get_integrated_anomaly_patterns(
            db=db,
            district_name=district_name,
            analysis_month=analysis_month,
            top_n=top_n
        )
        
        return success_response(
            data=result.dict(),
            message=f"Integrated anomaly patterns analysis for {district_name}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing anomaly patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    summary="API 상태 확인",
    description="""
    **Anomaly Pattern API 서비스 상태 확인**
    
    API 서비스의 정상 작동 여부와 사용 가능한 모든 엔드포인트 목록을 제공합니다.
    
    **제공 정보:**
    - 서비스 상태 (healthy/unhealthy)
    - 사용 가능한 엔드포인트 목록
    - API 서비스 설명
    
    **활용 사례:**
    - 서비스 모니터링 및 헬스체크
    - API 엔드포인트 목록 확인
    - 시스템 상태 진단
    """,
    response_description="API 서비스 상태 정보와 엔드포인트 목록",
)
async def health_check():
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
                "/underutilized",
                "/integration"
            ],
            "description": "구별 교통 특이패턴 분석 API - 6개 개별 엔드포인트 + 종합 분석"
        },
        message="Anomaly Pattern API is running"
    )