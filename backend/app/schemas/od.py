"""
OD 데이터 기반 DRT 도입 우선순위 분석 API 응답 스키마
웹 대시보드에서 구별 DRT 도입 타당성 및 우선순위 정보 제공
"""

from typing import List, Dict
from pydantic import BaseModel, Field


# ==========================================
# 1. 기본 구성 요소 스키마
# ==========================================

class ODPairInfoSchema(BaseModel):
    """OD 구간 기본 정보"""
    from_station_id: str = Field(..., description="출발 정류장 ID")
    from_station_name: str = Field(..., description="출발 정류장명")
    from_station_num: str = Field(..., description="출발 정류장 번호")
    from_coordinates: dict = Field(None, description="출발 정류장 좌표", example={"x": 127.0276, "y": 37.4979})
    to_station_id: str = Field(..., description="도착 정류장 ID")
    to_station_name: str = Field(..., description="도착 정류장명")
    to_station_num: str = Field(..., description="도착 정류장 번호")
    to_coordinates: dict = Field(None, description="도착 정류장 좌표", example={"x": 127.0345, "y": 37.4844})
    from_district: str = Field(..., description="출발 구명")
    to_district: str = Field(..., description="도착 구명")
    distance_km: float = Field(..., description="예상 이동 거리 (km)")
    
    class Config:
        schema_extra = {
            "example": {
                "from_station_id": "113000422",
                "from_station_name": "홍대입구역",
                "from_station_num": "01234",
                "to_station_id": "114000567",
                "to_station_name": "강남역",
                "to_station_num": "05678",
                "from_district": "마포구",
                "to_district": "강남구",
                "distance_km": 12.5
            }
        }


class DRTPriorityBreakdownSchema(BaseModel):
    """DRT 우선순위 점수 상세 분해"""
    p1_high_transfer: Dict = Field(
        ..., 
        description="P1: 고수요 환승구간 (가중치 10)"
    )
    p2_low_transfer: Dict = Field(
        ..., 
        description="P2: 저수요 환승구간 (가중치 5)"
    )
    p3_capacity_issue: Dict = Field(
        ..., 
        description="P3: 직행노선 부족 고수요 (가중치 3)"
    )
    p4_efficiency: Dict = Field(
        ..., 
        description="P4: 저수요 장거리 (가중치 1)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "p1_high_transfer": {
                    "count": 13,
                    "weight": 10,
                    "score": 130,
                    "monthly_demand": 1663
                },
                "p2_low_transfer": {
                    "count": 130,
                    "weight": 5,
                    "score": 650,
                    "monthly_demand": 4301
                },
                "p3_capacity_issue": {
                    "count": 628,
                    "weight": 3,
                    "score": 1884,
                    "monthly_demand": 106982
                },
                "p4_efficiency": {
                    "count": 98666,
                    "weight": 1,
                    "score": 98666,
                    "monthly_demand": 459394
                }
            }
        }


# ==========================================
# 2. DRT 우선순위별 상세 스키마
# ==========================================

class HighPriorityTransferSchema(BaseModel):
    """고우선순위 환승 구간 (P1, P2)"""
    od_pair: ODPairInfoSchema
    daily_demand: int = Field(..., description="일일 수요량")
    transfer_required: bool = Field(..., description="환승 필요 여부")
    priority_category: str = Field(..., description="우선순위 카테고리")
    
    class Config:
        schema_extra = {
            "example": {
                "od_pair": {},
                "daily_demand": 233,
                "transfer_required": True,
                "priority_category": "P1_최우선"
            }
        }


