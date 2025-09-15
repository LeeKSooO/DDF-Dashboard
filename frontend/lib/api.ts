// API 서비스 레이어
// DRT Dashboard API 통신을 위한 함수들

import { API_BASE_URL, RAG_API_URL } from './constants';

// RAG API 타입 정의
export interface RAGQueryRequest {
  query: string;
  max_results?: number;
  similarity_threshold?: number;
  use_multi_query?: boolean;
  include_sources?: boolean;
  backend_data?: boolean;
  summary_only?: boolean;
}

export interface RAGQueryResponse {
  status: string;
  message: string;
  query: string;
  answer: string;
  sources?: Array<{
    reasoning_steps?: unknown[];
    generated_queries?: string[];
    documents_retrieved?: number;
    documents_reranked?: number;
    unique_sources?: number;
    reranking_enabled?: boolean;
    top_rerank_scores?: number[];
  }>;
  backend_data?: {
    cot_enabled: boolean;
    multi_query_enabled?: boolean;
    query_mode?: string;
    reranking_enabled?: boolean;
  };
  confidence?: number;
}

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
  total_ride?: number;
  total_alight?: number;
  coordinate: {
    latitude: number;
    longitude: number;
  };
}

export interface DistrictData {
  district_name: string;
  sgg_code: string;
  total_traffic: number;
  total_ride: number;
  total_alight: number;
  avg_daily_traffic: number;
  traffic_rank: number;
  traffic_density_score: number;
  boundary?: {
    type: string;
    coordinates: number[][][];
  };
  stations: StationData[];
}

export interface HeatmapStatistics {
  total_seoul_traffic: number;
  total_stations: number;
  max_district_traffic: number;
  min_district_traffic: number;
  district_traffic_quartiles: number[];
  max_station_traffic: number;
  station_traffic_quartiles: number[];
}

export interface HeatmapResponse {
  analysis_month: string;
  seoul_boundary?: {
    type: string;
    coordinates: number[][][][];
  };
  districts: DistrictData[];
  statistics: HeatmapStatistics;
}

// DRT Score API 타입 정의
export interface DRTStationData {
  station_id: string;
  station_name: string;
  coordinate: {
    lat: number;
    lng: number;
  };
  drt_score: number;
  peak_hour: number;
}

// 정류장 상세 정보 API 응답 타입
export interface DRTStationDetailResponse {
  station: {
    station_id: string;
    station_name: string;
    latitude: number;
    longitude: number;
    district_name: string;
    administrative_dong: string;
  };
  model_type: DRTModelType;
  analysis_month: string;
  current_hour: number;
  current_score: number;
  peak_score: number;
  peak_hour: number;
  monthly_average: number;
  feature_scores: FeatureScores;
  hourly_scores: Array<{
    hour: number;
    score: number;
  }>;
}

export interface DRTTopStation {
  station_id: string;
  station_name: string;
  coordinate: {
    lat: number;
    lng: number;
  };
  drt_score: number;
  peak_hour: number;
}

export interface DRTScoreResponse {
  district_name: string;
  model_type: "commuter" | "tourism" | "vulnerable";
  analysis_month: string;
  stations: DRTStationData[];
  top_stations: DRTTopStation[];
}

export type DRTModelType = "commuter" | "tourism" | "vulnerable";

// Feature scores 타입 정의 (모델별로 다른 구조)
export interface VulnerableFeatureScores {
  var_t_score: number;
  sed_t_score: number;
  mdi_t_score: number;
  avs_score: number;
}

export interface CommuterFeatureScores {
  tc_score: number;
  pdr_score: number;
  ru_score: number;
  pcw_score: number;
}

export interface TourismFeatureScores {
  tc_t_score: number;
  tdr_t_score: number;
  ru_t_score: number;
  pcw_score: number;
}

export type FeatureScores = VulnerableFeatureScores | CommuterFeatureScores | TourismFeatureScores;

// Health check 응답 타입
export interface HealthResponse {
  status: string;
  timestamp?: string;
  message?: string;
}

