"""
DRT 운영 지표 스키마 정의
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# 지역별 서비스 공백 응답
class RegionServiceGapResponse(BaseModel):
    region: str
    region_kr: str
    total_stops: int
    active_stops: int
    unused_stops: int
    utilization_rate: float
    total_boarding: int
    avg_boarding_per_stop: float
    service_gap_severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    drt_priority: int
    recommended_vehicles: int

# 시간대별 DRT 필요도 응답
class HourlyDRTNeedResponse(BaseModel):
    hour: int
    time_category: str  # MORNING_PEAK, EVENING_PEAK, DAYTIME_OFF_PEAK, etc.
    total_passengers: int
    active_stops: int
    avg_boarding_per_event: float
    bus_service_adequacy: str  # SUFFICIENT, NEEDS_SUPPLEMENT, INSUFFICIENT
    drt_operation_mode: str  # EXCLUSIVE, PRIMARY, SUPPLEMENTARY, NOT_NEEDED
    recommended_frequency: int

# 노선별 연계 전략 응답
class RouteConnectionStrategyResponse(BaseModel):
    route_number: str
    route_type: str
    efficiency_grade: str  # HIGH_EFFICIENCY, MEDIUM_EFFICIENCY, LOW_EFFICIENCY
    stops_count: int
    active_stops_count: int
    utilization_rate: float
    daily_avg_boarding: float
    drt_connection_type: str  # HUB_CONNECTION, FEEDER_SERVICE, ROUTE_REPLACEMENT
    hub_stations: List[str]
    underutilized_stops: int

# DRT 서비스 권역 응답
class DRTServiceZoneResponse(BaseModel):
    zone_id: str
    zone_name: str
    region: str
    center_lat: float
    center_lng: float
    coverage_radius: float
    total_stops: int
    service_type: str  # ON_DEMAND, SCHEDULED, HYBRID
    operating_hours: dict
    recommended_vehicles: int
    expected_daily_trips: int
    connection_points: List[str]

# 서비스 커버리지
class ServiceCoverage(BaseModel):
    total_service_area: float
    population_covered: int
    stops_served: int
    coverage_improvement: int

# 운영 효율성
class OperationalEfficiency(BaseModel):
    vehicle_utilization: int
    average_occupancy: float
    trips_per_vehicle_per_day: int
    on_time_performance: int
    service_reliability: int

# 재정 성과
class FinancialPerformance(BaseModel):
    daily_revenue: int
    daily_operating_cost: int
    cost_recovery_ratio: int
    subsidy_per_passenger: int
    break_even_passengers_per_day: int

# 사회적 영향
class SocialImpact(BaseModel):
    mobility_improved_population: int
    reduced_private_car_usage: int
    elderly_mobility_improvement: int
    employment_accessibility_improvement: int
    medical_facility_accessibility: int

# DRT 성과 지표 응답
class DRTPerformanceKPIsResponse(BaseModel):
    service_coverage: ServiceCoverage
    operational_efficiency: OperationalEfficiency
    financial_performance: FinancialPerformance
    social_impact: SocialImpact