class HighDemandDirectRouteSchema(BaseModel):
    """직행노선 부족 고수요 구간 (P3)"""
    od_pair: ODPairInfoSchema
    daily_demand: int = Field(..., description="일일 수요량")
    transfer_required: bool = Field(..., description="환승 필요 여부")
    avg_dispatch_interval: float = Field(None, description="현재 평균 배차간격(분)")
    priority_category: str = Field(..., description="우선순위 카테고리")
    
    class Config:
        schema_extra = {
            "example": {
                "od_pair": {},
                "daily_demand": 150,
                "transfer_required": False,
                "avg_dispatch_interval": 25.5,
                "priority_category": "P3_고려대상"
            }
        }


class LowDemandLongDistanceSchema(BaseModel):
    """저수요 장거리 구간 (P4)"""
    od_pair: ODPairInfoSchema
    daily_demand: int = Field(..., description="일일 수요량")
    demand_per_km: float = Field(..., description="거리당 수요량 (명/km)")
    service_recommendation: str = Field(..., description="서비스 권장사항")
    
    class Config:
        schema_extra = {
            "example": {
                "od_pair": {},
                "daily_demand": 5,
                "demand_per_km": 0.6,
                "service_recommendation": "DRT 전환 권장"
            }
        }


# ==========================================
# 3. 시간대별 분석 스키마
# ==========================================

class TimeBasedDemandSchema(BaseModel):
    """시간대별 DRT 수요 분석"""
    time_period: str = Field(..., description="시간대 구분")
    transfer_demand: int = Field(..., description="환승 수요량")
    percentage: float = Field(..., description="전체 대비 비율 (%)")
    drt_suitability: str = Field(..., description="DRT 적합성")
    
    class Config:
        schema_extra = {
            "example": {
                "time_period": "비피크시간 (10-16)",
                "transfer_demand": 77089,
                "percentage": 39.1,
                "drt_suitability": "DRT 최적 운영시간"
            }
        }


# ==========================================
# 4. 통합 분석 응답 스키마
# ==========================================

class DRTPriorityMatrixResponse(BaseModel):
    """DRT 도입 우선순위 매트릭스 응답"""
    
    # 메타 정보
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)")
    generated_at: str = Field(..., description="생성 시간 (ISO 8601)")
    
    # 전체 요약 지표
    total_od_pairs: int = Field(..., description="전체 OD 구간 수")
    drt_applicable_pairs: int = Field(..., description="DRT 적용 가능 구간 수")
    monthly_transfer_demand: int = Field(..., description="월간 환승 수요")
    
    # 우선순위별 분석
    priority_distribution: Dict = Field(
        ..., 
        description="우선순위별 분포"
    )
    
    
    # 주요 환승 구간
    high_priority_transfers: List[HighPriorityTransferSchema] = Field(
        ..., 
        description="고우선순위 환승 구간 (P1, P2)"
    )
    
    # 직행노선 부족 고수요 구간
    high_demand_direct_routes: List[HighDemandDirectRouteSchema] = Field(
        ..., 
        description="직행노선 부족 고수요 구간 (P3)"
    )
    
    # 저효율 구간
    low_efficiency_routes: List[LowDemandLongDistanceSchema] = Field(
        ..., 
        description="저효율 장거리 구간 (P4)"
    )
    
    # 시간대별 분석
    time_based_analysis: List[TimeBasedDemandSchema] = Field(
        ..., 
        description="시간대별 수요 분석"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "generated_at": "2025-08-31T10:30:00Z",
                "total_od_pairs": 2958009,
                "drt_applicable_pairs": 1536211,
                "monthly_transfer_demand": 197280,
                "priority_distribution": {
                    "p1_최우선": 39,
                    "p2_우선": 1662,
                    "p3_고려": 9152,
                    "p4_적합": 1525358
                },
                "high_priority_transfers": [],
                "high_demand_direct_routes": [],
                "low_efficiency_routes": [],
                "time_based_analysis": []
            }
        }