// API 함수들
class ApiService {
  private async fetchWithErrorHandling<T>(url: string): Promise<T> {
    try {
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("API request failed:", error);
      throw error;
    }
  }

  // 시간대별 교통량 패턴 조회
  async getHourlyTraffic(
    analysisMonth: string,
    regionType: "seoul" | "district" = "seoul",
    districtName?: string
  ): Promise<TrafficResponse> {
    const params = new URLSearchParams({
      analysis_month: analysisMonth,
      region_type: regionType,
    });

    if (regionType === "district" && districtName) {
      params.append("district_name", districtName);
    }

    const url = `${API_BASE_URL}/traffic/hourly?${params.toString()}`;
    return this.fetchWithErrorHandling<TrafficResponse>(url);
  }

  // 서울시 히트맵 데이터 조회
  async getSeoulHeatmap(
    analysisMonth: string,
    includeStationDetails: boolean = true,
    minTrafficThreshold?: number
  ): Promise<HeatmapResponse> {
    const params = new URLSearchParams({
      analysis_month: analysisMonth,
      include_station_details: includeStationDetails.toString(),
    });

    if (minTrafficThreshold !== undefined) {
      params.append("min_traffic_threshold", minTrafficThreshold.toString());
    }

    const url = `${API_BASE_URL}/heatmap/seoul?${params.toString()}`;
    return this.fetchWithErrorHandling<HeatmapResponse>(url);
  }

  // 특정 구 히트맵 데이터 조회
  async getDistrictHeatmap(
    districtName: string,
    analysisMonth: string,
    minTrafficThreshold?: number
  ): Promise<DistrictData> {
    const params = new URLSearchParams({
      analysis_month: analysisMonth,
    });

    if (minTrafficThreshold !== undefined) {
      params.append("min_traffic_threshold", minTrafficThreshold.toString());
    }

    const url = `${API_BASE_URL}/heatmap/districts/${encodeURIComponent(
      districtName
    )}?${params.toString()}`;
    return this.fetchWithErrorHandling<DistrictData>(url);
  }

  // API 상태 확인
  async getTrafficHealth(): Promise<HealthResponse> {
    const url = `${API_BASE_URL}/traffic/hourly/health`;
    return this.fetchWithErrorHandling<HealthResponse>(url);
  }

  async getHeatmapHealth(): Promise<HealthResponse> {
    const url = `${API_BASE_URL}/heatmap/health`;
    return this.fetchWithErrorHandling<HealthResponse>(url);
  }

  // DRT Score 관련 API 함수들

  // 구별 DRT 점수 조회
  async getDRTScores(
    districtName: string = "강남구",  // Default 지역
    modelType: DRTModelType = "vulnerable",  // Default 모델
analysisMonth: string
  ): Promise<DRTScoreResponse> {
    const params = new URLSearchParams({
      model_type: modelType,
      analysis_month: analysisMonth,
    });

    const url = `${API_BASE_URL}/drt-score/districts/${encodeURIComponent(
      districtName
    )}?${params.toString()}`;
    
    console.log('🌐 API Request:', { url, districtName, modelType, analysisMonth });
    
    const result = await this.fetchWithErrorHandling<DRTScoreResponse>(url);
    console.log('🌐 API Response:', result);
    
    return result;
  }

  // 정류장 상세 정보 조회 (시간대별 점수 포함)
  async getStationDetail(
    stationId: string,
    modelType: DRTModelType = "vulnerable",
analysisMonth: string
  ): Promise<DRTStationDetailResponse> {
    const params = new URLSearchParams({
      model_type: modelType,
      analysis_month: analysisMonth,
    });

    const url = `${API_BASE_URL}/drt-score/stations/${encodeURIComponent(stationId)}?${params.toString()}`;
    
    console.log('🌐 Station Detail API Request:', { url, stationId, modelType, analysisMonth });
    
    const result = await this.fetchWithErrorHandling<DRTStationDetailResponse>(url);
    console.log('🌐 Station Detail API Response:', result);
    
    return result;
  }

