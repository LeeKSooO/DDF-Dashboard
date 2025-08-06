/*
DRT 운영 지표 타입 정의
실제 교통 데이터 기반 의미있는 운영 지표
*/

// 지역별 교통 사각지대 현황
export interface RegionServiceGap {
  region: string;
  region_kr: string;
  total_stops: number;
  active_stops: number;
  unused_stops: number;
  utilization_rate: number;
  total_boarding: number;
  avg_boarding_per_stop: number;
  service_gap_severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  drt_priority: number; // 1-5 (1이 최우선)
  recommended_vehicles: number;
}

// 시간대별 DRT 운영 필요성
export interface HourlyDRTNeed {
  hour: number;
  time_category: 'MORNING_PEAK' | 'EVENING_PEAK' | 'DAYTIME_OFF_PEAK' | 'EVENING_OFF_PEAK' | 'NIGHT_TIME';
  total_passengers: number;
  active_stops: number;
  avg_boarding_per_event: number;
  bus_service_adequacy: 'SUFFICIENT' | 'NEEDS_SUPPLEMENT' | 'INSUFFICIENT';
  drt_operation_mode: 'NOT_NEEDED' | 'SUPPLEMENTARY' | 'PRIMARY' | 'EXCLUSIVE';
  recommended_frequency: number; // 분 단위
}

// 노선별 DRT 연계 전략
export interface RouteConnectionStrategy {
  route_number: string;
  route_type: string;
  efficiency_grade: 'HIGH_EFFICIENCY' | 'MEDIUM_EFFICIENCY' | 'LOW_EFFICIENCY' | 'POOR_EFFICIENCY';
  stops_count: number;
  active_stops_count: number;
  utilization_rate: number;
  daily_avg_boarding: number;
  drt_connection_type: 'HUB_CONNECTION' | 'FEEDER_SERVICE' | 'ROUTE_REPLACEMENT' | 'NO_CONNECTION';
  hub_stations: string[];
  underutilized_stops: number;
}

// DRT 서비스 권역 설계
export interface DRTServiceZone {
  zone_id: string;
  zone_name: string;
  region: string;
  center_lat: number;
  center_lng: number;
  coverage_radius: number; // km
  total_stops: number;
  target_stops: number[];
  service_type: 'ON_DEMAND' | 'SCHEDULED' | 'HYBRID';
  operating_hours: {
    start: string;
    end: string;
  };
  recommended_vehicles: number;
  expected_daily_trips: number;
  connection_points: string[]; // 기존 버스와 연결점
}

// 실시간 DRT 운영 현황
export interface DRTOperationalStatus {
  zone_id: string;
  zone_name: string;
  active_vehicles: number;
  total_vehicles: number;
  current_requests: number;
  completed_trips_today: number;
  average_response_time: number; // 분
  average_trip_time: number; // 분
  passenger_satisfaction: number; // 1-5
  cost_per_trip: number;
  revenue_per_trip: number;
  occupancy_rate: number; // %
}

// 종합 DRT 성과 지표
export interface DRTPerformanceKPIs {
  // 서비스 접근성
  service_coverage: {
    total_service_area: number; // km²
    population_covered: number;
    stops_served: number;
    coverage_improvement: number; // % vs 기존 버스만
  };
  
  // 운영 효율성
  operational_efficiency: {
    vehicle_utilization: number; // %
    average_occupancy: number; // 명/대
    trips_per_vehicle_per_day: number;
    on_time_performance: number; // %
    service_reliability: number; // %
  };
  
  // 경제적 성과
  financial_performance: {
    daily_revenue: number;
    daily_operating_cost: number;
    cost_recovery_ratio: number; // %
    subsidy_per_passenger: number;
    break_even_passengers_per_day: number;
  };
  
  // 사회적 영향
  social_impact: {
    mobility_improved_population: number;
    reduced_private_car_usage: number; // %
    elderly_mobility_improvement: number; // %
    employment_accessibility_improvement: number; // %
    medical_facility_accessibility: number; // %
  };
}

// 예측 vs 실제 성과 비교 (MST-GCN 모델 검증용)
export interface PredictionValidation {
  date: string;
  zone_id: string;
  predicted_demand_probability: number;
  actual_trip_requests: number;
  actual_completed_trips: number;
  prediction_accuracy: number; // %
  model_confidence: number;
  adjustment_factor: number; // 예측 보정 계수
}

// 대시보드 메인 요약
export interface DRTDashboardSummary {
  current_date: string;
  total_active_zones: number;
  total_vehicles_operating: number;
  daily_trips_completed: number;
  daily_trips_target: number;
  service_areas_covered: string[];
  critical_alerts: {
    type: 'SERVICE_GAP' | 'VEHICLE_SHORTAGE' | 'HIGH_DEMAND' | 'SYSTEM_ERROR';
    message: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    zone_affected?: string;
  }[];
  key_metrics: {
    avg_response_time: number;
    customer_satisfaction: number;
    cost_efficiency: number;
    environmental_impact: number; // CO2 절약량
  };
}