class ODHeatmapDataSchema(BaseModel):
    """OD 히트맵 데이터 (대시보드용)"""
    origin_district: str = Field(..., description="출발 구")
    destination_district: str = Field(..., description="도착 구")
    total_demand: int = Field(..., description="총 수요량")
    transfer_pairs: int = Field(..., description="환승 필요 구간 수")
    avg_distance: float = Field(..., description="평균 거리")
    drt_recommendation: str = Field(..., description="DRT 권장사항")
    
    class Config:
        schema_extra = {
            "example": {
                "origin_district": "강북구",
                "destination_district": "성북구",
                "total_demand": 351314,
                "transfer_pairs": 851,
                "avg_distance": 3.0,
                "drt_recommendation": "DRT 필요"
            }
        }



# ==========================================
# 5. DRT 의사결정 지표 스키마 (연구원 피드백 반영)
# ==========================================
    
    # == 서비스 품질 평가 지표 LOG ==
    # 1. 배차간격이 길수록 품질이 떨어짐
    # 2. OD Pair 총 교통량 / OD Pair 등장 횟수 = 일평균 총승객량?
    # 3. 빈도수가 잦을수록 고정노선이 잘 구축되어있을 것
    # 4. ....

    ## 환승 구간 분석 결과 ##
    # 전체 OD 구간 61만 구간 중 2415개 구간에서 환승 필요(19만7천)
    
    ## 직행 연결 패턴 ##
    # 직행 없음 (0개) : 2415개 구간(환승이 필요한 구간)
    # 직행 1개 : 419,055개 구간 (68.6%) <- 대부분의 구간
    # 직행 2개 이상 : 188,067개 구간 (30.8%) <- 다양한 선택지

    ## DRT 관점에서 시사점 ##
    #   1. 환승 필요 구간은 매우 적음 (0.4%)
    #    - 서울의 고정노선 체계가 매우 잘 구축됨
    #    - 대부분 구간에서 직행 연결 존재
    #   2. 환승 구간 평균 수요: 81.7명/월
    #    - 일평균 약 2.7명으로 소규모 수요
    #    - DRT 도입에 적정한 수요 규모
    #   3. 직행 연결이 많을수록 수요 증가
    #    - 직행 10개 이상: 평균 800명+ 수요
    #    - 선택지가 많은 구간일수록 인기 높음


class DemandSupplyMismatchSchema(BaseModel):
    """수요-공급 미스매치 분석 - 수요 대비 서비스 품질이 떨어지는 구간"""
    
    # 기본 정보
    od_pair: ODPairInfoSchema
    monthly_total_passengers: int = Field(..., description="월간 총 승객 수")
    daily_avg_passengers: float = Field(..., description="일평균 승객 수")
    distance_km: float = Field(..., description="이동거리(km)")
    
    # 서비스 품질 지표 (핵심 - 기존 대중교통 서비스 수준)
    # OD Pair의 노선에서 기존 고정노선이 얼마나 잘 서비스하는지
    service_quality_score: float = Field(..., description="서비스 품질 점수 (0-100)")
    
    # OD Pair가 여러 노선을 가질텐데, common_routes JSONB에서 각 노선의 dispatch_interval 추출.
    # 조화평균으로 계산 (실제 대기시간)
    avg_dispatch_interval_min: float = Field(..., description="평균 배차간격(분) - common_routes 기반")
    
    # common_routes의 노선 타입별 가중합
    route_diversity_index: float = Field(..., description="노선 다양성 지수 (선택지 개수)")
    
    # 환승 여부
    transfer_penalty: float = Field(..., description="환승 페널티 (0=직행, 1=1회환승, 2=2회이상)")
    
    
    # 수요-서비스 미스매치 분석
    # 수요는 있는데 서비스는 부족한 곳, 수요는 OD Pair의 승객수와 빈도수로 확인해볼 수 있음. 
    # 각각 필드들 어떻게 계산할 건지 미리 파악하기

    # 수요 대비 서비스 비율 : 값이 클수록 수요는 많은데 서비스 품질이 낮음을 의미 - drt 고려 필요
    demand_service_ratio: float = Field(..., description="수요 대비 서비스 비율")
    
    # TODO: 중복성 검토 후 결정
    # underserved_score: float = Field(..., description="서비스 부족 점수 (높을수록 DRT 필요)")
    # service_gap_type: str = Field(..., description="서비스 공백 유형 (환승필요/배차부족/노선부재)")


    
    class Config:
        schema_extra = {
            "example": {
                "od_pair": {},
                "monthly_total_passengers": 1250,
                "daily_avg_passengers": 41.7,
                "distance_km": 8.3,
                "service_quality_score": 35.5,
                "avg_dispatch_interval_min": 25.5,
                "route_diversity_index": 2.3,
                "transfer_penalty": 1.0,
                "demand_service_ratio": 3.2
                # "underserved_score": 72.5,
                # "service_gap_type": "환승필요"
            }
        }



