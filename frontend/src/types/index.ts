// DRT 대시보드 타입 정의

export interface BusStop {
  stop_id: string;
  stop_name: string;
  latitude: number;
  longitude: number;
  district: string;
  is_active: boolean;
}

export interface DRTPrediction {
  stop_id: string;
  stop_name?: string;
  drt_probability: number;
  predicted_boarding_count: number;
  prediction_horizon: number;
  confidence_interval: {
    lower: number;
    upper: number;
  };
}

export interface PredictionResponse {
  request_id: string;
  target_datetime: string;
  predictions: DRTPrediction[];
  model_version: string;
  processing_time_ms: number;
}

export interface HeatmapData {
  latitude: number;
  longitude: number;
  intensity: number; // DRT 확률 (0-1)
  stop_id: string;
  stop_name?: string;
}

export interface TimeSelection {
  date: string;
  hour: number;
}

export interface MapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

export interface BusRoute {
  route_id: string;
  route_no: string;
  route_type: string;
  start_node: string;
  end_node: string;
  stop_count: number;
  color: string;
  coordinates: [number, number][];
}

// API 응답 타입
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}