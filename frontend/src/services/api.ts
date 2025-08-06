import axios from 'axios';
import { PredictionResponse, BusStop, HeatmapData, DRTPrediction } from '../types';
import { 
  RegionServiceGap, 
  HourlyDRTNeed, 
  RouteConnectionStrategy, 
  DRTPerformanceKPIs
} from '../types/drtMetrics';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const predictionApi = {
  // DRT 예측 요청 (전체 정류장)
  getPredictions: async (
    targetDatetime: string
  ): Promise<PredictionResponse> => {
    const response = await apiClient.post('/api/v1/predictions/predict', {
      target_datetime: targetDatetime,
    });
    return response.data;
  },

  // 히트맵 데이터 요청 (Top N 정류장)
  getHeatmapData: async (
    targetDatetime: string,
    topN: number = 10
  ): Promise<HeatmapData[]> => {
    // 전체 정류장 예측 데이터 가져오기
    const response = await predictionApi.getPredictions(targetDatetime);
    const predictions = response.predictions;
    
    // DRT 확률 기준으로 정렬하여 상위 N개 추출
    const topPredictions = predictions
      .sort((a: DRTPrediction, b: DRTPrediction) => b.drt_probability - a.drt_probability)
      .slice(0, topN);
    
    // 정류장 좌표 정보와 합쳐서 히트맵 데이터 생성
    const busStops = await busStopApi.getAllStops();
    
    return topPredictions.map((pred: DRTPrediction) => {
      const stop = busStops.find(s => s.stop_id === pred.stop_id);
      return {
        latitude: stop?.latitude || 0,
        longitude: stop?.longitude || 0,
        intensity: pred.drt_probability,
        stop_id: pred.stop_id,
        stop_name: stop?.stop_name,
      };
    });
  },

  // 특정 정류장 상세 정보
  getStopDetail: async (stopId: string, targetDatetime: string) => {
    // 전체 예측에서 해당 정류장만 찾기
    const response = await predictionApi.getPredictions(targetDatetime);
    return response.predictions.find(p => p.stop_id === stopId) || null;
  },
};

export const busStopApi = {
  // 모든 정류장 정보
  getAllStops: async (): Promise<BusStop[]> => {
    try {
      const response = await apiClient.get('/api/v1/bus-stops/');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch bus stops:', error);
      // API 실패시 더미 데이터 반환
      return generateDummyBusStops();
    }
  },

  // 특정 정류장 정보
  getStop: async (stopId: string): Promise<BusStop | null> => {
    const stops = await busStopApi.getAllStops();
    return stops.find(stop => stop.stop_id === stopId) || null;
  },
};

// 임시 더미 데이터 (실제 DB 연동 전까지 사용)
function generateDummyBusStops(): BusStop[] {
  const stops: BusStop[] = [];
  
  // 가평군 영역 (대략적인 좌표 범위)
  const bounds = {
    north: 37.986850,
    south: 37.512117,
    west: 127.044667,
    east: 127.607017,
  };
  
  for (let i = 1; i <= 957; i++) {
    stops.push({
      stop_id: `GGB239000${String(i).padStart(3, '0')}`,
      stop_name: `정류장${i}`,
      latitude: bounds.south + Math.random() * (bounds.north - bounds.south),
      longitude: bounds.west + Math.random() * (bounds.east - bounds.west),
      district: '가평군',
      is_active: true,
    });
  }
  
  return stops;
}

// DRT 운영 분석 API
export const drtAnalyticsApi = {
  // 지역별 서비스 공백 분석
  getServiceGaps: async (analysisDate?: string, analysisHour?: number): Promise<RegionServiceGap[]> => {
    const params: any = {};
    if (analysisDate) params.analysis_date = analysisDate;
    if (analysisHour !== undefined) params.analysis_hour = analysisHour;
    const response = await apiClient.get('/api/v1/drt-analytics/service-gaps', { params });
    return response.data;
  },

  // 시간대별 DRT 최적화 데이터
  getHourlyOptimization: async (analysisDate?: string, targetHour?: number): Promise<HourlyDRTNeed[]> => {
    const params: any = {};
    if (analysisDate) params.analysis_date = analysisDate;
    if (targetHour !== undefined) params.target_hour = targetHour;
    const response = await apiClient.get('/api/v1/drt-analytics/hourly-optimization', { params });
    return response.data;
  },

  // 노선별 연계 전략
  getRouteStrategies: async (): Promise<RouteConnectionStrategy[]> => {
    const response = await apiClient.get('/api/v1/drt-analytics/route-strategies');
    return response.data;
  },

  // DRT 성과 지표
  getPerformanceKPIs: async (): Promise<DRTPerformanceKPIs> => {
    const response = await apiClient.get('/api/v1/drt-analytics/performance-kpi');
    return response.data;
  },

  // 긴급 알림
  getCriticalAlerts: async () => {
    const response = await apiClient.get('/api/v1/drt-analytics/critical-alerts');
    return response.data;
  }
};

export default apiClient;