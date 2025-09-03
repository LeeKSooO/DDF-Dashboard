// API 관련 타입 정의
// DRT Dashboard API 통신을 위한 모든 타입들

// Traffic API 타입 정의
export interface HourlyPattern {
  hour: number;
  avg_ride_passengers: number;
  avg_alight_passengers: number;
  avg_total_passengers: number;
}

export interface PeakHour {
  hour: number;
  avg_total_passengers: number;
}

export interface TrafficResponse {
  analysis_month: string;
  region_type: "seoul" | "district";
  region_name: string;
  district_name?: string;
  weekday_patterns: HourlyPattern[];
  weekend_patterns: HourlyPattern[];
  peak_hours: {
    weekday_morning_peak: PeakHour;
    weekday_evening_peak: PeakHour;
    weekend_peak: PeakHour;
  };
  total_weekday_passengers: number;
  total_weekend_passengers: number;
  weekday_weekend_ratio: number;
}

// Heatmap API 타입 정의
export interface StationData {
  station_id: string;
  station_name: string;
  total_traffic: number;
  coordinate: {
    latitude: number;
    longitude: number;
  };
}

export interface DistrictData {
  district_name: string;
  sgg_code: string;
  total_traffic: number;
}

export interface HeatmapResponse {
  analysis_month: string;
  region_type: "seoul" | "district";
  region_name: string;
  district_name?: string;
  stations: StationData[];
  districts: DistrictData[];
}

// DRT Score API 타입 정의
export interface DRTCoordinate {
  lat: number;
  lng: number;
}

export interface DRTStationData {
  station_id: string;
  station_name: string;
  drt_score: number;
  coordinate: DRTCoordinate;
  peak_hour: number;
  commute_demand?: number;
  tourist_demand?: number;
  vulnerable_demand?: number;
}

export interface DRTDistrictData {
  district_name: string;
  sgg_code: string;
  avg_drt_score: number;
  station_count: number;
  top_station?: DRTStationData;
}

export interface DRTScoreResponse {
  analysis_date: string;
  model_type: "commute" | "tourist" | "vulnerable";
  region_name: string;
  stations: DRTStationData[];
  districts: DRTDistrictData[];
  summary?: {
    total_stations: number;
    avg_score: number;
    high_score_stations: number;
  };
}

export interface DRTStationDetailResponse {
  station: DRTStationData;
  hourly_demand: Array<{
    hour: number;
    commute_demand: number;
    tourist_demand: number;
    vulnerable_demand: number;
  }>;
  nearby_stations: DRTStationData[];
  district_ranking: number;
  recommendations: string[];
}

// 공통 응답 타입
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

// API 파라미터 타입
export interface TrafficParams {
  region: string;
  month: string;
}

export interface HeatmapParams {
  region: string;
  month: string;
}

export interface DRTScoreParams {
  region: string;
  model_type: "commute" | "tourist" | "vulnerable";
  date: string;
}