# ==========================================
# 6. 시간대별로 출발지-도착지 클러스터 패턴 분석
# ==========================================

class DestinationStationSchema(BaseModel):
    """목적지 정류장 상세 정보"""
    station_id: str = Field(..., description="정류장 ID")
    station_name: str = Field(..., description="정류장명")
    station_num: str = Field(..., description="정류장 번호")
    district_name: str = Field(..., description="소속 구명")
    coordinates: dict = Field(
        ..., 
        description="좌표 정보",
        example={"x": 127.0276, "y": 37.4979}
    )
    demand: int = Field(..., description="해당 목적지로의 수요량")
    rank: int = Field(..., description="해당 출발지에서의 목적지 순위")

class TimeBasedOriginAnalysisSchema(BaseModel):
    """
    시간대별 출발지 분석 - 목적지 클러스터 순위별 출발지 정보
    
    목적지 클러스터가 큰 출발지 순으로 정렬되어 
    히트맵에서 클릭 시 목적지 좌표들을 표시할 수 있도록 구성
    """
    
    # 출발지 정보
    from_station: dict = Field(
        ..., 
        description="출발 정류장 상세 정보 (히트맵 중심점)",
        example={
            "station_id": "102000081",
            "station_name": "서울역버스환승센터", 
            "station_num": "02161",
            "district_name": "중구",
            "coordinates": {"x": 126.9726, "y": 37.5547}
        }
    )
    
    # 목적지 클러스터 정보
    destination_count: int = Field(..., description="해당 시간대 목적지 개수")
    time_period_demand: int = Field(..., description="해당 시간대 총 수요량")
    avg_distance_km: float = Field(..., description="평균 이동 거리")
    
    # 목적지 정류장 목록 (상위 20개)
    to_stations: List[DestinationStationSchema] = Field(
        ...,
        description="상위 목적지 정류장 목록 (상위 20개, 히트맵 마커용)",
        max_items=20
    )
    
    # DRT 분석 정보
    drt_potential: str = Field(
        ...,
        description="DRT 도입 잠재력",
        example="높음"  # 높음, 보통, 낮음
    )
    service_recommendation: str = Field(
        ...,
        description="서비스 권장사항",
        example="시간대 집중 운영"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "from_station": {
                    "station_id": "121000213",
                    "station_name": "양재역",
                    "station_num": "22289",
                    "district_name": "서초구",
                    "coordinates": {"x": 127.0345, "y": 37.4844}
                },
                "destination_count": 80,
                "time_period_demand": 33526,
                "avg_distance_km": 2.87,
                "to_stations": [
                    {
                        "station_id": "122000008",
                        "station_name": "강남역",
                        "station_num": "23271",
                        "district_name": "강남구",
                        "coordinates": {"x": 127.0276, "y": 37.4979},
                        "demand": 4520,
                        "rank": 1
                    },
                    {
                        "station_id": "121000158",
                        "station_name": "교대역",
                        "station_num": "22156",
                        "district_name": "서초구",
                        "coordinates": {"x": 127.0142, "y": 37.4936},
                        "demand": 3240,
                        "rank": 2
                    }
                ],
                "drt_potential": "보통",
                "service_recommendation": "기존 노선 보완"
            }
        }


