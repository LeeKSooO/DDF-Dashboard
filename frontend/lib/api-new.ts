// 새로운 API 서비스 레이어
// DRT Dashboard API 통신을 위한 클린 버전

import { API_BASE_URL } from './constants';
import type {
  TrafficResponse,
  HeatmapResponse,
  DRTScoreResponse,
  DRTStationDetailResponse,
  TrafficParams,
  HeatmapParams,
  DRTScoreParams,
  ApiResponse
} from '@/types/api';

class ApiService {
  private async fetchWithErrorHandling<T>(url: string): Promise<T> {
    try {
      console.log(`🔄 API Request: ${url}`);
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log(`✅ API Response:`, data);
      return data;
    } catch (error) {
      console.error("❌ API request failed:", error);
      throw error;
    }
  }

  // 교통량 패턴 데이터 조회
  async getTrafficPatterns(params: TrafficParams): Promise<TrafficResponse> {
    const searchParams = new URLSearchParams({
      analysis_month: params.month,
      region_type: params.region === "전체" ? "seoul" : "district",
    });

    if (params.region !== "전체") {
      searchParams.append("district_name", params.region);
    }

    const url = `${API_BASE_URL}/traffic/hourly?${searchParams.toString()}`;
    return this.fetchWithErrorHandling<TrafficResponse>(url);
  }

  // 히트맵 데이터 조회
  async getHeatmapData(params: HeatmapParams): Promise<HeatmapResponse> {
    const searchParams = new URLSearchParams({
      analysis_month: params.month,
      include_station_details: "true",
    });

    let url: string;
    if (params.region === "전체") {
      url = `${API_BASE_URL}/heatmap/seoul?${searchParams.toString()}`;
    } else {
      searchParams.append("district_name", params.region);
      url = `${API_BASE_URL}/heatmap/district?${searchParams.toString()}`;
    }

    return this.fetchWithErrorHandling<HeatmapResponse>(url);
  }

  // DRT 점수 데이터 조회
  async getDRTScores(params: DRTScoreParams): Promise<DRTScoreResponse> {
    const url = `${API_BASE_URL}/drt-score/${params.region}/${params.model_type}?date=${params.date}`;
    return this.fetchWithErrorHandling<DRTScoreResponse>(url);
  }

  // DRT 정류장 상세 정보 조회
  async getDRTStationDetail(
    region: string,
    stationId: string,
    modelType: "commute" | "tourist" | "vulnerable",
    date: string = "2025-07-01"
  ): Promise<DRTStationDetailResponse> {
    const url = `${API_BASE_URL}/drt-score/${region}/${stationId}/detail?model_type=${modelType}&date=${date}`;
    return this.fetchWithErrorHandling<DRTStationDetailResponse>(url);
  }
}

// 싱글톤 인스턴스 export
export const newApiService = new ApiService();

// 유틸리티 함수들
export const utils = {
  // 구 이름 정규화 (API 호출용)
  normalizeDistrictName: (districtName: string): string => {
    return districtName.replace(/구$/, '') + '구';
  },

  // 월 형식 변환 (YYYY-MM)
  formatMonth: (month: string): string => {
    if (month.includes('-')) return month;
    return `2024-${month.padStart(2, '0')}`;
  },

  // DRT 점수 등급 계산
  getDRTGrade: (score: number): string => {
    if (score >= 80) return 'S';
    if (score >= 60) return 'A';
    if (score >= 40) return 'B';
    if (score >= 20) return 'C';
    return 'D';
  },

  // 숫자 포맷팅 (천 단위 콤마)
  formatNumber: (num: number): string => {
    return new Intl.NumberFormat('ko-KR').format(num);
  },

  // 시간 포맷팅
  formatHour: (hour: number): string => {
    return `${hour.toString().padStart(2, '0')}:00`;
  }
};