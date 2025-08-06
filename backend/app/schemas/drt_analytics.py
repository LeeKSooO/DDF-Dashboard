from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Union
from datetime import datetime, time
from enum import IntEnum

# =============================================================================
# 기본 데이터 스키마 (실제 DB 데이터)
# =============================================================================

class BusStopBase(BaseModel):
    """정류장 기본 정보"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    district: str = Field(..., description="행정구역")
    is_active: bool = Field(default=True, description="운영 여부")

class BusStopResponse(BusStopBase):
    """정류장 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

class BusRouteBase(BaseModel):
    """버스 노선 기본 정보"""
    route_id: str = Field(..., description="노선 ID")
    route_number: str = Field(..., description="노선 번호")
    route_type: str = Field(..., description="노선 유형")
    start_point: str = Field(..., description="기점")
    end_point: str = Field(..., description="종점")
    first_bus_time: time = Field(..., description="첫차 시간")
    last_bus_time: time = Field(..., description="막차 시간")
    weekday_interval: int = Field(..., description="평일 배차간격(분)")
    saturday_interval: Optional[int] = Field(None, description="토요일 배차간격(분)")
    sunday_interval: Optional[int] = Field(None, description="일요일 배차간격(분)")
    is_active: bool = Field(default=True, description="운영 여부")

class BusRouteResponse(BusRouteBase):
    """버스 노선 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

class RouteStopBase(BaseModel):
    """노선-정류장 연결 정보"""
    route_id: str = Field(..., description="노선 ID")
    stop_id: str = Field(..., description="정류장 ID")
    stop_sequence: int = Field(..., description="정류장 순서")

class RouteStopResponse(RouteStopBase):
    """노선-정류장 연결 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

class StopUsageBase(BaseModel):
    """정류장 이용량 정보"""
    stop_id: str = Field(..., description="정류장 ID")
    recorded_at: datetime = Field(..., description="기록 시간")
    boarding_count: int = Field(default=0, description="승차 인원")
    alighting_count: int = Field(default=0, description="하차 인원")
    is_operational: bool = Field(default=True, description="운행 여부")
    is_holiday: bool = Field(default=False, description="공휴일 여부")
    is_weekend: bool = Field(default=False, description="주말 여부")

class StopUsageResponse(StopUsageBase):
    """정류장 이용량 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# 집계 데이터 스키마
# =============================================================================

class StopUsageAggregated(BaseModel):
    """정류장별 집계 이용량"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    total_boarding: int = Field(..., description="총 승차 인원")
    total_alighting: int = Field(..., description="총 하차 인원")
    avg_boarding: float = Field(..., description="평균 승차 인원")
    avg_alighting: float = Field(..., description="평균 하차 인원")
    active_days_count: int = Field(..., description="운행일 수")
    utilization_rate: float = Field(..., description="이용률 (%)")

class DailyUsageSummary(BaseModel):
    """일별 이용량 요약"""
    date: datetime = Field(..., description="날짜")
    daily_total_boarding: int = Field(..., description="일별 총 승차")
    daily_total_alighting: int = Field(..., description="일별 총 하차")
    active_stops_count: int = Field(..., description="활성 정류장 수")
    total_stops_count: int = Field(..., description="전체 정류장 수")
    stop_utilization_rate: float = Field(..., description="정류장 활용률 (%)")

# =============================================================================
# DRT 특성 분석 스키마 (drt_probability 제외)
# =============================================================================

class ServiceAvailability(IntEnum):
    """서비스 가용성 레벨"""
    NO_SERVICE = 0
    LIMITED_SERVICE = 1
    FULL_SERVICE = 2