class TimeBasedOriginAnalysisResponse(BaseModel):
    """시간대별 출발지 분석 응답 (메타데이터 포함)"""
    
    # 시간대 메타데이터
    time_period: str = Field(..., description="분석 시간대", example="morning_peak")
    time_period_name: str = Field(..., description="시간대 한글명", example="출근시간(07-09시)")
    analysis_month: str = Field(..., description="분석 대상 월", example="2025-07")
    
    # 전체 요약 정보
    total_origins: int = Field(..., description="총 출발지 개수")
    total_demand: int = Field(..., description="해당 시간대 총 수요량")
    avg_destinations_per_origin: float = Field(..., description="출발지당 평균 목적지 개수")
    
    # 출발지별 상세 분석 결과
    origins: List[TimeBasedOriginAnalysisSchema] = Field(
        ...,
        description="출발지별 분석 결과 (목적지 클러스터 순위별 정렬)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "time_period": "morning_peak",
                "time_period_name": "출근시간(07-09시)",
                "analysis_month": "2025-07",
                "total_origins": 20,
                "total_demand": 567890,
                "avg_destinations_per_origin": 15.5,
                "origins": []
            }
        }


# class TimeBasedDRTOperationSchema(BaseModel):
#     """시간대별 DRT 운영 최적화 분석"""
#     district_name: str = Field(..., description="분석 대상 구명")
#     
#     # 시간대별 집중도 분석
#     morning_intensive_rate: float = Field(..., description="출근시간 수요집중 구간 비율")
#     evening_intensive_rate: float = Field(..., description="퇴근시간 수요집중 구간 비율") 
#     night_service_need_rate: float = Field(..., description="심야 서비스 필요 구간 비율")
#     daytime_service_need_rate: float = Field(..., description="주간 서비스 필요 구간 비율")
#     
#     # 운영시간 권장사항
#     recommended_operation_hours: dict = Field(..., description="권장 운영시간")
#     od_pair_count: int = Field(..., description="해당 구의 총 OD 구간 수")
#     total_monthly_demand: int = Field(..., description="해당 구의 총 월간 수요")
#     
#     # 운영 효율성 지표
#     time_flexibility_score: float = Field(..., description="시간대별 유연성 점수 (0-100)")
#     resource_optimization_potential: float = Field(..., description="자원 최적화 가능성(%)")
#     
#     class Config:
#         schema_extra = {
#             "example": {
#                 "district_name": "영등포구",
#                 "morning_intensive_rate": 0.42,
#                 "evening_intensive_rate": 0.38,
#                 "night_service_need_rate": 0.15,
#                 "daytime_service_need_rate": 0.28,
#                 "recommended_operation_hours": {
#                     "weekday_start": "05:30",
#                     "weekday_end": "23:30",
#                     "weekend_start": "07:00", 
#                     "weekend_end": "22:00"
#                 },
#                 "od_pair_count": 2847,
#                 "total_monthly_demand": 45230,
#                 "time_flexibility_score": 82.5,
#                 "resource_optimization_potential": 15.8
#             }
#         }