  // 여러 구의 DRT 점수 조회 (대시보드용)
  async getMultipleDRTScores(
    districtNames: string[],
    modelType: DRTModelType,
analysisMonth: string
  ): Promise<DRTScoreResponse[]> {
    const promises = districtNames.map((districtName) =>
      this.getDRTScores(districtName, modelType, analysisMonth)
    );

    return Promise.all(promises);
  }

  // 서울시 전체 DRT Top 정류장 조회 (여러 구 통합)
  async getSeoulTopDRTStations(
    modelType: DRTModelType,
analysisMonth: string,
    topN: number = 10
  ): Promise<DRTTopStation[]> {
    // 주요 구들을 조회해서 Top 정류장들을 수집
    const majorDistricts = [
      "강남구",
      "강서구",
      "관악구",
      "광진구",
      "마포구",
      "서초구",
      "성동구",
      "송파구",
      "영등포구",
      "용산구",
    ];

    try {
      const responses = await this.getMultipleDRTScores(
        majorDistricts,
        modelType,
        analysisMonth
      );

      // 모든 구의 top_stations를 수집하고 점수순으로 정렬
      const allTopStations = responses
        .flatMap((response) => response.top_stations)
        .sort((a, b) => b.drt_score - a.drt_score)
        .slice(0, topN);

      return allTopStations;
    } catch (error) {
      console.error("Failed to fetch Seoul top DRT stations:", error);
      return [];
    }
  }

  // Anomaly Pattern API 함수들

  // 구별 anomaly 패턴 데이터 조회 (통합)
  async getAnomalyPatterns(
    districtName: string,
analysisMonth: string
  ): Promise<any> { // eslint-disable-line @typescript-eslint/no-explicit-any
    const url = `${API_BASE_URL}/anomaly-pattern/integration?district_name=${encodeURIComponent(districtName)}&analysis_month=${analysisMonth}`;
    
    const result = await this.fetchWithErrorHandling(url);
    
    return result;
  }

  // 📝 개별 패턴 API들은 getIntegratedPatterns()로 통합됨

  // 통합 패턴 분석 (서울 전체 또는 구별 - 6개 패턴 종합)
  async getIntegratedPatterns(
    analysisMonth: string,
    districtName?: string,
    topN: number = 5
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ): Promise<any> {
    try {
      const params = new URLSearchParams({
        analysis_month: analysisMonth,
        top_n: String(topN)
      });
      
      if (districtName) {
        params.append('district_name', districtName);
      }
      
      const url = `${API_BASE_URL}/anomaly-pattern/integration?${params.toString()}`;
      const response = await this.fetchWithErrorHandling(url);
      
      // 통합 응답을 기존 state 형태에 맞게 정리
      return {
        success: (response as Record<string, unknown>)?.success || false,
        data: (response as Record<string, unknown>)?.data || {},
        message: (response as Record<string, unknown>)?.message || '',
        timestamp: (response as Record<string, unknown>)?.timestamp || new Date().toISOString()
      };
    } catch {
      // 실패해도 UI가 자연스럽게 동작하도록 안전한 형태 반환
      return {
        success: false,
        data: {},
        message: `Pattern data not available for ${districtName || '서울시 전체'}`
      };
    }
  }

