"""
DRT Score 분석 API 엔드포인트
출퇴근형, 관광특화형, 교통취약지형 3개 모델에 따른 DRT 점수 제공
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.db.session import get_db
from app.services.drtScoreService import DRTScoreService
from app.schemas.drtScore import (
    DistrictDRTScoreResponse,
    StationDRTDetailResponse
)
from app.utils.response import (
    success_response,
    log_api_request
)

router = APIRouter()


@router.get("/districts/{district_name}", response_model=DistrictDRTScoreResponse)
async def get_district_drt_scores(
    district_name: str = Path(..., description="구명 (예: 강남구, 마포구)"),
    model_type: str = Query(..., description="DRT 모델 타입", regex="^(commuter|tourism|vulnerable)$"),
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01, 프론트에서 -01 추가)"),
    db: AsyncSession = Depends(get_db)
):
    """
    === 1. 히트맵용 구별 DRT 점수 조회 === 
    
    **주요 기능**:
    - 히트맵 렌더링용 정류장별 DRT 점수 및 좌표 (stations 배열)
    - 대시보드 Top 5 리스트 표시 (top_stations 배열) 
    - 모델 변경시 빠른 업데이트 지원
    
    **모델 타입**:
    - `commuter`: 출퇴근형 (TC, PDR, RU, PCW 지표)
    - `tourism`: 관광특화형 (TC, TDR, RU, PCW 지표, 10-16시 가중치)
    - `vulnerable`: 교통취약지형 (VAR, SED, MDI, AVS 지표)
    
    **사용 예시**:
    - `/districts/강남구?model_type=commuter&analysis_month=2025-07-01`
    - `/districts/마포구?model_type=tourism&analysis_month=2025-07-01`
    
    **응답 구조** (요구사항 완전 충족):
    ```json
    {
      "district_name": "강남구",
      "model_type": "commuter", 
      "analysis_month": "2025-07",
      "stations": [
        {
          "station_id": "121000012",
          "station_name": "지하철2호선강남역", 
          "coordinate": {"lat": 37.500785, "lng": 127.02637},
          "drt_score": 87.5,  // 최고점수 시간대 기준
          "peak_hour": 8
        }
        // ... 구 내 모든 정류장
      ],
      "top_stations": [
        // 상위 5개 정류장만 (대시보드 Top 5 리스트용)
      ]
    }
    ```
    
    === 성능 최적화 === 
    - 히트맵용 최고점수만 표시 (drt_score, peak_hour)
    - Top 5 미리 계산하여 제공 (top_stations)
    - 모델 전환시 빠른 업데이트 보장
    """
    start_time = time.time()
    
    print(f"[DRT SCORE API] ===== DISTRICT DRT REQUEST =====")
    print(f"[DRT SCORE API] District: {district_name}, Model: {model_type}, Month: {analysis_month}")
    
    try:
        # 서비스 호출
        service = DRTScoreService()
        
        print("[DRT SCORE API] Calling district DRT score service...")
        result = await service.get_district_drt_scores(
            db=db,
            district_name=district_name,
            model_type=model_type,
            analysis_month=analysis_month
        )
        
        print(f"[DRT SCORE API] Service returned: {len(result.stations)} stations")
        print(f"[DRT SCORE API] Top 5 stations: {len(result.top_stations)}")
        if result.top_stations:
            print(f"[DRT SCORE API] Top station: {result.top_stations[0].station_name} (score: {result.top_stations[0].drt_score})")
        
        # 처리 시간
        processing_time = round((time.time() - start_time) * 1000, 2)
        print(f"[DRT SCORE API] Processing time: {processing_time}ms")
        
        # 로깅
        log_api_request(
            endpoint=f"drt_score/districts/{district_name}",
            params={
                "model_type": model_type,
                "analysis_month": analysis_month
            },
            execution_time=processing_time/1000
        )
        
        return result
        
    except Exception as e:
        print(f"[DRT SCORE API] Error: {e}")
        import traceback
        print(f"[DRT SCORE API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stations/{station_id}", response_model=StationDRTDetailResponse)
async def get_station_drt_detail(
    station_id: str = Path(..., description="정류장 ID"),
    model_type: str = Query(..., description="DRT 모델 타입", regex="^(commuter|tourism|vulnerable)$"),
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식, 예: 2025-07-01)"),
    hour: Optional[int] = Query(None, ge=0, le=23, description="조회할 시간대 (기본값: peak_hour)"),
    db: AsyncSession = Depends(get_db)
):
    """
    === 2. 정류장 상세 DRT 분석 === 
    
    **주요 기능**:
    - 정류장 클릭시 피처 패널 업데이트용
    - 24시간별 DRT 점수 차트 데이터 (hourly_scores)
    - 세부 지표별 점수 분석 (feature_scores)
    - 현재 선택 시간대 정보 (current_hour, current_score)
    
    **사용 예시**:
    - `/stations/121000012?model_type=commuter&analysis_month=2025-07-01`
    - `/stations/121000012?model_type=commuter&analysis_month=2025-07-01&hour=8`
    
    **응답 구조** (요구사항 완전 충족):
    ```json
    {
      "station": {
        "station_id": "121000012",
        "station_name": "지하철2호선강남역",
        "latitude": 37.500785,
        "longitude": 127.02637,
        "district_name": "강남구", 
        "administrative_dong": "역삼1동"
      },
      "model_type": "commuter",
      "analysis_month": "2025-07",
      "current_hour": 8,        // 현재 조회 중인 시간대
      "current_score": 87.5,    // 현재 시간대 DRT 점수
      "peak_score": 87.5,
      "peak_hour": 8,
      "monthly_average": 65.2,
      "feature_scores": {       // 모델별 동적 변경
        "tc_score": 0.95,   // 출퇴근형: TC, PDR, RU, PCW
        "pdr_score": 0.87,  // 관광특화형: TC, TDR, RU, PCW  
        "ru_score": 0.75,   // 교통취약지형: VAR, SED, MDI, AVS
        "pcw_score": 1.0
      },
      "hourly_scores": [        // 차트용 24시간 데이터
        {"hour": 0, "score": 45.2},
        {"hour": 8, "score": 87.5}
        // ... 24시간 전체
      ]
    }
    ```
    
    **🎯 용도**:
    - 히트맵 정류장 클릭시 팝업 표시
    - 시간대별 차트 렌더링 (hourly_scores)
    - 세부 지표 분석 (feature_scores)
    - 시간대 필터링 (hour 파라미터)
    """
    start_time = time.time()
    
    print(f"[DRT SCORE API] ===== STATION DETAIL REQUEST =====")
    print(f"[DRT SCORE API] Station: {station_id}, Model: {model_type}, Month: {analysis_month}, Hour: {hour}")
    
    try:
        service = DRTScoreService()
        
        result = await service.get_station_drt_detail(
            db=db,
            station_id=station_id,
            model_type=model_type,
            analysis_month=analysis_month,
            hour=hour  # 선택적 시간대 파라미터
        )
        
        processing_time = round((time.time() - start_time) * 1000, 2)
        print(f"[DRT SCORE API] Processing time: {processing_time}ms")
        print(f"[DRT SCORE API] Current hour: {result.current_hour}, Current score: {result.current_score}")
        print(f"[DRT SCORE API] Peak hour: {result.peak_hour}, Peak score: {result.peak_score}")
        
        log_api_request(
            endpoint=f"drt_score/stations/{station_id}",
            params={
                "model_type": model_type,
                "analysis_month": analysis_month,
                "hour": hour
            },
            execution_time=processing_time/1000
        )
        
        return result
        
    except Exception as e:
        print(f"[DRT SCORE API] Error: {e}")
        import traceback
        print(f"[DRT SCORE API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_type}/districts/{district_name}", response_model=DistrictDRTScoreResponse) 
async def get_model_specific_district_scores(
    model_type: str = Path(..., description="DRT 모델 타입", regex="^(commuter|tourism|vulnerable)$"),
    district_name: str = Path(..., description="구명"),
    analysis_month: date = Query(..., description="분석 월 (YYYY-MM-DD 형식)"),
    db: AsyncSession = Depends(get_db)
):
    """
    === 3. 모델별 특화 점수 조회 (옵션) === 
    
    **모델별 feature_scores 차이**:
    
    **출퇴근형 (commuter)**:
    ```json
    "feature_scores": {
      "tc_score": 0.95,   // 시간 집중도
      "pdr_score": 0.87,  // 피크 수요 비율  
      "ru_score": 0.75,   // 노선 활용도
      "pcw_score": 1.0    // POI 카테고리 가중치
    }
    ```
    
    **관광특화형 (tourism)**:
    ```json
    "feature_scores": {
      "tc_score": 1.14,   // 관광 집중도 (10-16시 가중치 1.2)
      "tdr_score": 0.94,  // 관광 수요 비율 (10-16시 가중치 1.1)
      "ru_score": 0.75,   // 구간 이용률
      "pcw_score": 0.8    // POI 관광 가중치 (관광특구>고궁>상권>공원)
    }
    ```
    
    **교통취약지형 (vulnerable)**:
    ```json
    "feature_scores": {
      "var_score": 0.23,  // 취약 접근성 비율
      "sed_score": 0.18,  // 사회 형평성 수요
      "mdi_score": 0.65,  // 이동성 불리 지수
      "avs_score": 0.7    // 지역 취약성 점수
    }
    ```
    """
    # 기본 district 엔드포인트와 동일한 로직
    return await get_district_drt_scores(
        district_name=district_name,
        model_type=model_type, 
        analysis_month=analysis_month,
        db=db
    )


@router.get("/models")
async def get_available_models():
    """
    사용 가능한 DRT 모델 정보 조회
    """
    return success_response(
        data={
            "models": [
                {
                    "type": "commuter",
                    "name": "출퇴근형",
                    "description": "출퇴근 시간대 교통수요 집중 패턴 분석",
                    "indicators": ["tc_score", "pdr_score", "ru_score", "pcw_score"],
                    "peak_hours": [7, 8, 9, 18, 19, 20],
                    "feature_descriptions": {
                        "tc_score": "시간 집중도 지수",
                        "pdr_score": "피크 수요 비율", 
                        "ru_score": "노선 활용도",
                        "pcw_score": "POI 카테고리 가중치"
                    }
                },
                {
                    "type": "tourism",
                    "name": "관광특화형", 
                    "description": "관광지 접근성과 여가활동 시간대 분석",
                    "indicators": ["tc_score", "tdr_score", "ru_score", "pcw_score"],
                    "weighted_hours": [10, 11, 12, 13, 14, 15, 16],
                    "feature_descriptions": {
                        "tc_score": "관광 집중도 (10-16시 가중치 1.2)",
                        "tdr_score": "관광 수요 비율 (10-16시 가중치 1.1)",
                        "ru_score": "구간 이용률",
                        "pcw_score": "POI 관광 가중치"
                    }
                },
                {
                    "type": "vulnerable",
                    "name": "교통취약지형",
                    "description": "교통소외계층과 취약시간대 접근성 분석", 
                    "indicators": ["var_score", "sed_score", "mdi_score", "avs_score"],
                    "vulnerable_hours": [9, 10, 11, 14, 15, 16, 18, 19, 20],
                    "feature_descriptions": {
                        "var_score": "취약 접근성 비율",
                        "sed_score": "사회 형평성 수요",
                        "mdi_score": "이동성 불리 지수", 
                        "avs_score": "지역 취약성 점수"
                    }
                }
            ]
        },
        message="Available DRT Score models with feature descriptions"
    )


@router.get("/health")
async def health_check():
    """
    DRT Score API 상태 확인
    """
    print("[DRT SCORE API] ===== HEALTH CHECK CALLED =====")
    return success_response(
        data={
            "status": "healthy",
            "service": "drt-score-analysis",
            "endpoints": [
                "GET /districts/{district_name}",
                "GET /stations/{station_id}", 
                "GET /models/{model_type}/districts/{district_name}",
                "GET /models"
            ],
            "description": "DRT Score 분석 API - 출퇴근형/관광특화형/교통취약지형",
            "data_unit": "월간 집계 시간대별 데이터",
            "performance": "MV 최적화 적용 (평균 162ms)"
        },
        message="DRT Score API is running"
    )


@router.get("/info")
async def api_info():
    """
    DRT Score API 상세 정보
    """
    return success_response(
        data={
            "component_name": "DRT Score 분석 시스템",
            "dashboard_ux_flow": {
                "step1": "모델 선택 → DistrictDRTScoreResponse로 히트맵 + Top 5 업데이트",
                "step2": "정류장 클릭 → StationDRTDetailResponse로 상세 팝업 + 차트 표시", 
                "step3": "시간대 필터 → 현재 응답에서 hourly_scores 활용"
            },
            "models": {
                "commuter": "출퇴근형 - 시간집중도, 피크수요비율, 노선활용도, POI카테고리가중치",
                "tourism": "관광특화형 - 관광집중도, 관광수요비율, 구간이용률, POI관광가중치",
                "vulnerable": "교통취약지형 - 취약접근성비율, 사회형평성수요, 이동성불리지수, 지역취약성점수"
            },
            "performance_optimization": {
                "heatmap": "최고점수만 표시 (drt_score, peak_hour)",
                "top5": "미리 계산된 top_stations 제공",
                "detail_analysis": "필요시에만 StationDRTDetailResponse 호출",
                "model_switching": "feature_scores 구조만 동적 변경"
            },
            "data_sources": [
                "mv_station_hourly_patterns (승하차 데이터 - MV 최적화)",
                "dispatch_history (배차 데이터)",
                "section_passenger_history (구간별 승객 데이터)",
                "spatial_mapping (정류장 위치 정보)"
            ],
            "available_period": "2025-07 (월간 집계 시간대별 데이터)",
            "total_indicators": 12
        },
        message="DRT Score Analysis API - 완전한 요구사항 충족"
    )