class TransportModeSubstitutionSchema(BaseModel):
    """기존 교통수단 대체 잠재력 분석"""
    corridor_name: str = Field(..., description="교통 축 명칭", example="영등포구 → 서초구")
    od_pair: ODPairInfoSchema
    
    # 현재 교통 패턴
    monthly_total_passengers: int = Field(..., description="현재 대중교통 월간 이용객")
    avg_distance_km: float = Field(..., description="평균 이동거리")
    current_transfer_required: bool = Field(..., description="현재 환승 필요 여부")
    weekend_weekday_ratio: float = Field(..., description="주말/평일 수요 비율")
    
    # 대체 가능성 분석
    substitution_potential: str = Field(..., description="대체 가능성 수준")
    target_transport_modes: List[str] = Field(..., description="대체 대상 교통수단")
    potential_ridership_increase: int = Field(..., description="DRT 도입시 추가 승객 예상수")
    
    # 경제성 분석
    estimated_modal_shift_rate: float = Field(..., description="교통수단 전환율 예상(%)")
    carbon_reduction_potential: float = Field(..., description="탄소 저감 잠재력(kg CO2/월)")
    service_accessibility_improvement: float = Field(..., description="접근성 개선도(%)")
    
    class Config:
        schema_extra = {
            "example": {
                "corridor_name": "영등포구 → 서초구",
                "od_pair": {},
                "monthly_total_passengers": 1580,
                "avg_distance_km": 12.4,
                "current_transfer_required": True,
                "weekend_weekday_ratio": 0.6,
                "substitution_potential": "높음 - 승용차 대체 가능",
                "target_transport_modes": ["승용차", "택시"],
                "potential_ridership_increase": 420,
                "estimated_modal_shift_rate": 18.5,
                "carbon_reduction_potential": 2840.7,
                "service_accessibility_improvement": 32.1
            }
        }


class DRTROIAnalysisSchema(BaseModel):
    """DRT 노선 ROI 예측 분석 - 연구원 피드백 핵심"""
    demand_segment: str = Field(..., description="수요 구간 분류")
    od_count: int = Field(..., description="해당 구간의 OD 쌍 개수")
    avg_monthly_demand: float = Field(..., description="구간별 평균 월간 수요")
    avg_service_interval: float = Field(..., description="평균 배차간격(분)")
    transfer_rate: float = Field(..., description="환승 필요 구간 비율")
    avg_drt_score: float = Field(..., description="평균 DRT 우선순위 점수")
    
    # ROI 예측 지표
    investment_priority: str = Field(..., description="투자 우선순위", example="최우선")
    expected_roi_percentage: float = Field(..., description="예상 ROI(%)")
    break_even_timeframe: str = Field(..., description="손익분기점 예상 기간")
    
    # 운영 전략 권장사항
    recommended_service_type: str = Field(..., description="권장 서비스 유형")
    fleet_size_recommendation: int = Field(..., description="권장 차량 규모")
    pricing_strategy: str = Field(..., description="요금 전략 권장사항")
    
    class Config:
        schema_extra = {
            "example": {
                "demand_segment": "Top10K-DRT핵심타겟",
                "od_count": 8547,
                "avg_monthly_demand": 892.3,
                "avg_service_interval": 18.7,
                "transfer_rate": 0.68,
                "avg_drt_score": 4.2,
                "investment_priority": "최우선",
                "expected_roi_percentage": 12.8,
                "break_even_timeframe": "18개월",
                "recommended_service_type": "고정노선 + 주문형",
                "fleet_size_recommendation": 25,
                "pricing_strategy": "기존 대중교통 대비 10% 할증"
            }
        }


# ==========================================
# 6. 통합 DRT 의사결정 대시보드 응답 스키마
# ==========================================

