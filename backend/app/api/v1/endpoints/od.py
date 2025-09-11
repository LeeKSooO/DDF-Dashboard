"""
OD 데이터 기반 DRT 분석 API 엔드포인트
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.odService import ODService
from app.schemas.od import DRTPriorityMatrixResponse, TimeBasedOriginAnalysisSchema, DestinationStationSchema, TimeBasedOriginAnalysisResponse, DemandSupplyMismatchSchema, ODPairHourlyAnalysisSchema

router = APIRouter()


@router.get(
    "/priority/{priority_level}",
    summary="DRT 우선순위별 구간 분석",
    description="""
    DRT 도입 우선순위별 구간 분석 데이터를 제공합니다.
    
    === 분석 기준 ===
    - 기존 대중교통 서비스 품질 vs 승객 수요량 분석
    - 환승 필요성, 배차간격, 수요 밀도 종합 평가
    - 실제 운영 데이터 기반 우선순위 산정
    
    === 우선순위 분류 === 
    - P1 (최우선): 환승 필요 구간 - 즉시 DRT 도입 권장
    - P2 (우선): 직행노선 부족 고수요 구간 - 중장기 DRT 고려  
    - P3 (검토): 저수요 장거리 구간 - 수요응답형 서비스 적합
    
    === 활용 방안 === 
    - DRT 노선 계획 수립의 우선순위 결정
    - 예산 배정 및 단계별 도입 전략 수립
    - 기존 노선 개선 vs DRT 신규 도입 의사결정 지원
    """
)
async def get_drt_priority_segments(
    priority_level: str = Path(
        ...,
        description="우선순위 레벨 - p1: 환승 필요 구간(최우선), p2: 직행노선 부족 고수요, p3: 저수요 장거리",
        regex="^(p1|p2|p3)$"
    ),
    analysis_month: date = Query(
        ...,
        description="분석 대상 월 (YYYY-MM-DD 형식, 일자는 무시됨)",
        example="2025-07-01"
    ),
    top_n: int = Query(
        20,
        ge=1,
        le=100,
        description="상위 N개 결과 반환"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    DRT 우선순위별 구간 분석
    
    === P1 - 환승 필요 구간 (최우선, 149개) === 
    - 현재 환승이 필요한 구간으로 DRT 도입 시 승객 편의성이 크게 개선
    - 고수요(일일 100명 이상) + 저수요(일일 100명 미만) 환승구간 통합
    - 즉시 DRT 도입 권장 구간
    
    === P2 - 직행노선 부족 고수요 구간 (2,747개) === 
    - 직행 노선이 있지만 배차간격이 길거나 수요 대비 공급 부족
    - 기존 대중교통 보완용 DRT 서비스 검토 구간
    - 중장기 DRT 도입 고려 구간
    
    === P3 - 저수요 장거리 구간 (237,286개) === 
    - 수요 밀도가 낮은 장거리 이동 구간
    - 기존 고정노선 대비 효율성이 떨어지는 구간  
    - 수요응답형 서비스가 더 적합한 구간
    """
    try:
        od_service = ODService()
        
        if priority_level == "p1":
            result = await od_service.get_p1_transfer_routes(db, analysis_month, top_n)
        elif priority_level == "p2":
            result = await od_service.get_p2_high_demand_routes(db, analysis_month, top_n)
        elif priority_level == "p3":
            result = await od_service.get_p3_low_efficiency_routes(db, analysis_month, top_n)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DRT P{priority_level.upper()} 우선순위 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/time-based-origin/{time_period}",
    response_model=TimeBasedOriginAnalysisResponse,
    summary="시간대별 출발지 분석",
    description="""
    특정 시간대의 출발지별 목적지 클러스터 패턴을 분석하여 히트맵 시각화용 데이터를 제공합니다.
    
    === 히트맵 시각화 지원 === 
    - 출발지 좌표를 중심점으로 하는 히트맵 생성
    - 상위 20개 목적지 좌표를 마커로 표시 가능
    - 시간대별 수요 집중도를 색상 강도로 구분
    
    === 지원 시간대 === 
    - morning_peak: 출근시간(07-09시) - 주거→업무 집중 패턴
    - evening_peak: 퇴근시간(17-19시) - 업무→주거 분산 패턴  
    - daytime: 주간시간(10-16시) - 다목적 안정적 수요
    - night: 심야시간(23-06시) - 대중교통 공백 시간대
    
    === DRT 서비스 계획 지원 === 
    - 출발지별 목적지 분산도 분석 (집중형/분산형/광역형)
    - DRT 도입 잠재력 평가 (높음/보통/낮음)
    - 시간대별 운영 전략 권장사항 제공
    """
)
async def get_time_based_origin_analysis(
    time_period: str = Path(
        ...,
        description="분석 시간대 - morning_peak: 출근(07-09시), evening_peak: 퇴근(17-19시), daytime: 주간(10-16시), night: 심야(23-06시)",
        regex="^(morning_peak|evening_peak|night|daytime)$"
    ),
    analysis_month: date = Query(
        ...,
        description="분석 대상 월 (YYYY-MM-DD 형식, 일자는 무시됨)",
        example="2025-07-01"
    ),
    top_n: int = Query(
        20,
        ge=1,
        le=100,
        description="상위 N개 출발지 반환"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    시간대별 출발지 분석 - 히트맵 시각화용
    
    === morning_peak (출근시간, 07-09시) === 
    - 주거지역에서 업무지구로의 집중적 이동 패턴
    - 지하철역, 버스정류장 중심의 수요 집중
    - DRT 서비스로 First/Last Mile 해결 가능
    
    === evening_peak (퇴근시간, 17-19시) === 
    - 업무지구에서 주거지역으로의 분산적 이동 패턴
    - 출근시간 대비 목적지가 더 분산됨
    - 역방향 DRT 서비스 수요 분석
    
    === night (심야시간, 23-06시) === 
    - 대중교통 공백시간대의 교통 수요
    - 유흥가, 24시간 업무지역 중심 패턴
    - 심야 DRT 서비스 필요성이 높은 구간
    
    === daytime (주간시간, 10-16시) === 
    - 쇼핑, 업무, 병원 등 다목적 이동 패턴
    - 상대적으로 안정적이고 예측 가능한 수요
    - 정기적 DRT 서비스 운영에 적합
    
    === 응답 데이터 === 
    - 출발지 정보 (좌표 포함)
    - 상위 목적지 20개 (좌표 포함) 
    - 수요 집중도 및 분산도 분석
    - DRT 잠재력 및 서비스 권장사항
    """
    try:
        od_service = ODService()
        result = await od_service.get_time_based_origin_analysis(
            db=db,
            analysis_month=analysis_month,
            time_period=time_period,
            top_n=top_n
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시간대별 출발지 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/mismatch-analysis",
    response_model=List[DemandSupplyMismatchSchema],
    summary="수요-공급 미스매치 분석",
    description="""
    수요 대비 서비스 품질이 떨어지는 구간을 식별하여 DRT 도입 필요성을 분석합니다.
    
    === 핵심 분석 지표 === 
    - demand_service_ratio: 수요 대비 서비스 비율 (높을수록 미스매치 심각)
    - service_quality_score: 종합 서비스 품질 점수 (0-100점)
    - avg_dispatch_interval_min: 실제 배차간격 (환승시 환승시간 포함)
    - route_diversity_index: 노선 선택권의 다양성
    
    === 서비스 품질 가중치 === 
    - 배차간격: 60% (가장 중요 - 대기시간 직결)
    - 노선다양성: 20% (선택권 및 대안 경로)
    - 환승페널티: 20% (이용 편의성)
    
    === DRT 도입 효과 예측 === 
    - 높은 demand_service_ratio = DRT 도입 효과 큰 구간
    - 기존 고정노선이 해결하지 못하는 실제 교통 수요 식별
    - 투자 대비 효과가 명확한 우선 도입 구간 제시
    
    === 의사결정 활용 === 
    - 예산 우선순위 결정 근거 제공
    - 기존 노선 개선 vs DRT 신규 도입 판단 지원
    - 서비스 개선 효과 정량화
    """
)
async def get_demand_supply_mismatch_analysis(
    analysis_month: date = Query(
        ...,
        description="분석 대상 월 (YYYY-MM-DD 형식, 일자는 무시됨)",
        example="2025-07-01"
    ),
    min_passengers: int = Query(
        10,
        ge=1,
        le=200,
        description="분석 대상 최소 일평균 승객 수 (낮을수록 더 많은 구간 포함, 높을수록 고수요 구간만 분석)"
    ),
    top_n: int = Query(
        50,
        ge=1,
        le=200,
        description="상위 N개 미스매치 구간 반환"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    수요-공급 미스매치 분석
    
    === 분석 목적 === 
    - 수요는 있지만 서비스 품질이 부족한 구간 식별
    - DRT 도입 필요성이 높은 OD Pair 발굴
    - 기존 고정노선이 해결하지 못하는 교통 수요 분석
    
    === 분석 지표 === 
    - service_quality_score: 서비스 품질 점수 (배차간격, 노선다양성, 환승여부 종합)
    - demand_service_ratio: 수요 대비 서비스 비율 (높을수록 미스매치 심각)
    - avg_dispatch_interval_min: 평균 배차간격 (환승시 환승시간 포함)
    - route_diversity_index: 노선 선택권 다양성
    - transfer_penalty: 환승 필요 여부 (0=직행, 1=환승)
    
    === 필터링 기준 === 
    - 일평균 승객 수 >= min_passengers
    - demand_service_ratio >= 1.0 (수요가 서비스보다 높은 경우만)
    - demand_service_ratio 내림차순 정렬
    
    === 활용 방안 === 
    - DRT 노선 계획 수립
    - 기존 노선 개선 우선순위 결정
    - 투자 대비 효과 예측
    """
    try:
        od_service = ODService()
        result = await od_service.get_demand_supply_mismatch_analysis(
            db=db,
            analysis_month=analysis_month,
            min_passengers=min_passengers,
            top_n=top_n
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"수요-공급 미스매치 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/hourly-analysis",
    response_model=ODPairHourlyAnalysisSchema,
    summary="OD Pair 시간대별 상세 분석",
    description="""
    특정 OD Pair의 24시간 승객 분포와 시간대별 집중도를 분석합니다.
    
    === 제공 데이터 === 
    - hourly_passengers: 0시-23시 일평균 승객 수 (월간 누적 ÷ 실제 등장일수)
    - daily_avg_passengers: 일평균 총 승객 수 (검증용)
    - time_summary: 피크시간, 집중도, 패턴 타입 분석
    
    === 시간대별 패턴 분류 === 
    - 출근시간 집중형: 출근시간 > 20% & 출근 > 퇴근
    - 퇴근시간 집중형: 퇴근시간 > 20% & 퇴근 > 출근  
    - 주간 분산형: 주간시간 > 50%
    - 균등 분산형: 위 조건에 해당하지 않는 경우
    
    === DRT 운영 계획 활용 === 
    - 최적 운영 시간대 결정 (피크시간 집중 vs 전일 운영)
    - 차량 배치 및 운행 빈도 계획
    - 수요 예측 기반 동적 요금제 설계
    
    === 연계 분석 워크플로우 === 
    1. mismatch-analysis에서 고위험 구간 식별
    2. 해당 구간의 from_station_id, to_station_id 확인  
    3. hourly-analysis로 상세 시간대별 분석 수행
    4. 결과 기반 DRT 운영 전략 수립
    """
)
async def get_od_pair_hourly_analysis(
    analysis_month: date = Query(
        ...,
        description="분석 대상 월 (YYYY-MM-DD 형식, 일자는 무시됨)",
        example="2025-07-01"
    ),
    from_station_id: str = Query(
        ...,
        description="출발 정류장 ID (mismatch-analysis 결과에서 확인 가능)",
        example="105900027"
    ),
    to_station_id: str = Query(
        ...,
        description="도착 정류장 ID (mismatch-analysis 결과에서 확인 가능)", 
        example="105900050"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    OD Pair 시간대별 상세 분석
    
    === 기능 === 
    - 특정 OD Pair의 24시간 승객 분포 제공
    - 피크시간, 집중도, 패턴 타입 분석
    - DRT 운영 시간대 계획 수립 지원
    
    === 사용법 === 
    1. mismatch-analysis에서 from_station_id, to_station_id 확인
    2. 해당 ID로 상세 시간대별 분석 요청
    3. 결과를 통해 DRT 운영 계획 수립
    
    === 분석 항목 === 
    - hourly_passengers: 0시-23시 승객 수
    - time_summary: 피크시간, 집중도, 패턴 타입
    - pattern_type: 출근시간/퇴근시간/주간분산/균등분산형
    
    === 패턴 타입 기준 === 
    - 출근시간 집중형: 출근시간 > 20% & 출근 > 퇴근
    - 퇴근시간 집중형: 퇴근시간 > 20% & 퇴근 > 출근  
    - 주간 분산형: 주간시간 > 50%
    - 균등 분산형: 위 조건에 해당하지 않는 경우
    """
    try:
        od_service = ODService()
        result = await od_service.get_od_pair_hourly_analysis(
            db=db,
            analysis_month=analysis_month,
            from_station_id=from_station_id,
            to_station_id=to_station_id
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시간대별 분석 중 오류가 발생했습니다: {str(e)}"
        )