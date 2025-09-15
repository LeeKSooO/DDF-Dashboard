/**
 * OD Analysis API Client
 * 모든 OD 분석 API 엔드포인트를 처리하는 클라이언트
 */

import { API_BASE_URL } from './constants';

// ===== 공통 유틸: analysis_month 정규화 (강화된 버전) =====
function normalizeAnalysisMonth(input?: string | number | Date): string {
  // 0) Date 인스턴스
  if (input instanceof Date) return input.toISOString().slice(0, 10);

  const sRaw = (input ?? '').toString().trim();

  // 1) 이미 YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(sRaw)) return sRaw;

  // 2) 문자열 맨 앞에서 YYYY-MM만 뽑아내 복구 (이상치 보호)
  //    예: "2025-122000157-01" -> (2025, 12) -> "2025-12-01"
  const head = sRaw.match(/^(\d{4})-(\d{1,2})/);
  if (head) {
    let year = Number(head[1]);
    let month = Number(head[2]);
    if (!Number.isFinite(year) || year < 1970 || year > 2100) year = new Date().getFullYear();
    // 월 범위 보정 (1~12), 0이나 13이상도 안전하게 보정
    if (!Number.isFinite(month) || month < 1) month = 1;
    if (month > 12) month = ((month - 1) % 12) + 1;
    return `${year}-${String(month).padStart(2, '0')}-01`;
  }

  // 3) YYYY-MM (정상)
  if (/^\d{4}-\d{2}$/.test(sRaw)) return `${sRaw}-01`;

  // 4) 숫자만 들어온 경우: '7' -> 올해-07-01
  if (/^[0-9]+$/.test(sRaw)) {
    const monthNum = Number(sRaw);
    const year = new Date().getFullYear();
    const safeMonth = ((monthNum - 1) % 12 + 12) % 12 + 1; // 1~12로 보정
    return `${year}-${String(safeMonth).padStart(2, '0')}-01`;
  }

  // 5) Date 파싱 시도
  const d = new Date(sRaw);
  if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);

  // 6) 최종 fallback: 오늘
  return new Date().toISOString().slice(0, 10);
}

// 공통 타입 정의
export interface ODPair {
  from_station_id: string;
  from_station_name: string;
  from_station_num: string;
  to_station_id: string;
  to_station_name: string;
  to_station_num: string;
  from_district: string;
  to_district: string;
  distance_km: number;
  // 좌표 정보 (백엔드에서 추가됨)
  from_coordinates: {
    x: number;
    y: number;
  };
  to_coordinates: {
    x: number;
    y: number;
  };
}

export interface Station {
  station_id: string;
  station_name: string;
  station_num: string;
  district_name: string;
  coordinates: {
    x: number;
    y: number;
  };
}

// 좌표가 옵셔널인 기존 ODPair 타입 (하위 호환성)
export interface ODPairLegacy {
  from_station_id: string;
  from_station_name: string;
  from_station_num: string;
  to_station_id: string;
  to_station_name: string;
  to_station_num: string;
  from_district: string;
  to_district: string;
  distance_km: number;
  // 좌표 정보는 옵셔널 (기존 API 호환)
  from_coordinates?: {
    x: number;
    y: number;
  };
  to_coordinates?: {
    x: number;
    y: number;
  };
}

// P1/P2/P3 우선순위 API 응답 타입
export interface HighPriorityTransferData {
  od_pair: ODPairLegacy;
  daily_demand: number;
  transfer_required: boolean;
  priority_category: string;
}

export interface HighDemandDirectRouteData {
  od_pair: ODPairLegacy;
  daily_demand: number;
  transfer_required: boolean;
  avg_dispatch_interval?: number;
  priority_category: string;
}

export interface LowDemandLongDistanceData {
  od_pair: ODPairLegacy;
  daily_demand: number;
  demand_per_km: number;
  service_recommendation: string;
}

// 시간대별 출발지 분석 타입
export interface DestinationStation {
  station_id: string;
  station_name: string;
  station_num: string;
  district_name: string;
  coordinates: {
    x: number;
    y: number;
  };
  demand: number;
  rank: number;
}

export interface TimeBasedOriginAnalysis {
  from_station: {
    station_id: string;
    station_name: string;
    station_num: string;
    district_name: string;
    coordinates: {
      x: number;
      y: number;
    };
  };
  destination_count: number;
  time_period_demand: number;
  avg_distance_km: number;
  to_stations: DestinationStation[];
  drt_potential: string;
  service_recommendation: string;
}

