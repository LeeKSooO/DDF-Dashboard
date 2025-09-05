import { useState, useEffect, useCallback, useMemo } from "react";
import { apiService, utils } from "@/lib/api";

interface TrafficAnalysisData {
  weekendData: any;
  nightData: any;
  rushHourData: any;
  lunchTimeData: any;
  areaTypeData: any;
  underutilizedData: any;
  integrationData: any;
}

interface UseTrafficAnalysisDataReturn {
  data: TrafficAnalysisData;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// 간단한 메모리 캐시
const cache = new Map<string, { data: any; timestamp: number }>();
const CACHE_DURATION = 5 * 60 * 1000; // 5분

export const useTrafficAnalysisData = (
  selectedMonth: string,
  selectedRegion: string
): UseTrafficAnalysisDataReturn => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TrafficAnalysisData>({
    weekendData: null,
    nightData: null,
    rushHourData: null,
    lunchTimeData: null,
    areaTypeData: null,
    underutilizedData: null,
    integrationData: null,
  });

  // 캐시 키 생성
  const cacheKey = useMemo(() => {
    return `${selectedMonth}-${selectedRegion}`;
  }, [selectedMonth, selectedRegion]);

  // 캐시에서 데이터 확인
  const getCachedData = useCallback((key: string) => {
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
      return cached.data;
    }
    return null;
  }, []);

  // 캐시에 데이터 저장
  const setCachedData = useCallback((key: string, data: any) => {
    cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }, []);

  const loadTrafficAnalysisData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 캐시 확인
      const cachedData = getCachedData(cacheKey);
      if (cachedData) {
        setData(cachedData);
        setLoading(false);
        return;
      }

      console.log("🚌 Loading integrated traffic analysis data for:", {
        selectedMonth,
        selectedRegion,
      });

      // 분석할 구 목록 결정
      const districtsToAnalyze =
        selectedRegion === "전체"
          ? ["강남구", "서초구", "송파구", "영등포구", "마포구"]
          : [selectedRegion];

      const targetDistrict = districtsToAnalyze[0];
      const analysisMonth = utils.formatSelectedMonth(selectedMonth);

      // 통합 API 호출
      const integrationResult = await apiService.getIntegratedAnomalyAnalysis(
        targetDistrict,
        analysisMonth
      );

      if (integrationResult?.success && integrationResult?.data) {
        const apiData = integrationResult.data;
        
        const newData: TrafficAnalysisData = {
          weekendData: {
            success: true,
            data: apiData.weekend_dominant_stations || []
          },
          nightData: {
            success: true,
            data: apiData.night_demand_stations || []
          },
          rushHourData: {
            success: true,
            data: apiData.rush_hour_stations || {}
          },
          lunchTimeData: {
            success: true,
            data: apiData.lunch_time_stations || []
          },
          areaTypeData: {
            success: true,
            data: apiData.area_type_analysis || {}
          },
          underutilizedData: {
            success: true,
            data: apiData.underutilized_stations || []
          },
          integrationData: integrationResult,
        };

        setData(newData);
        setCachedData(cacheKey, newData);
      } else {
        throw new Error("Invalid response from integrated API");
      }
    } catch (err) {
      console.error("🚨 Integrated Traffic Analysis API error:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load integrated traffic analysis data"
      );
    } finally {
      setLoading(false);
    }
  }, [selectedMonth, selectedRegion, cacheKey, getCachedData, setCachedData]);

  useEffect(() => {
    loadTrafficAnalysisData();
  }, [loadTrafficAnalysisData]);

  return {
    data,
    loading,
    error,
    refetch: loadTrafficAnalysisData,
  };
};