class DRTFeatureBase(BaseModel):
    """DRT 특성 분석 기본 데이터 (확률 제외)"""
    stop_id: str = Field(..., description="정류장 ID")
    recorded_at: datetime = Field(..., description="기록 시간")
    normalized_log_boarding_count: float = Field(..., description="정규화된 로그 승차수")
    service_availability: ServiceAvailability = Field(..., description="서비스 가용성")
    is_rest_day: bool = Field(..., description="휴무일 여부")
    normalized_interval: float = Field(..., description="정규화된 배차간격")
    hour_of_day: int = Field(..., ge=0, le=23, description="시간(0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="요일(0-6)")
    is_weekend: bool = Field(..., description="주말 여부")
    is_holiday: bool = Field(..., description="공휴일 여부")
    is_in_service_hours: bool = Field(..., description="운행시간 내 여부")
    applicable_interval: int = Field(..., description="적용 배차간격")
    route_count: int = Field(..., description="노선 수")

class DRTFeatureResponse(DRTFeatureBase):
    """DRT 특성 응답 스키마"""
    feature_id: int = Field(..., description="특성 ID")
    created_at: datetime = Field(..., description="생성 시간")
    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# DRT 확률 분석 스키마 (별도 분리)
# =============================================================================

class DRTProbabilityBase(BaseModel):
    """DRT 필요 확률 분석 (추정 데이터)"""
    stop_id: str = Field(..., description="정류장 ID")
    recorded_at: datetime = Field(..., description="기록 시간")
    drt_probability: float = Field(..., ge=0.0, le=1.0, description="DRT 필요 확률 (0-1)")
    confidence_level: Optional[float] = Field(None, ge=0.0, le=1.0, description="예측 신뢰도")

class DRTProbabilityResponse(DRTProbabilityBase):
    """DRT 확률 응답 스키마"""
    probability_id: int = Field(..., description="확률 분석 ID")
    model_version: Optional[str] = Field(None, description="사용된 모델 버전")
    created_at: datetime = Field(..., description="분석 생성 시간")
    model_config = ConfigDict(from_attributes=True)

class DRTProbabilityAggregated(BaseModel):
    """정류장별 DRT 확률 집계"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    avg_drt_probability: float = Field(..., description="평균 DRT 필요 확률")
    max_drt_probability: float = Field(..., description="최대 DRT 필요 확률")
    high_probability_hours: List[int] = Field(..., description="고확률 시간대 리스트")
    peak_probability_time: Optional[datetime] = Field(None, description="최고 확률 시점")

# =============================================================================
# DRT 운영 인사이트 스키마
# =============================================================================

class TransportationGapAnalysis(BaseModel):
    """교통 공백 지역 분석"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    nearest_stop_distance: float = Field(..., description="최근접 정류장까지 거리(m)")
    route_count: int = Field(..., description="경유 노선 수")
    avg_daily_usage: float = Field(..., description="일평균 이용량")
    usage_per_route: float = Field(..., description="노선당 이용량")
    isolation_level: str = Field(..., description="고립도 (높음/중간/낮음)")
    drt_priority_score: float = Field(..., description="DRT 도입 우선순위 점수")

class ServiceGapAnalysis(BaseModel):
    """시간대별 서비스 공백 분석"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    hour_of_day: int = Field(..., description="시간대")
    avg_usage: float = Field(..., description="평균 이용량")
    available_routes: int = Field(..., description="이용 가능 노선 수")
    avg_interval_minutes: float = Field(..., description="평균 배차간격(분)")
    drt_recommendation: str = Field(..., description="DRT 운영 권장사항")
    gap_severity: str = Field(..., description="서비스 공백 심각도")

class WeekendServiceGap(BaseModel):
    """주말 서비스 격차 분석"""
    stop_id: str = Field(..., description="정류장 ID")
    stop_name: str = Field(..., description="정류장 명")
    weekday_avg_usage: float = Field(..., description="평일 평균 이용량")
    weekend_avg_usage: float = Field(..., description="주말 평균 이용량")
    weekday_interval: int = Field(..., description="평일 배차간격")
    weekend_interval: Optional[int] = Field(None, description="주말 배차간격")
    weekend_service_ratio: float = Field(..., description="주말 서비스 비율")
    weekend_drt_necessity: str = Field(..., description="주말 DRT 필요도")

class RouteConnectivityAnalysis(BaseModel):
    """노선 연결성 분석"""
    origin_stop_id: str = Field(..., description="출발 정류장 ID")
    destination_stop_id: str = Field(..., description="도착 정류장 ID")
    origin_stop_name: str = Field(..., description="출발 정류장명")
    destination_stop_name: str = Field(..., description="도착 정류장명")
    demand_score: float = Field(..., description="수요 점수")
    direct_connection_count: int = Field(..., description="직접 연결 노선 수")
    drt_opportunity: str = Field(..., description="DRT 연결 기회")
    estimated_travel_time: Optional[int] = Field(None, description="예상 이동시간(분)")

# =============================================================================
# 수요 예측 스키마 (추정 데이터 - 별도 분리)
# =============================================================================

class DemandEstimationMethod(BaseModel):
    """수요 추정 방법론"""
    method_name: str = Field(..., description="추정 방법명")
    base_data_period: str = Field(..., description="기준 데이터 기간")
    confidence_interval: float = Field(..., description="신뢰구간 (%)")
    estimation_date: datetime = Field(..., description="추정 수행 일시")

class ExpectedDemandBase(BaseModel):
    """예상 수요 기본 정보 (추정 데이터)"""
    area_id: str = Field(..., description="지역/정류장 ID")
    area_name: str = Field(..., description="지역/정류장명")
    daily_expected_calls: int = Field(..., description="일일 예상 호출 건수")
    peak_hour_calls: int = Field(..., description="피크시간 예상 호출")
    off_peak_calls: int = Field(..., description="비피크시간 예상 호출")
    weekend_calls: int = Field(..., description="주말 예상 호출")
    demand_level: str = Field(..., description="수요 수준 (높음/중간/낮음)")
    
class ExpectedDemandResponse(ExpectedDemandBase):
    """예상 수요 응답 스키마"""
    estimation_id: int = Field(..., description="추정 ID")
    method_used: DemandEstimationMethod = Field(..., description="사용된 추정 방법")
    lower_bound: int = Field(..., description="예상 수요 하한")
    upper_bound: int = Field(..., description="예상 수요 상한")
    model_config = ConfigDict(from_attributes=True)

class VehicleRequirementEstimation(BaseModel):
    """차량 소요 추정 (추정 데이터)"""
    area_id: str = Field(..., description="지역 ID")
    area_name: str = Field(..., description="지역명")
    peak_vehicle_count: int = Field(..., description="피크시간 필요 차량 수")
    off_peak_vehicle_count: int = Field(..., description="비피크시간 필요 차량 수")
    total_daily_km: float = Field(..., description="일일 예상 운행거리(km)")
    estimated_operating_cost: float = Field(..., description="예상 운영비용(일일)")
    cost_per_passenger: float = Field(..., description="승객당 예상 비용")
    estimation_method: DemandEstimationMethod = Field(..., description="추정 방법")

# =============================================================================
# 대시보드 응답 스키마 (실측 데이터 중심)
# =============================================================================

class DRTDashboardSummary(BaseModel):
    """DRT 대시보드 요약 정보 (실측 데이터 기반)"""
    total_stops: int = Field(..., description="총 정류장 수")
    isolated_stops_count: int = Field(..., description="고립된 정류장 수 (실측)")
    high_drt_probability_stops: int = Field(..., description="DRT 고확률 정류장 수")
    service_gap_hours: List[int] = Field(..., description="서비스 공백 시간대 (실측)")
    weekend_gap_stops: int = Field(..., description="주말 서비스 부족 정류장 수 (실측)")
    top_drt_priority_areas: List[str] = Field(..., description="DRT 우선 도입 지역")
    
    # 추정 데이터는 별도 필드로 구분
    has_demand_estimation: bool = Field(default=False, description="수요 추정 데이터 포함 여부")

class DRTRecommendation(BaseModel):
    """DRT 운영 권장사항 (실측 데이터 기반)"""
    area_name: str = Field(..., description="지역명")
    recommendation_type: str = Field(..., description="권장 유형")
    priority_level: str = Field(..., description="우선순위 (높음/중간/낮음)")
    
    # 실측 데이터 기반 근거
    current_usage_pattern: str = Field(..., description="현재 이용 패턴 (실측)")
    service_gap_severity: str = Field(..., description="서비스 공백 심각도 (실측)")
    operating_hours: str = Field(..., description="권장 운행시간 (실측 기반)")
    rationale: str = Field(..., description="권장 근거 (실측 데이터)")
    
    # 추정 데이터는 별도 객체로 분리
    demand_estimation: Optional[ExpectedDemandBase] = Field(None, description="수요 추정 (추정 데이터)")
    vehicle_requirement: Optional[VehicleRequirementEstimation] = Field(None, description="차량 소요 추정")

# =============================================================================
# 요청/응답 래퍼 스키마
# =============================================================================

class DateRangeFilter(BaseModel):
    """날짜 범위 필터"""
    start_date: datetime = Field(..., description="시작 날짜")
    end_date: datetime = Field(..., description="종료 날짜")

class StopFilter(BaseModel):
    """정류장 필터"""
    stop_ids: Optional[List[str]] = Field(None, description="정류장 ID 목록")
    district: Optional[str] = Field(None, description="행정구역")
    min_usage: Optional[int] = Field(None, description="최소 이용량")

class TimeFilter(BaseModel):
    """시간 필터"""
    hours: Optional[List[int]] = Field(None, description="시간대 목록")
    weekdays_only: Optional[bool] = Field(None, description="평일만")
    weekends_only: Optional[bool] = Field(None, description="주말만")

class DRTAnalysisRequest(BaseModel):
    """DRT 분석 요청"""
    date_range: DateRangeFilter
    stop_filter: Optional[StopFilter] = None
    time_filter: Optional[TimeFilter] = None
    analysis_types: List[str] = Field(..., description="분석 유형 목록")
    include_probability: bool = Field(default=True, description="확률 데이터 포함 여부")

class DRTAnalysisResponse(BaseModel):
    """DRT 분석 응답"""
    # 실측 데이터 기반 분석 결과
    summary: DRTDashboardSummary
    transportation_gaps: List[TransportationGapAnalysis]
    service_gaps: List[ServiceGapAnalysis]
    weekend_gaps: List[WeekendServiceGap]
    connectivity_analysis: List[RouteConnectivityAnalysis]
    recommendations: List[DRTRecommendation]
    
    # 추정/예측 데이터는 선택적으로 포함
    drt_probabilities: Optional[List[DRTProbabilityAggregated]] = Field(None, description="DRT 필요 확률 (예측)")
    demand_estimations: Optional[List[ExpectedDemandResponse]] = Field(None, description="수요 추정 (예측)")
    vehicle_requirements: Optional[List[VehicleRequirementEstimation]] = Field(None, description="차량 소요 추정")
    
    # 메타데이터
    data_types_included: List[str] = Field(..., description="포함된 데이터 유형")
    generated_at: datetime = Field(default_factory=datetime.now, description="생성 시간")
    estimation_disclaimer: str = Field(
        default="수요 추정 및 확률 데이터는 과거 시내버스 이용 패턴을 바탕으로 한 예측값입니다.",
        description="추정 데이터 면책사항"
    )

# =============================================================================
# 페이지네이션
# =============================================================================

class PaginationParams(BaseModel):
    """페이지네이션 매개변수"""
    page: int = Field(default=1, ge=1, description="페이지 번호")
    size: int = Field(default=20, ge=1, le=100, description="페이지 크기")

class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""
    items: List[BaseModel] = Field(..., description="데이터 목록")
    total: int = Field(..., description="전체 항목 수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    pages: int = Field(..., description="전체 페이지 수")

# =============================================================================
# 에러 응답 스키마
# =============================================================================

class ErrorResponse(BaseModel):
    """에러 응답"""
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 정보")
    timestamp: datetime = Field(default_factory=datetime.now, description="발생 시간")