class DRTDecisionDashboardResponse(BaseModel):
    """
    DRT 의사결정 지원 통합 대시보드 응답
    
    기존 서비스 공백 지역 식별과 실용적인 DRT 도입 전략 제공
    """
    
    # 메타 정보
    analysis_month: str = Field(..., description="분석 기준월")
    generated_at: str = Field(..., description="분석 생성시간")
    
    # ========== 핵심 의사결정 지표 ==========
    
    # 1. 수요-공급 미스매치 분석
    demand_supply_mismatches: List[DemandSupplyMismatchSchema] = Field(
        ..., description="수요-공급 미스매치 구간 (DRT 효과 큰 구간)"
    )
    
    # 2. 시간대별 운영 최적화
    # time_based_operations: List[TimeBasedDRTOperationSchema] = Field(
    #     ..., description="시간대별 운영 최적화 분석"
    # )
    
    # 3. 교통수단 대체 기회
    substitution_opportunities: List[TransportModeSubstitutionSchema] = Field(
        ..., description="기존 교통수단 대체 기회 분석"
    )
    
    # 4. ROI 분석
    roi_analysis: List[DRTROIAnalysisSchema] = Field(
        ..., description="수요 구간별 ROI 분석 (투자 우선순위)"
    )
    
    # 종합 권장사항
    executive_summary: dict = Field(..., description="경영진 요약")
    action_priorities: List[str] = Field(..., description="실행 우선순위 리스트")
    
    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "generated_at": "2025-09-10T14:30:00Z",
                "demand_supply_mismatches": [],
                # "time_based_operations": [],
                "substitution_opportunities": [],
                "roi_analysis": [],
                "executive_summary": {
                    "total_drt_opportunities": 156,
                    "high_impact_routes": 23,
                    "estimated_total_investment": "15억원",
                    "expected_annual_ridership": "2.8만명"
                },
                "action_priorities": [
                    "영등포-서초 축 DRT 노선 우선 도입",
                    "심야시간 서비스 확대 검토",
                    "환승 구간 대체 노선 설계"
                ]
            }
        }


# ==========================================
# 7. 쿼리 파라미터 정의 (GET 요청용)
# ==========================================
# API 엔드포인트에서 직접 쿼리 파라미터로 처리
# 예시:
# GET /api/od/drt-decision?analysis_month=2025-07&district=영등포구&top_n=20
# GET /api/od/demand-supply-mismatch?impact_level=high&min_passengers=1000
# GET /api/od/route-clusters?min_destinations=5&max_distance=15
# 
# Query Parameters:
# - analysis_month (required): 분석 월 (YYYY-MM 형식)
# - district_name (optional): 특정 구 분석 
# - top_n (optional, default=20): 상위 N개 결과


# ==========================================
# 8. OD Pair 시간대별 분석 스키마 (간단버전)
# ==========================================

class ODPairHourlyAnalysisSchema(BaseModel):
    """OD Pair 시간대별 간단 분석"""
    
    # 기본 정보
    od_pair: ODPairInfoSchema = Field(..., description="OD 구간 정보")
    daily_avg_passengers: float = Field(..., description="일평균 승객 수")
    
    # 24시간 분포 (시간:승객수)
    hourly_passengers: dict = Field(
        ..., 
        description="시간대별 승객 수 (0시-23시)",
        example={
            "0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 163,
            "6": 1469, "7": 3748, "8": 6164, "9": 4047, "10": 3141,
            "11": 1626, "12": 2375, "13": 3061, "14": 2008, "15": 1549,
            "16": 1088, "17": 914, "18": 786, "19": 581, "20": 387,
            "21": 562, "22": 165, "23": 0
        }
    )
    
    # 시간대별 집중도 요약
    time_summary: dict = Field(
        ...,
        description="시간대별 집중도 요약",
        example={
            "peak_hour": 8,
            "peak_passengers": 6164,
            "morning_peak_pct": 44.4,
            "evening_peak_pct": 7.3,
            "daytime_pct": 47.3,
            "night_pct": 1.0,
            "pattern_type": "출근시간 집중형"
        }
    )
    
    class Config:
        schema_extra = {
            "example": {
                "od_pair": {
                    "from_station_id": "105900027",
                    "from_station_name": "회기역",
                    "to_station_id": "105900050",
                    "to_station_name": "경희대의료원.경희여중고",
                    "distance_km": 0.66
                },
                "daily_avg_passengers": 1990.2,
                "hourly_passengers": {"8": 6164, "17": 914},
                "time_summary": {
                    "peak_hour": 8,
                    "pattern_type": "출근시간 집중형"
                }
            }
        }