  // RAG API 함수들
  async queryRAG(request: RAGQueryRequest): Promise<RAGQueryResponse> {
    try {
      const response = await fetch(`${RAG_API_URL}/api/v1/query/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: request.query,
          max_results: request.max_results || 10,
          similarity_threshold: request.similarity_threshold || 0.5,
          use_multi_query: request.use_multi_query || true,
          include_sources: request.include_sources || true,
          backend_data: request.backend_data || true,
          summary_only: request.summary_only || false,
        }),
      });

      if (!response.ok) {
        throw new Error(`RAG API error! status: ${response.status}`);
      }

      const data: RAGQueryResponse = await response.json();
      
      
      return data;
    } catch (error) {
      console.error('RAG API request failed:', error);
      throw error;
    }
  }

  // RAG 시스템 상태 확인
  async getRAGHealth(): Promise<{ status: string; message?: string }> {
    try {
      const response = await fetch(`${RAG_API_URL}/api/v1/query/examples`);
      
      if (!response.ok) {
        throw new Error(`RAG Health check failed! status: ${response.status}`);
      }

      return {
        status: 'healthy',
        message: 'RAG system is operational'
      };
    } catch (error) {
      console.error('RAG Health check failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  // RAG 예시 질문 가져오기
  async getRAGExamples(): Promise<{ examples: string[] }> {
    try {
      const response = await fetch(`${RAG_API_URL}/api/v1/query/examples`);
      
      if (!response.ok) {
        throw new Error(`RAG Examples API error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('RAG Examples API request failed:', error);
      return {
        examples: [
          "DRT 시스템이 무엇인가요?",
          "수요응답형 교통의 장점은 무엇인가요?",
          "교통 데이터 분석 방법론에 대해 설명해주세요"
        ]
      };
    }
  }
}

// 싱글톤 인스턴스 export
export const apiService = new ApiService();

// 유틸리티 함수들
export const utils = {
  // 날짜 포맷팅 (YYYY-MM-01 형식으로 변환)
  formatAnalysisMonth: (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}-01`;
  },

  // 시간 포맷팅 (24시간 -> 12시간 형식)
  formatHour: (hour: number): string => {
    if (hour === 0) return "12 AM";
    if (hour === 12) return "12 PM";
    if (hour < 12) return `${hour} AM`;
    return `${hour - 12} PM`;
  },

  // 숫자 포맷팅 (천 단위 콤마)
  formatNumber: (num: number): string => {
    return num.toLocaleString();
  },

  // 비율 포맷팅 (소수점 1자리)
  formatRatio: (ratio: number): string => {
    return `${(ratio * 100).toFixed(1)}%`;
  },

  // 선택된 월을 API 형식으로 변환 ("7" -> "2025-07-01")
  // 데이터가 2025년 기준이므로 2025년으로 고정하되, 향후 확장 가능하도록 구조화
  formatSelectedMonth: (selectedMonth: string, year: number = 2025): string => {
    const month = String(selectedMonth).padStart(2, "0");
    return `${year}-${month}-01`;
  },

  // 서울시 25개 구 목록
  seoulDistricts: [
    "강남구",
    "강동구",
    "강북구",
    "강서구",
    "관악구",
    "광진구",
    "구로구",
    "금천구",
    "노원구",
    "도봉구",
    "동대문구",
    "동작구",
    "마포구",
    "서대문구",
    "서초구",
    "성동구",
    "성북구",
    "송파구",
    "양천구",
    "영등포구",
    "용산구",
    "은평구",
    "종로구",
    "중구",
    "중랑구",
  ],

  // 중복된 정류장명에만 ID를 붙이는 함수
  getStationDisplayNames: <T extends { station_name: string; station_id: string }>(
    stations: T[]
  ): Map<string, string> => {
    const nameCount = new Map<string, number>();
    const stationIdsByName = new Map<string, string[]>();
    
    // 정류장 이름별로 카운트 및 ID 수집
    stations.forEach(station => {
      const count = nameCount.get(station.station_name) || 0;
      nameCount.set(station.station_name, count + 1);
      
      const ids = stationIdsByName.get(station.station_name) || [];
      ids.push(station.station_id);
      stationIdsByName.set(station.station_name, ids);
    });
    
    // 표시할 이름 생성
    const displayNames = new Map<string, string>();
    stations.forEach(station => {
      if (nameCount.get(station.station_name)! > 1) {
        // 중복된 이름인 경우 ID의 마지막 6자리 추가
        const shortId = station.station_id.slice(-6);
        displayNames.set(station.station_id, `${station.station_name} (${shortId})`);
      } else {
        // 유일한 이름인 경우 그대로 사용
        displayNames.set(station.station_id, station.station_name);
      }
    });
    
    return displayNames;
  },
};
