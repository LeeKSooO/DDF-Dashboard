"""
서울시 교통량 히트맵 컴포넌트 API 엔드포인트
구별/정류장별 교통량 집계와 지도 경계 데이터 제공
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.db.session import get_db
from app.services.heatmapService import HeatmapService
from app.schemas.heatmap import SeoulHeatmapSchema
from app.utils.response import (
    success_response,
    log_api_request
)

router = APIRouter()


@router.get("/seoul", response_model=SeoulHeatmapSchema)
async def get_seoul_heatmap(
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01, 프론트에서 -01 추가)"),
    include_station_details: bool = Query(
        True, 
        description="정류장별 상세 데이터 포함 여부 (false시 구별 집계만 반환)"
    ),
    min_traffic_threshold: Optional[int] = Query(
        None, 
        ge=0, 
        description="최소 교통량 임계값 (이하 정류장 제외)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    서울시 교통량 히트맵 데이터 조회
    
    **주요 기능**:
    - 서울시 25개 구별 교통량 집계 및 순위
    - 구별 경계 좌표 데이터 (지도 렌더링용)
    - 정류장별 상세 교통량 및 좌표 (선택적)
    - 히트맵 색상 구간을 위한 통계 (사분위수, 최대/최소값)
    
    **사용 예시**:
    - 구별 집계만: `?analysis_month=2025-07-01&include_station_details=false`
    - 상세 데이터: `?analysis_month=2025-07-01&include_station_details=true`
    - 필터링: `?analysis_month=2025-07-01&min_traffic_threshold=5000`
    
    **응답 구조**:
    ```json
    {
      "seoul_boundary": "서울시 전체 경계 좌표",
      "districts": [
        {
          "district_name": "강남구", 
          "boundary": "구 경계 좌표",
          "total_traffic": 10374028,
          "traffic_rank": 1,
          "stations": [{"station_id": "...", "coordinate": {...}}]
        }
      ],
      "statistics": {
        "max_district_traffic": 10374028,
        "district_traffic_quartiles": [Q1, Q2, Q3]
      }
    }
    ```
    
    **참고**: 현재 2025년 7월 16일~31일 데이터만 존재합니다.
    """
    start_time = time.time()
    
    print(f"[HEATMAP API] ===== REQUEST STARTED =====")
    print(f"[HEATMAP API] Params: month={analysis_month}, details={include_station_details}, threshold={min_traffic_threshold}")
    
    try:
        # 서비스 호출
        service = HeatmapService()
        
        print("[HEATMAP API] Calling heatmap service...")
        result = await service.get_seoul_heatmap(
            db=db,
            analysis_month=analysis_month,
            include_station_details=include_station_details,
            min_traffic_threshold=min_traffic_threshold
        )
        
        print(f"[HEATMAP API] Service returned: {len(result.districts)} districts")
        print(f"[HEATMAP API] Seoul total traffic: {result.statistics.total_seoul_traffic:,}")
        print(f"[HEATMAP API] Total stations: {result.statistics.total_stations}")
        
        # 처리 시간
        processing_time = round((time.time() - start_time) * 1000, 2)
        print(f"[HEATMAP API] Processing time: {processing_time}ms")
        
        # 로깅
        log_api_request(
            endpoint="heatmap/seoul",
            params={
                "analysis_month": analysis_month,
                "include_station_details": include_station_details,
                "min_traffic_threshold": min_traffic_threshold
            },
            execution_time=processing_time/1000  # ms를 초로 변환
        )
        
        # Pydantic 모델을 직접 반환
        return result
        
    except Exception as e:
        print(f"[HEATMAP API] Error: {e}")
        import traceback
        print(f"[HEATMAP API] Traceback: {traceback.format_exc()}")
        raise


