// 컴포넌트 관련 타입 정의

// 공통 컴포넌트 props
export interface BaseContentProps {
  selectedMonth: string;
  selectedRegion: string;
}

export interface DashboardContentProps extends BaseContentProps {
  onRegionChange?: (region: string) => void;
  onMonthChange?: (month: string) => void;
}

// DRT 관련 컴포넌트 props
export interface DRTAnalysisContentProps extends BaseContentProps {
  selectedModel: string;
  setSelectedModel: (model: string) => void;
}

export interface DRTScoreContentProps extends BaseContentProps {
  selectedModel: string;
}

// Map 컴포넌트 props
export interface MapProps {
  onDistrictClick?: (districtName: string, districtCode?: string) => void;
  selectedDistrict?: string;
  className?: string;
}

export interface SeoulMapProps extends MapProps {
  trafficData?: Array<{
    district_name: string;
    total_traffic: number;
  }>;
}

export interface HeatmapProps extends MapProps {
  stationsData?: Array<{
    station_id: string;
    station_name: string;
    total_traffic: number;
    coordinate: {
      latitude: number;
      longitude: number;
    };
  }>;
  mode?: 'district' | 'station';
}

export interface DRTScoreMapProps extends MapProps {
  selectedModel: string;
  drtData?: {
    stations: Array<{
      station_id: string;
      station_name: string;
      drt_score: number;
      coordinate: {
        lat: number;
        lng: number;
      };
      peak_hour: number;
    }>;
  };
}

// Chart 컴포넌트 props
export interface TrafficChartProps {
  className?: string;
  selectedMonth?: string;
}

// 분석 패널 props
export interface DistrictAnalysisPanelProps {
  selectedRegion: string;
  selectedMonth: string;
  onClose: () => void;
}

// UI 상태 관련 타입
export interface LoadingState {
  isLoading: boolean;
  error?: string | null;
}

export interface SelectOption {
  value: string;
  label: string;
}

// 모델 타입 매핑
export type ModelType = "교통취약지" | "출퇴근" | "관광";
export type ApiModelType = "vulnerable" | "commute" | "tourist";

export const modelTypeMapping: Record<ModelType, ApiModelType> = {
  "교통취약지": "vulnerable",
  "출퇴근": "commute", 
  "관광": "tourist"
};

// 지역 목록 타입
export type RegionType = "전체" | "강남구" | "강동구" | "강북구" | "강서구" | "관악구" | "광진구" | "구로구" | "금천구" | "노원구" | "도봉구" | "동대문구" | "동작구" | "마포구" | "서대문구" | "서초구" | "성동구" | "성북구" | "송파구" | "양천구" | "영등포구" | "용산구" | "은평구" | "종로구" | "중구" | "중랑구";

// 월 목록 타입  
export type MonthType = "2024-01" | "2024-02" | "2024-03" | "2024-04" | "2024-05" | "2024-06" | "2024-07" | "2024-08" | "2024-09" | "2024-10" | "2024-11" | "2024-12";