export interface TimeBasedOriginAnalysisResponse {
  time_period: string;
  time_period_name: string;
  analysis_month: string;
  total_origins: number;
  total_demand: number;
  avg_destinations_per_origin: number;
  origins: TimeBasedOriginAnalysis[];
}

// 수요-공급 미스매치 분석 타입
export interface DemandSupplyMismatchData {
  od_pair: ODPair;
  monthly_total_passengers: number;
  daily_avg_passengers: number;
  distance_km: number;
  service_quality_score: number;
  avg_dispatch_interval_min: number;
  route_diversity_index: number;
  transfer_penalty: number;
  demand_service_ratio: number;
}

// OD Pair 시간대별 상세 분석 타입 - 좌표 옵셔널 허용
export interface ODPairHourlyAnalysis {
  od_pair: ODPairLegacy;  // ✅ 좌표 옵셔널 허용
  daily_avg_passengers: number;
  hourly_passengers: { [hour: string]: number };
  time_summary: {
    peak_hour: number;
    peak_passengers: number;
    morning_peak_pct: number;
    evening_peak_pct: number;
    daytime_pct: number;
    night_pct: number;
    pattern_type: string;
  };
}

// API 클라이언트 클래스
export class ODAnalysisAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // 1. 우선순위별 구간 분석 (P1, P2, P3)
  async getDRTPrioritySegments(
    priorityLevel: 'p1' | 'p2' | 'p3',
    analysisMonth: string | number | Date = '2025-07-01',
    topN: number = 20
  ): Promise<HighPriorityTransferData[] | HighDemandDirectRouteData[] | LowDemandLongDistanceData[]> {
    const params = new URLSearchParams({
      analysis_month: normalizeAnalysisMonth(analysisMonth),
      top_n: String(topN)
    });

    const response = await fetch(
      `${this.baseUrl}/od/priority/${priorityLevel}?${params}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch ${priorityLevel} priority data: ${response.statusText}`);
    }

    const data = await response.json();

    // (임시) 백엔드가 문자열 배열을 돌려주는 케이스 처리
    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'string') {
      return data
        .map((item: string) => {
          try {
            const odPairMatch = item.match(/od_pair=ODPairInfoSchema\((.*?)\)/);
            const dailyDemandMatch = item.match(/daily_demand=(\d+)/);
            const transferMatch = item.match(/transfer_required=(True|False)/);
            const priorityMatch = item.match(/priority_category='([^']+)'/);
            if (!odPairMatch || !dailyDemandMatch) throw new Error('Invalid response format');

            const odPairStr = odPairMatch[1];
            const fromStationIdMatch = odPairStr.match(/from_station_id='([^']+)'/);
            const fromStationNameMatch = odPairStr.match(/from_station_name='([^']+)'/);
            const fromStationNumMatch = odPairStr.match(/from_station_num='([^']+)'/);
            const toStationIdMatch = odPairStr.match(/to_station_id='([^']+)'/);
            const toStationNameMatch = odPairStr.match(/to_station_name='([^']+)'/);
            const toStationNumMatch = odPairStr.match(/to_station_num='([^']+)'/);
            const fromDistrictMatch = odPairStr.match(/from_district='([^']+)'/);
            const toDistrictMatch = odPairStr.match(/to_district='([^']+)'/);
            const distanceMatch = odPairStr.match(/distance_km=([0-9.]+)/);
            const fromCoordXMatch = odPairStr.match(/from_coordinates_x=([0-9.-]+)/);
            const fromCoordYMatch = odPairStr.match(/from_coordinates_y=([0-9.-]+)/);
            const toCoordXMatch = odPairStr.match(/to_coordinates_x=([0-9.-]+)/);
            const toCoordYMatch = odPairStr.match(/to_coordinates_y=([0-9.-]+)/);

            return {
              od_pair: {
                from_station_id: fromStationIdMatch?.[1] || '',
                from_station_name: fromStationNameMatch?.[1] || '',
                from_station_num: fromStationNumMatch?.[1] || '',
                to_station_id: toStationIdMatch?.[1] || '',
                to_station_name: toStationNameMatch?.[1] || '',
                to_station_num: toStationNumMatch?.[1] || '',
                from_district: fromDistrictMatch?.[1] || '',
                to_district: toDistrictMatch?.[1] || '',
                distance_km: parseFloat(distanceMatch?.[1] || '0'),
                from_coordinates:
                  fromCoordXMatch && fromCoordYMatch
                    ? { x: parseFloat(fromCoordXMatch[1]), y: parseFloat(fromCoordYMatch[1]) }
                    : undefined,
                to_coordinates:
                  toCoordXMatch && toCoordYMatch
                    ? { x: parseFloat(toCoordXMatch[1]), y: parseFloat(toCoordYMatch[1]) }
                    : undefined
              },
              daily_demand: parseInt(dailyDemandMatch[1]),
              transfer_required: transferMatch?.[1] === 'True',
              priority_category: priorityMatch?.[1] || ''
            };
          } catch (e) {
            console.error('Failed to parse OD data item:', item, e);
            return null;
          }
        })
        .filter((x): x is NonNullable<typeof x> => x !== null);
    }

    return data;
  }

  // 2. 시간대별 출발지 분석
  async getTimeBasedOriginAnalysis(
    timePeriod: 'morning_peak' | 'evening_peak' | 'night' | 'daytime',
    analysisMonth: string | number | Date = '2025-07-01',
    topN: number = 20
  ): Promise<TimeBasedOriginAnalysisResponse> {
    const params = new URLSearchParams({
      analysis_month: normalizeAnalysisMonth(analysisMonth),
      top_n: String(topN)
    });

    try {
      const response = await fetch(
        `${this.baseUrl}/od/time-based-origin/${timePeriod}?${params}`
      );

      if (!response.ok) {
        console.error(`API returned ${response.status}: ${response.statusText}`);
        throw new Error(`Failed to fetch time-based origin analysis: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('🔌 Time-based origin API response:', data);
      return data;
    } catch (error) {
      console.error('❌ Time-based origin API call failed:', error);
      // 실패 시 빈 셰이프 반환 (UI는 fallback 로직/샘플로 보완)
      return {
        time_period: timePeriod,
        time_period_name: this.getTimePeriodName(timePeriod),
        analysis_month: normalizeAnalysisMonth(analysisMonth),
        total_origins: 0,
        total_demand: 0,
        avg_destinations_per_origin: 0,
        origins: []
      };
    }
  }

  private getTimePeriodName(timePeriod: string): string {
    switch (timePeriod) {
      case 'morning_peak':
        return '출근시간 (07-09시)';
      case 'evening_peak':
        return '퇴근시간 (17-19시)';
      case 'daytime':
        return '주간시간 (10-16시)';
      case 'night':
        return '심야시간 (22-05시)';
      default:
        return timePeriod;
    }
  }

  // 3. 수요-공급 미스매치 분석 (단일 표준 형식으로 요청)
  async getDemandSupplyMismatchAnalysis(
    analysisMonth: string | number | Date = '2025-07-01',
    minPassengers: number = 10,
    topN: number = 50
  ): Promise<DemandSupplyMismatchData[]> {
    const params = new URLSearchParams({
      analysis_month: normalizeAnalysisMonth(analysisMonth),
      min_passengers: String(minPassengers),
      top_n: String(topN)
    });

    const response = await fetch(
      `${this.baseUrl}/od/mismatch-analysis?${params}`
    );

    if (!response.ok) {
      // 여기서 422가 나면 거의 100% 날짜 형식 문제였음 -> 정규화로 예방됨
      throw new Error(`Failed to fetch mismatch analysis: ${response.status} ${response.statusText}`);
    }

    const rawData = await response.json();

    // 백엔드 스키마 다양성에 대한 안전 변환
    return (rawData || []).map((item: any) => {
      const service_quality_score =
        item.service_quality_score ?? Math.max(20, 100 - ((item.drt_priority_score ?? 0) * 8));
      const demand_service_ratio =
        item.demand_service_ratio ?? (item.adjusted_drt_priority_score ?? 0) / 2;
      const transfer_penalty = item.transfer_penalty ?? (item.ever_transfer_required ? 1.5 : 0);

      return {
        od_pair: {
          from_station_id: item.from_station_id ?? item.od_pair?.from_station_id,
          from_station_name: item.from_station_name ?? item.od_pair?.from_station_name,
          from_station_num: item.from_station_num ?? item.od_pair?.from_station_num,
          to_station_id: item.to_station_id ?? item.od_pair?.to_station_id,
          to_station_name: item.to_station_name ?? item.od_pair?.to_station_name,
          to_station_num: item.to_station_num ?? item.od_pair?.to_station_num,
          from_district: item.from_district_name ?? item.od_pair?.from_district,
          to_district: item.to_district_name ?? item.od_pair?.to_district,
          distance_km: item.avg_distance_km ?? item.distance_km ?? 0,
          from_coordinates: {
            x: item.from_coordinates_x ?? item.od_pair?.from_coordinates?.x ?? 127.0276,
            y: item.from_coordinates_y ?? item.od_pair?.from_coordinates?.y ?? 37.4979
          },
          to_coordinates: {
            x: item.to_coordinates_x ?? item.od_pair?.to_coordinates?.x ?? 127.0276,
            y: item.to_coordinates_y ?? item.od_pair?.to_coordinates?.y ?? 37.4979
          }
        },
        monthly_total_passengers: item.monthly_total_passengers ?? 0,
        daily_avg_passengers: item.daily_avg_passengers ?? 0,
        distance_km: item.avg_distance_km ?? item.distance_km ?? 0,
        service_quality_score,
        avg_dispatch_interval_min: item.avg_dispatch_interval ?? 0,
        route_diversity_index: item.route_diversity_index ?? 1,
        transfer_penalty,
        demand_service_ratio
      } as DemandSupplyMismatchData;
    });
  }

  // 4. OD Pair 시간대별 상세 분석
  async getODPairHourlyAnalysis(
    fromStationId: string,
    toStationId: string,
    analysisMonth: string | number | Date = '2025-07-01'
  ): Promise<ODPairHourlyAnalysis> {
    // ✅ 입력값 사전 검증
    if (!fromStationId || !toStationId) {
      throw new Error(`from/to station id missing: from="${fromStationId}", to="${toStationId}"`);
    }

    const monthNorm = normalizeAnalysisMonth(analysisMonth);

    // ✅ 강력 가드: 최종적으로 YYYY-MM-DD 아니면 에러 (원인 추적용)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(monthNorm)) {
      console.error('❌ normalizeAnalysisMonth produced invalid value:', {
        analysisMonth,
        monthNorm
      });
      throw new Error(`Invalid analysis_month after normalization: "${monthNorm}"`);
    }

    const params = new URLSearchParams();
    params.set('analysis_month', monthNorm);
    params.set('from_station_id', String(fromStationId).trim());
    params.set('to_station_id', String(toStationId).trim());

    const url = `${this.baseUrl}/od/hourly-analysis?${params.toString()}`;

    // ✅ 최종 URL/파라미터 디버그
    console.log('➡️ GET hourly-analysis', {
      url,
      analysisMonthRaw: analysisMonth,
      analysisMonthNorm: monthNorm,
      fromStationId,
      toStationId
    });

    const response = await fetch(url, { 
      headers: { 
        accept: 'application/json' 
      } 
    });

    if (!response.ok) {
      // ✅ 서버가 준 422 상세를 콘솔에 찍어 원인 확인
      const body = await response.text();
      console.error(`❌ API returned ${response.status}: ${response.statusText} • body=${body}`);
      throw new Error(`Failed to fetch hourly analysis: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log('🔌 Hourly analysis API response:', data);
    return data;
  }

  // 5. 통합 분석 - 모든 우선순위 데이터를 병렬로 로드
  async getAllPriorityData(
    analysisMonth: string | number | Date = '2025-07-01',
    topN: number = 20
  ): Promise<{
    p1: HighPriorityTransferData[];
    p2: HighDemandDirectRouteData[];
    p3: LowDemandLongDistanceData[];
  }> {
    try {
      const [p1Data, p2Data, p3Data] = await Promise.all([
        this.getDRTPrioritySegments('p1', analysisMonth, topN) as Promise<HighPriorityTransferData[]>,
        this.getDRTPrioritySegments('p2', analysisMonth, topN) as Promise<HighDemandDirectRouteData[]>,
        this.getDRTPrioritySegments('p3', analysisMonth, topN) as Promise<LowDemandLongDistanceData[]>
      ]);

      return { p1: p1Data, p2: p2Data, p3: p3Data };
    } catch (error) {
      console.error('Failed to load all priority data:', error);
      return { p1: [], p2: [], p3: [] };
    }
  }

  // 6. 모든 시간대별 분석 데이터를 병렬로 로드
  async getAllTimeBasedAnalysis(
    analysisMonth: string | number | Date = '2025-07-01',
    topN: number = 10
  ): Promise<{
    morning_peak: TimeBasedOriginAnalysisResponse;
    evening_peak: TimeBasedOriginAnalysisResponse;
    daytime: TimeBasedOriginAnalysisResponse;
    night: TimeBasedOriginAnalysisResponse;
  }> {
    const month = normalizeAnalysisMonth(analysisMonth);
    try {
      const [morningData, eveningData, daytimeData, nightData] = await Promise.all([
        this.getTimeBasedOriginAnalysis('morning_peak', month, topN),
        this.getTimeBasedOriginAnalysis('evening_peak', month, topN),
        this.getTimeBasedOriginAnalysis('daytime', month, topN),
        this.getTimeBasedOriginAnalysis('night', month, topN)
      ]);

      return {
        morning_peak: morningData,
        evening_peak: eveningData,
        daytime: daytimeData,
        night: nightData
      };
    } catch (error) {
      console.error('Failed to load all time-based analysis:', error);
      throw error;
    }
  }

  // 7. 헬스체크 및 통계
  async getAPIHealth(): Promise<{ status: string; message: string }> {
    try {
      // 표준화된 날짜 사용
      const params = new URLSearchParams({
        analysis_month: normalizeAnalysisMonth('2025-07-01'),
        top_n: '1'
      });
      const response = await fetch(`${this.baseUrl}/od/priority/p1?${params}`);

      if (response.ok) return { status: 'healthy', message: 'OD API is working properly' };
      return { status: 'unhealthy', message: `API returned ${response.status}` };
    } catch (error) {
      return { status: 'error', message: `API connection failed: ${error}` };
    }
  }
}

// 기본 인스턴스 생성 및 export
export const odAPI = new ODAnalysisAPI();

// 유틸리티 함수들
export const ODAnalysisUtils = {
  // 우선순위 카테고리별 색상 반환
  getColorByPriority: (category: string): [number, number, number, number] => {
    if (category.includes('P1_고수요_환승구간')) return [220, 38, 38, 220]; // 빨강
    if (category.includes('P1_저수요_환승구간')) return [249, 115, 22, 200]; // 주황
    if (category.includes('P2')) return [59, 130, 246, 180]; // 파랑
    if (category.includes('P3')) return [147, 51, 234, 160]; // 보라
    return [156, 163, 175, 140]; // 회색
  },

  // 우선순위별 표시 텍스트
  getPriorityLabel: (category: string): string => {
    if (category.includes('P1_고수요_환승구간')) return '🚨 P1 고수요 환승';
    if (category.includes('P1_저수요_환승구간')) return '⚠️ P1 저수요 환승';
    if (category.includes('P2')) return '🔄 P2 직행부족';
    if (category.includes('P3')) return '📏 P3 장거리';
    return '기타';
  },

  // 수요 레벨별 색상 (텍스트용)
  getDemandLevelColor: (demand: number): string => {
    if (demand >= 1000) return 'text-red-600';
    if (demand >= 500) return 'text-orange-600';
    if (demand >= 100) return 'text-blue-600';
    if (demand >= 50) return 'text-green-600';
    return 'text-gray-600';
  },

  // DRT 잠재력별 색상
  getDRTPotentialColor: (potential: string): string => {
    if (potential === '높음') return 'text-red-600';
    if (potential === '보통') return 'text-orange-600';
    return 'text-green-600';
  },

  // 시간대 패턴별 아이콘
  getPatternIcon: (patternType: string): string => {
    if (patternType.includes('출근시간')) return '🌅';
    if (patternType.includes('퇴근시간')) return '🌆';
    if (patternType.includes('주간')) return '☀️';
    if (patternType.includes('균등')) return '📊';
    return '⏰';
  },

  // 좌표 변환 (API 응답의 coordinates를 lat, lng로 변환)
  convertCoordinates: (coordinates: { x: number; y: number }): { lat: number; lng: number } => {
    return { lat: coordinates.y, lng: coordinates.x };
  },

  // 정류장 데이터를 Station 형식으로 변환
  convertToStationData: (odData: (HighPriorityTransferData | HighDemandDirectRouteData | LowDemandLongDistanceData)[]): Station[] => {
    const stationMap = new Map<string, Station>();

    odData.forEach(od => {
      if (!stationMap.has(od.od_pair.from_station_id)) {
        stationMap.set(od.od_pair.from_station_id, {
          station_id: od.od_pair.from_station_id,
          station_name: od.od_pair.from_station_name,
          station_num: od.od_pair.from_station_num,
          district_name: od.od_pair.from_district,
          coordinates: { x: 127.0276, y: 37.4979 } // 기본값 (실좌표 API 필요)
        });
      }
      if (!stationMap.has(od.od_pair.to_station_id)) {
        stationMap.set(od.od_pair.to_station_id, {
          station_id: od.od_pair.to_station_id,
          station_name: od.od_pair.to_station_name,
          station_num: od.od_pair.to_station_num,
          district_name: od.od_pair.to_district,
          coordinates: { x: 127.0276, y: 37.4979 } // 기본값
        });
      }
    });

    return Array.from(stationMap.values());
  }
};