@router.get("/districts/{district_name}")
async def get_district_heatmap(
    district_name: str,
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01, 프론트에서 -01 추가)"),
    min_traffic_threshold: Optional[int] = Query(
        None, 
        ge=0, 
        description="최소 교통량 임계값 (이하 정류장 제외)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 구의 정류장별 상세 히트맵 데이터 조회
    
    **주요 기능**:
    - 특정 구 내 정류장별 교통량 및 좌표
    - 구 경계 좌표 데이터
    - 정류장별 교통량 순위
    
    **사용 예시**:
    - `/districts/강남구?analysis_month=2025-07`
    - `/districts/마포구?analysis_month=2025-07&min_traffic_threshold=1000`
    
    **참고**: 구명은 URL 인코딩 필요 (강남구 → %EA%B0%95%EB%82%A8%EA%B5%AC)
    """
    start_time = time.time()
    
    print(f"[HEATMAP API] ===== DISTRICT REQUEST STARTED =====")
    print(f"[HEATMAP API] District: {district_name}, Month: {analysis_month}")
    
    try:
        service = HeatmapService()
        
        # 전체 서울시 데이터 조회 후 해당 구만 필터링
        result = await service.get_seoul_heatmap(
            db=db,
            analysis_month=analysis_month,
            include_station_details=True,
            min_traffic_threshold=min_traffic_threshold
        )
        
        # 해당 구 찾기
        target_district = None
        for district in result.districts:
            if district.district_name == district_name:
                target_district = district
                break
        
        if not target_district:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"District '{district_name}' not found or has no traffic data"
            )
        
        print(f"[HEATMAP API] Found district: {target_district.district_name}")
        print(f"[HEATMAP API] District stations: {len(target_district.stations)}")
        print(f"[HEATMAP API] District traffic: {target_district.total_traffic:,}")
        
        # 처리 시간
        processing_time = round((time.time() - start_time) * 1000, 2)
        print(f"[HEATMAP API] Processing time: {processing_time}ms")
        
        # 구별 상세 데이터만 반환
        return target_district
        
    except Exception as e:
        print(f"[HEATMAP API] Error: {e}")
        import traceback
        print(f"[HEATMAP API] Traceback: {traceback.format_exc()}")
        raise


@router.get("/statistics")
async def get_heatmap_statistics(
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01, 프론트에서 -01 추가)"),
    db: AsyncSession = Depends(get_db)
):
    """
    히트맵 통계 데이터만 조회 (빠른 로딩용)
    
    **주요 기능**:
    - 구별/정류장별 교통량 통계
    - 히트맵 색상 구간 계산용 사분위수
    - 전체 집계 정보
    
    **사용 예시**:
    - 히트맵 초기화시 색상 범위 설정
    - 대시보드 통계 카드 표시
    """
    start_time = time.time()
    
    try:
        service = HeatmapService()
        
        # 구별 집계만 조회 (정류장 상세 제외)
        result = await service.get_seoul_heatmap(
            db=db,
            analysis_month=analysis_month,
            include_station_details=False
        )
        
        processing_time = round((time.time() - start_time) * 1000, 2)
        
        return success_response(
            data={
                "statistics": result.statistics,
                "processing_time_ms": processing_time
            },
            message=f"Heatmap statistics for {analysis_month}"
        )
        
    except Exception as e:
        print(f"[HEATMAP API] Statistics error: {e}")
        raise


@router.get("/health")
async def health_check():
    """
    히트맵 API 상태 확인
    """
    print("[HEATMAP API] ===== HEALTH CHECK CALLED =====")
    return success_response(
        data={
            "status": "healthy",
            "service": "seoul-heatmap-component",
            "endpoints": ["/seoul", "/districts/{district_name}", "/statistics"],
            "description": "서울시 교통량 히트맵 컴포넌트 API"
        },
        message="Heatmap API is running"
    )


@router.get("/info")
async def api_info():
    """
    히트맵 API 정보
    """
    return success_response(
        data={
            "component_name": "서울시 교통량 히트맵 컴포넌트",
            "data_source": "station_passenger_history + spatial_mapping + bus_stops",
            "available_period": "2025-07 (2025년 7월 16일~31일)",
            "coverage": "서울시 25개 구, 11,000+ 정류장",
            "features": {
                "hierarchical_data": "서울시 → 구 → 정류장 계층 구조",
                "geographic_boundaries": "서울시/구별 경계 좌표",
                "traffic_statistics": "사분위수 기반 히트맵 색상 구간",
                "performance_options": "선택적 로딩, 임계값 필터링"
            },
            "response_size": {
                "statistics_only": "~1KB (빠른 로딩)",
                "district_summary": "~50KB (구별 집계)",
                "full_details": "~500KB+ (정류장별 상세)"
            }
        },
        message="Seoul Heatmap Component API Information"
    )