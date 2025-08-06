import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const analyticsClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 분석 데이터 타입 정의
export interface HourlyDemandPattern {
  hour: number;
  demand: number;
  prediction: number;
  confidence: number;
}

export interface RegionalAnalysis {
  region: string;
  totalDemand: number;
  avgProbability: number;
  stopCount: number;
  peakHours: number[];
}

export interface RouteEfficiencyData {
  routeId: string;
  routeName: string;
  demandDensity: number;
  coverage: number;
  efficiency: number;
  avgWaitTime: number;
  onTimePerformance: number;
}

export interface DemandTrendData {
  date: string;
  totalDemand: number;
  avgProbability: number;
  weatherImpact: number;
  eventImpact: number;
}

export interface VehicleOperationalData {
  vehicleId: string;
  routeName: string;
  currentLoad: number;
  maxCapacity: number;
  status: 'active' | 'idle' | 'maintenance';
  location: {
    lat: number;
    lng: number;
  };
  lastUpdate: string;
  estimatedArrival: string;
}

export interface SystemKPIs {
  totalPredictedDemand: number;
  avgProbability: number;
  peakHour: string;
  highDemandStops: number;
  systemUptime: number;
  responseTime: number;
  activeVehicles: number;
  totalVehicles: number;
}

export const analyticsApi = {
  // 시간대별 수요 패턴 분석
  getHourlyDemandPattern: async (
    date: string,
    routeIds?: string[]
  ): Promise<HourlyDemandPattern[]> => {
    const params = new URLSearchParams();
    params.append('date', date);
    if (routeIds) {
      routeIds.forEach(id => params.append('route_ids', id));
    }

    const response = await analyticsClient.get(`/api/v1/analytics/hourly-demand?${params}`);
    return response.data;
  },

  // 지역별 수요 분석
  getRegionalAnalysis: async (
    dateRange: { start: string; end: string }
  ): Promise<RegionalAnalysis[]> => {
    const response = await analyticsClient.post('/api/v1/analytics/regional-analysis', {
      date_start: dateRange.start,
      date_end: dateRange.end
    });
    return response.data;
  },

  // 노선별 효율성 분석
  getRouteEfficiency: async (
    dateRange: { start: string; end: string }
  ): Promise<RouteEfficiencyData[]> => {
    const response = await analyticsClient.post('/api/v1/analytics/route-efficiency', {
      date_start: dateRange.start,
      date_end: dateRange.end
    });
    return response.data;
  },

  // 수요 트렌드 분석 (일주일)
  getDemandTrend: async (
    dateRange: { start: string; end: string }
  ): Promise<DemandTrendData[]> => {
    const response = await analyticsClient.post('/api/v1/analytics/demand-trend', {
      date_start: dateRange.start,
      date_end: dateRange.end
    });
    return response.data;
  },

  // 실시간 차량 운영 현황
  getVehicleOperationalData: async (): Promise<VehicleOperationalData[]> => {
    const response = await analyticsClient.get('/api/v1/operations/vehicles/status');
    return response.data;
  },

  // 시스템 KPI
  getSystemKPIs: async (targetTime?: string): Promise<SystemKPIs> => {
    const params = targetTime ? `?target_time=${targetTime}` : '';
    const response = await analyticsClient.get(`/api/v1/analytics/system-kpis${params}`);
    return response.data;
  },

  // 수요 예측 정확도 분석
  getPredictionAccuracy: async (
    dateRange: { start: string; end: string }
  ): Promise<{
    date: string;
    accuracy: number;
    mape: number; // Mean Absolute Percentage Error
    rmse: number; // Root Mean Square Error
  }[]> => {
    const response = await analyticsClient.post('/api/v1/analytics/prediction-accuracy', {
      date_start: dateRange.start,
      date_end: dateRange.end
    });
    return response.data;
  },

  // 이상 상황 감지 및 알림
  getSystemAlerts: async (): Promise<{
    id: string;
    type: 'warning' | 'error' | 'info';
    title: string;
    description: string;
    timestamp: string;
    resolved: boolean;
    severity: 'low' | 'medium' | 'high' | 'critical';
  }[]> => {
    const response = await analyticsClient.get('/api/v1/operations/alerts');
    return response.data;
  },

  // 수요 예측 시나리오 분석
  getScenarioAnalysis: async (
    targetTime: string,
    scenarios: {
      weather?: 'sunny' | 'rainy' | 'snowy';
      events?: string[];
      holiday?: boolean;
    }
  ): Promise<{
    scenario: string;
    predictions: Array<{
      stop_id: string;
      drt_probability: number;
      predicted_boarding_count: number;
    }>;
    impact_factor: number;
  }[]> => {
    const response = await analyticsClient.post('/api/v1/analytics/scenario-analysis', {
      target_time: targetTime,
      ...scenarios
    });
    return response.data;
  },

  // 노선 최적화 제안
  getRouteOptimizationSuggestions: async (
    criteria: 'demand' | 'efficiency' | 'coverage'
  ): Promise<{
    routeId: string;
    currentPerformance: number;
    suggestedChanges: {
      type: 'frequency' | 'route' | 'timing';
      description: string;
      expectedImprovement: number;
    }[];
    estimatedImpact: {
      demandSatisfaction: number;
      operationalCost: number;
      userSatisfaction: number;
    };
  }[]> => {
    const response = await analyticsClient.get(`/api/v1/analytics/route-optimization?criteria=${criteria}`);
    return response.data;
  }
};

export default analyticsApi;