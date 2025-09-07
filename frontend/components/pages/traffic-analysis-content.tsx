/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertTriangle,
  TrendingDown,
  Activity,
  Zap,
  Users,
  Clock,
  MapPin,
  HelpCircle,
} from "lucide-react";
import { apiService, utils } from "@/lib/api";

// Month names in Korean
const monthNames = [
  "1월",
  "2월",
  "3월",
  "4월",
  "5월",
  "6월",
  "7월",
  "8월",
  "9월",
  "10월",
  "11월",
  "12월",
];

interface TrafficAnalysisContentProps {
  selectedMonth: string;
  selectedRegion: string;
}

export function TrafficAnalysisContent({
  selectedMonth,
  selectedRegion,
}: TrafficAnalysisContentProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // API 데이터 상태들
  const [weekendData, setWeekendData] = useState<any>(null);
  const [nightData, setNightData] = useState<any>(null);
  const [rushHourData, setRushHourData] = useState<any>(null);
  const [lunchTimeData, setLunchTimeData] = useState<any>(null);
  const [areaTypeData, setAreaTypeData] = useState<any>(null);
  const [underutilizedData, setUnderutilizedData] = useState<any>(null);


  // 애니메이션 상태
  const [animatedNumbers, setAnimatedNumbers] = useState<
    Record<string, number>
  >({});
  const animatedTargetsRef = useRef<Record<string, number>>({});
  
  // 막대그래프 애니메이션 상태
  const [progressBarsAnimated, setProgressBarsAnimated] = useState(false);

  // 중복된 정류장 이름을 감지하고 구분 표시하는 함수
  const checkDuplicateStationNames = (stations: any[]) => {
    const nameCount: Record<string, number> = {};
    stations.forEach((station) => {
      const stationName = station.station?.station_name || station.station_name;
      nameCount[stationName] = (nameCount[stationName] || 0) + 1;
    });
    return nameCount;
  };

  // 정류장 이름 표시 함수 (전체 ID 표시 버전)
  const formatStationName = (station: any, allStations: any[]) => {
    const stationName = station.station?.station_name || station.station_name;
    const stationId = station.station?.station_id || station.station_id;
    const duplicateNames = checkDuplicateStationNames(allStations);
    const isDuplicate = duplicateNames[stationName] > 1;

    if (isDuplicate) {
      // 전체 ID 표시
      const fullId = stationId?.toString() || "N/A";
      return (
        <>
          {stationName}{" "}
          <span className="text-xs text-gray-500">({fullId})</span>
        </>
      );
    }

    return stationName;
  };

  // CSS 애니메이션 스타일 추가
  const animationStyles = `
    @keyframes slideInLeft {
      from {
        opacity: 0;
        transform: translateX(-20px);
      }
      to {
        opacity: 1;
        transform: translateX(0);
      }
    }
    
    @keyframes countUp {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    @keyframes progressBar {
      from {
        width: 0%;
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }
    
    .animate-slide-in {
      animation: slideInLeft 0.6s ease-out forwards;
    }
    
    .animate-count-up {
      animation: countUp 0.8s ease-out forwards;
    }
    
    .animate-progress {
      animation: progressBar 1.2s ease-out forwards;
    }
    
    .progress-bar-animate {
      width: 0%;
      transition: width 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      transition-delay: var(--delay, 0ms);
      will-change: width;
      transform: translateZ(0);
      backface-visibility: hidden;
      perspective: 1000px;
    }
    
    .scrollable-list {
      max-height: 400px;
      overflow-y: auto;
      scrollbar-width: thin;
      scrollbar-color: #cbd5e0 #f7fafc;
    }
    
    .scrollable-list::-webkit-scrollbar {
      width: 6px;
    }
    
    .scrollable-list::-webkit-scrollbar-track {
      background: #f7fafc;
      border-radius: 3px;
    }
    
    .scrollable-list::-webkit-scrollbar-thumb {
      background: #cbd5e0;
      border-radius: 3px;
    }
    
    .scrollable-list::-webkit-scrollbar-thumb:hover {
      background: #a0aec0;
    }
  `;

  // RAF ID 관리를 위한 ref
  const rafIdsRef = useRef<Set<number>>(new Set());

  // 막대그래프 렌더링 함수
  const renderProgressBar = (
    value: number, 
    maxValue: number, 
    colorClass: string, 
    index: number, 
    delay: number = 0
  ) => (
    <div className="w-full bg-gray-200 rounded-full h-1.5">
      <div
        className={`${colorClass} h-1.5 rounded-full progress-bar-animate`}
        style={{
          width: progressBarsAnimated ? `${Math.min(100, (value / maxValue) * 100)}%` : '0%',
          '--delay': `${index * 50 + delay}ms`,
        } as React.CSSProperties}
      ></div>
    </div>
  );

  // 글로벌 최대값 계산 함수
  const getGlobalMaxValues = () => {
    const residential = areaTypeData?.data?.residential_stations || [];
    const business = areaTypeData?.data?.business_stations || [];
    
    return {
      morningRide: Math.max(
        ...residential.map((s: any) => s.morning_ride || 0),
        ...business.map((s: any) => s.morning_ride || 0),
        1
      ),
      morningAlight: Math.max(
        ...residential.map((s: any) => s.morning_alight || 0),
        ...business.map((s: any) => s.morning_alight || 0),
        1
      ),
      eveningRide: Math.max(
        ...residential.map((s: any) => s.evening_ride || 0),
        ...business.map((s: any) => s.evening_ride || 0),
        1
      ),
      eveningAlight: Math.max(
        ...residential.map((s: any) => s.evening_alight || 0),
        ...business.map((s: any) => s.evening_alight || 0),
        1
      )
    };
  };

  // 동적 숫자 애니메이션 훅 (무한 루프 방지)
  const animateNumber = useCallback(
    (key: string, targetValue: number, duration: number = 1500) => {
      // 같은 key에 같은 목표값이면 재실행 방지
      if (animatedTargetsRef.current[key] === targetValue) return;
      animatedTargetsRef.current[key] = targetValue;

      const startValue = 0; // 항상 0에서 시작
      const startTime = performance.now();

      const easeOutCubic = (t: number): number => {
        return 1 - Math.pow(1 - t, 3);
      };

      const step = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(progress);
        const currentValue = Math.floor(
          startValue + (targetValue - startValue) * eased
        );

        setAnimatedNumbers((prev) =>
          prev[key] === currentValue ? prev : { ...prev, [key]: currentValue }
        );

        if (progress < 1) {
          const rafId = requestAnimationFrame(step);
          rafIdsRef.current.add(rafId);
        } else {
          // 마지막으로 정확히 맞춰줍
          setAnimatedNumbers((prev) =>
            prev[key] === targetValue ? prev : { ...prev, [key]: targetValue }
          );
        }
      };

      const rafId = requestAnimationFrame(step);
      rafIdsRef.current.add(rafId);
    },
    [] // 의존성 없음: 함수 참조가 안정적이라 useEffect 재실행 유발 안 함
  );

  // 애니메이션 트리거 - 한 번만 실행되도록 useRef로 관리
  const animationTriggered = useRef(false);

  useEffect(() => {
    if (!loading && !error && !animationTriggered.current) {
      animationTriggered.current = true; // 플래그 설정으로 중복 실행 방지

      // 데이터가 로드되면 애니메이션 시작
      const timeout = setTimeout(() => {
        // 각 섹션의 숫자들을 애니메이션으로 시작
        if (weekendData?.data) {
          weekendData.data.forEach((item: any, index: number) => {
            animateNumber(
              `weekend-${item.station.station_id}`,
              item.weekend_total_traffic || 0,
              1000 + index * 100
            );
          });
        }

        if (nightData?.data) {
          nightData.data.forEach((item: any, index: number) => {
            animateNumber(
              `night-${item.station.station_id}`,
              item.total_night_ride || 0,
              1000 + index * 100
            );
          });
        }

        if (rushHourData?.data?.morning_rush) {
          rushHourData.data.morning_rush.forEach((item: any, index: number) => {
            animateNumber(
              `morning-${item.station.station_id}`,
              item.total_morning_rush || 0,
              1000 + index * 100
            );
          });
        }

        if (rushHourData?.data?.evening_rush) {
          rushHourData.data.evening_rush.forEach((item: any, index: number) => {
            animateNumber(
              `evening-${item.station.station_id}`,
              item.total_evening_rush || 0,
              1000 + index * 100
            );
          });
        }

        if (lunchTimeData?.data) {
          lunchTimeData.data.forEach((item: any, index: number) => {
            animateNumber(
              `lunch-${item.station.station_id}`,
              item.total_lunch_alight || 0,
              1000 + index * 100
            );
          });
        }

        if (underutilizedData?.data) {
          underutilizedData.data.forEach((item: any, index: number) => {
            animateNumber(
              `underutil-${item.station.station_id}`,
              item.avg_daily_passengers || 0,
              1000 + index * 100
            );
          });
        }

        if (areaTypeData?.data?.residential_stations) {
          areaTypeData.data.residential_stations.forEach(
            (item: any, index: number) => {
              animateNumber(
                `residential-morning-${item.station.station_id}`,
                item.morning_ride || 0,
                1000 + index * 100
              );
              animateNumber(
                `residential-evening-${item.station.station_id}`,
                item.evening_alight || 0,
                1200 + index * 100
              );
            }
          );
        }

        if (areaTypeData?.data?.business_stations) {
          areaTypeData.data.business_stations.forEach(
            (item: any, index: number) => {
              animateNumber(
                `business-morning-${item.station.station_id}`,
                item.morning_alight || 0,
                1000 + index * 100
              );
              animateNumber(
                `business-evening-${item.station.station_id}`,
                item.evening_ride || 0,
                1200 + index * 100
              );
            }
          );
        }
        
      }, 300);
      
      return () => {
        clearTimeout(timeout);
        // 모든 RAF 정리
        rafIdsRef.current.forEach((rafId) => {
          cancelAnimationFrame(rafId);
        });
        rafIdsRef.current.clear();
      };
    }
  }, [
    loading,
    error,
    weekendData,
    nightData,
    rushHourData,
    lunchTimeData,
    underutilizedData,
    areaTypeData,
    animateNumber,
  ]);

  // 지역 특성 데이터가 로드되면 막대그래프 애니메이션 시작
  useEffect(() => {
    if (areaTypeData?.data && !loading && !error) {
      const timer = setTimeout(() => {
        setProgressBarsAnimated(true);
      }, 800); // 숫자 애니메이션 완료 후
      
      return () => clearTimeout(timer);
    }
  }, [areaTypeData, loading, error]);

  // 데이터 로드
  useEffect(() => {
    const loadTrafficAnalysisData = async () => {
      try {
        setLoading(true);
        setError(null);

        // 새로운 데이터 로드 시 애니메이션 플래그 리셋
        animationTriggered.current = false;
        animatedTargetsRef.current = {}; // 목표값 기록 초기화
        setAnimatedNumbers({}); // 애니메이션 숫자 상태 초기화
        setProgressBarsAnimated(false); // 막대그래프 애니메이션 리셋

        console.log("🚌 Loading integrated traffic analysis data for:", {
          selectedMonth,
          selectedRegion,
        });

        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        if (selectedRegion === "전체") {
          // 전체 서울 분석: 모든 구의 데이터를 병합
          const allDistricts = [
            "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", 
            "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구",
            "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구",
            "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
          ];

          // 모든 구의 데이터를 병렬로 가져와서 병합
          const allDistrictResults = await Promise.allSettled(
            allDistricts.map(district => 
              apiService.getIntegratedAnomalyAnalysis(district, analysisMonth)
            )
          );

          // 성공한 결과들만 필터링하고 데이터 병합
          const successfulResults: any[] = allDistrictResults
            .filter((result): result is PromiseFulfilledResult<any> => 
              result.status === 'fulfilled' && result.value?.success
            )
            .map(result => result.value.data);

          if (successfulResults.length > 0) {
            // 모든 구의 데이터를 패턴별로 병합
            const mergedData = {
              district_name: "서울시 전체",
              analysis_month: successfulResults[0].analysis_month,
              generated_at: new Date().toISOString(),
              weekend_dominant_stations: [] as any[],
              night_demand_stations: [] as any[],
              rush_hour_stations: { morning_rush: [] as any[], evening_rush: [] as any[] },
              lunch_time_stations: [] as any[],
              area_type_analysis: { residential_stations: [] as any[], business_stations: [] as any[] },
              underutilized_stations: [] as any[]
            };

            // 각 패턴별로 모든 구의 데이터를 합치고 상위 10개씩 선택
            successfulResults.forEach((districtData: any) => {
                mergedData.weekend_dominant_stations.push(...((districtData.weekend_dominant_stations as any[]) || []));
              mergedData.night_demand_stations.push(...((districtData.night_demand_stations as any[]) || []));
              mergedData.rush_hour_stations.morning_rush.push(...((districtData.rush_hour_stations?.morning_rush as any[]) || []));
              mergedData.rush_hour_stations.evening_rush.push(...((districtData.rush_hour_stations?.evening_rush as any[]) || []));
              mergedData.lunch_time_stations.push(...((districtData.lunch_time_stations as any[]) || []));
              mergedData.area_type_analysis.residential_stations.push(...((districtData.area_type_analysis?.residential_stations as any[]) || []));
              mergedData.area_type_analysis.business_stations.push(...((districtData.area_type_analysis?.business_stations as any[]) || []));
              mergedData.underutilized_stations.push(...((districtData.underutilized_stations as any[]) || []));
            });

            // 각 패턴별로 정렬하고 상위 10개만 선택
            mergedData.weekend_dominant_stations = (mergedData.weekend_dominant_stations as any[])
              .sort((a: any, b: any) => (b.weekend_total_traffic || 0) - (a.weekend_total_traffic || 0))
              .slice(0, 10);

            mergedData.night_demand_stations = (mergedData.night_demand_stations as any[])
              .sort((a: any, b: any) => (b.total_night_ride || 0) - (a.total_night_ride || 0))
              .slice(0, 10);

            mergedData.rush_hour_stations.morning_rush = (mergedData.rush_hour_stations.morning_rush as any[])
              .sort((a: any, b: any) => (b.total_morning_rush || 0) - (a.total_morning_rush || 0))
              .slice(0, 10);

            mergedData.rush_hour_stations.evening_rush = (mergedData.rush_hour_stations.evening_rush as any[])
              .sort((a: any, b: any) => (b.total_evening_rush || 0) - (a.total_evening_rush || 0))
              .slice(0, 10);

            mergedData.lunch_time_stations = (mergedData.lunch_time_stations as any[])
              .sort((a: any, b: any) => (b.total_lunch_alight || 0) - (a.total_lunch_alight || 0))
              .slice(0, 10);

            mergedData.area_type_analysis.residential_stations = (mergedData.area_type_analysis.residential_stations as any[])
              .sort((a: any, b: any) => (b.imbalance_ratio || 0) - (a.imbalance_ratio || 0))
              .slice(0, 10);

            mergedData.area_type_analysis.business_stations = (mergedData.area_type_analysis.business_stations as any[])
              .sort((a: any, b: any) => (b.imbalance_ratio || 0) - (a.imbalance_ratio || 0))
              .slice(0, 10);

            mergedData.underutilized_stations = (mergedData.underutilized_stations as any[])
              .sort((a: any, b: any) => (a.efficiency_score || Infinity) - (b.efficiency_score || Infinity))
              .slice(0, 10);

            // 병합된 데이터를 사용
            const integrationResult = { success: true, data: mergedData };
            processIntegrationResult(integrationResult);
          } else {
            throw new Error("모든 구의 데이터 로드에 실패했습니다.");
          }
        } else {
          // 개별 구 분석
          try {
            const integrationResult = await apiService.getIntegratedAnomalyAnalysis(
              selectedRegion,
              analysisMonth
            );
            processIntegrationResult(integrationResult);
          } catch (integrationError) {
            console.warn("🔄 통합 API 실패, 개별 패턴 API로 폴백 시도:", integrationError);
            
            // 통합 API 실패 시 개별 패턴 API들을 병렬로 호출
            const fallbackResults = await Promise.allSettled([
              apiService.getWeekendDominantStations(selectedRegion, analysisMonth, 10),
              apiService.getNightDemandStations(selectedRegion, analysisMonth, 10),
              apiService.getRushHourAnalysis(selectedRegion, analysisMonth),
              apiService.getLunchTimeStations(selectedRegion, analysisMonth, 10),
              apiService.getAreaTypeAnalysis(selectedRegion, analysisMonth),
              apiService.getUnderutilizedStations(selectedRegion, analysisMonth, 10)
            ]);

            // 성공한 개별 API 결과들을 통합 형태로 변환
            const [weekendResult, nightResult, rushHourResult, lunchTimeResult, areaTypeResult, underutilizedResult] = fallbackResults;

            const fallbackData = {
              district_name: selectedRegion,
              analysis_month: analysisMonth,
              generated_at: new Date().toISOString(),
              weekend_dominant_stations: weekendResult.status === 'fulfilled' && weekendResult.value?.success 
                ? weekendResult.value.data : [],
              night_demand_stations: nightResult.status === 'fulfilled' && nightResult.value?.success 
                ? nightResult.value.data : [],
              rush_hour_stations: rushHourResult.status === 'fulfilled' && rushHourResult.value?.success 
                ? rushHourResult.value.data : { morning_rush: [], evening_rush: [] },
              lunch_time_stations: lunchTimeResult.status === 'fulfilled' && lunchTimeResult.value?.success 
                ? lunchTimeResult.value.data : [],
              area_type_analysis: areaTypeResult.status === 'fulfilled' && areaTypeResult.value?.success 
                ? areaTypeResult.value.data : { residential_stations: [], business_stations: [] },
              underutilized_stations: underutilizedResult.status === 'fulfilled' && underutilizedResult.value?.success 
                ? underutilizedResult.value.data : []
            };

            const fallbackIntegrationResult = { success: true, data: fallbackData };
            console.log("✅ 개별 API 폴백 성공:", fallbackIntegrationResult);
            processIntegrationResult(fallbackIntegrationResult);
          }
        }

        function processIntegrationResult(integrationResult: any) {
          console.log("🚌 Integrated API Result:", integrationResult);

          // 데이터 검증 및 구조 확인
          if (!integrationResult?.success) {
            throw new Error(`API 응답 실패: ${integrationResult?.message || 'Unknown error'}`);
          }

          if (!integrationResult?.data) {
            throw new Error("API 응답에 데이터가 없습니다.");
          }

          const data = integrationResult.data;

          // 필수 데이터 구조 검증
          const requiredFields = [
            'weekend_dominant_stations',
            'night_demand_stations', 
            'rush_hour_stations',
            'lunch_time_stations',
            'area_type_analysis',
            'underutilized_stations'
          ];

          const missingFields = requiredFields.filter(field => !(field in data));
          if (missingFields.length > 0) {
            console.warn(`⚠️ 누락된 데이터 필드: ${missingFields.join(', ')}`);
          }

          // 각 패턴별 데이터 유효성 검증 및 기본값 설정
          const validateAndNormalize = (fieldData: any, fieldName: string, defaultValue: any) => {
            if (!fieldData) {
              console.warn(`⚠️ ${fieldName} 데이터가 없습니다. 기본값으로 설정합니다.`);
              return defaultValue;
            }
            return fieldData;
          };

          // 각 패턴 데이터를 검증하고 상태로 설정
          setWeekendData({
            success: true,
            data: validateAndNormalize(data.weekend_dominant_stations, '주말 우세 정류장', []),
          });

          setNightData({
            success: true,
            data: validateAndNormalize(data.night_demand_stations, '심야 고수요 정류장', []),
          });

          setRushHourData({
            success: true,
            data: validateAndNormalize(data.rush_hour_stations, '러시아워 정류장', { morning_rush: [], evening_rush: [] }),
          });

          setLunchTimeData({
            success: true,
            data: validateAndNormalize(data.lunch_time_stations, '점심시간 특화 정류장', []),
          });

          setAreaTypeData({
            success: true,
            data: validateAndNormalize(data.area_type_analysis, '지역 특성 분석', { residential_stations: [], business_stations: [] }),
          });

          setUnderutilizedData({
            success: true,
            data: validateAndNormalize(data.underutilized_stations, '저활용 정류장', []),
          });

          console.log("✅ 모든 패턴 데이터 처리 완료");
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
    };

    loadTrafficAnalysisData();
  }, [selectedMonth, selectedRegion]);

  // 로딩 상태
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">교통 패턴 분석 데이터 로딩 중...</p>
          </div>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="p-6">
            <div className="text-center text-red-500">
              <p className="font-medium">데이터 로드 실패</p>
              <p className="text-sm mt-2">{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 애니메이션 스타일 추가 */}
      <style>{animationStyles}</style>
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold">이상 패턴 분석</h1>
          <p className="text-gray-600">
            {selectedRegion === "전체" ? "서울시 전체" : selectedRegion} ·{" "}
            {monthNames[Number.parseInt(selectedMonth) - 1]}
          </p>
        </div>
      </div>

      {/* 이상 패턴 감지 콘텐츠 */}
      <div className="space-y-6">
        {/* 지역 특성별 정류장 분석 - 상단으로 이동 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5 text-purple-500" />
              지역 특성별 정류장 분석
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <HelpCircle className="h-4 w-4 text-purple-500 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="max-w-sm">
                      <p className="font-medium mb-2">
                        🏠 지역 특성별 정류장 분석 (주거지역/업무지역)
                      </p>
                      <p className="text-sm mb-3">
                        출퇴근시간대 승하차 패턴을 통해 주거지역과 업무지역 특성을 가진 
                        정류장을 각각 식별하여 도시 기능별 교통 패턴을 분석합니다.
                      </p>
                      <div className="text-sm">
                        <p className="font-medium mb-2">💡 활용 사례</p>
                        <ul className="space-y-1">
                          <li>• 도시계획 및 토지이용 패턴 파악</li>
                          <li>• 주거지역 vs 업무지역 대중교통 수요 특성 분석</li>
                          <li>• 지역별 맞춤형 교통정책 수립</li>
                          <li>• 도시 기능 분석을 통한 인프라 개발 계획</li>
                        </ul>
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
            <CardDescription>
              출퇴근 승하차 패턴으로 주거지역과 업무지역 구분 (주중)
            </CardDescription>
          </CardHeader>
          <CardContent>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 주거지역 특성 정류장 */}
              <div className="p-4 bg-blue-50 rounded-lg">
                <h5 className="font-semibold text-lg text-blue-800 mb-3 flex items-center gap-2">
                  🏠 주거지역 특성 (주거→업무 패턴)
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="h-4 w-4 text-blue-500 cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-lg">
                        <div className="space-y-3 text-sm">
                          <div>
                            <p className="font-semibold text-blue-600 mb-2">🏠 주거지역 특성 점수 (0~100점)</p>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">**필터링 조건:**</p>
                            <ul className="space-y-1 text-xs ml-2">
                              <li>• 출근시간(6-8시) 승차 &gt; 하차 (집에서 나감)</li>
                              <li>• 퇴근시간(17-19시) 하차 &gt; 승차 (집으로 돌아옴)</li>
                              <li>• 총 교통량 ≥ 2,000명 (평일 러시아워 기준)</li>
                              <li>• 각 시간대별 비중 ≥ 50%</li>
                            </ul>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">**점수 계산 공식:**</p>
                            <div className="bg-blue-100 border border-blue-200 p-2 rounded text-xs font-mono text-blue-800">
                              <p>출근_주거비중 = 출근승차 / (출근승차 + 출근하차)</p>
                              <p>퇴근_주거비중 = 퇴근하차 / (퇴근승차 + 퇴근하차)</p>
                              <p className="mt-1">기본점수 = (출근_주거비중 + 퇴근_주거비중) / 2</p>
                              <p className="mt-1">최종점수 = 기본점수 × 신뢰도가중치 × 100</p>
                            </div>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">📊 점수 해석:</p>
                            <ul className="space-y-1 text-xs">
                              <li>• **80점 이상**: 매우 전형적인 주거지역 특성</li>
                              <li>• **70~79점**: 뚜렷한 주거지역 특성</li>
                              <li>• **60~69점**: 보통 주거지역 특성</li>
                              <li>• **50~59점**: 약한 주거지역 특성</li>
                            </ul>
                          </div>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </h5>
                <div className="space-y-3 scrollable-list">
                  {areaTypeData?.data?.residential_stations?.map(
                    (item: any, index: number) => (
                      <div
                        key={item.station.station_id}
                        className="flex flex-col p-3 bg-white rounded-lg shadow-sm animate-slide-in border-l-4 border-l-blue-400"
                        style={{ animationDelay: `${index * 100}ms` }}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="font-semibold text-base">
                              {formatStationName(
                                item,
                                areaTypeData?.data?.residential_stations || []
                              )}
                            </div>
                            <div className="text-blue-600 font-semibold text-sm mt-1">
                              불균형 비율: {item.imbalance_ratio?.toFixed(1)}
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          {(() => {
                            const maxValues = getGlobalMaxValues();
                            return (
                              <>
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">출근시간대 승차 ⬆️</div>
                                  <div className="font-medium text-blue-600">
                                    {(item.morning_ride || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.morning_ride || 0, maxValues.morningRide, 'bg-blue-500', index, 0)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">출근시간대 하차 ⬇️</div>
                                  <div className="font-medium text-gray-600">
                                    {(item.morning_alight || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.morning_alight || 0, maxValues.morningAlight, 'bg-gray-400', index, 25)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">퇴근시간대 승차 ⬆️</div>
                                  <div className="font-medium text-gray-600">
                                    {(item.evening_ride || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.evening_ride || 0, maxValues.eveningRide, 'bg-gray-400', index, 50)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">퇴근시간대 하차 ⬇️</div>
                                  <div className="font-medium text-blue-600">
                                    {(item.evening_alight || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.evening_alight || 0, maxValues.eveningAlight, 'bg-blue-600', index, 75)}
                                </div>
                              </>
                            );
                          })()}
                        </div>
                      </div>
                    )
                  ) || (
                    <div className="text-center text-gray-500 py-4">
                      데이터를 불러오는 중...
                    </div>
                  )}
                </div>
              </div>

              {/* 업무지역 특성 정류장 */}
              <div className="p-4 bg-green-50 rounded-lg">
                <h5 className="font-semibold text-lg text-green-800 mb-3 flex items-center gap-2">
                  🏢 업무지역 특성 (업무←주거 패턴)
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="h-4 w-4 text-green-500 cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-lg">
                        <div className="space-y-3 text-sm">
                          <div>
                            <p className="font-semibold text-green-600 mb-2">🏢 업무지역 특성 점수 (0~100점)</p>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">**필터링 조건:**</p>
                            <ul className="space-y-1 text-xs ml-2">
                              <li>• 출근시간(6-8시) 하차 &gt; 승차 (직장으로 출근)</li>
                              <li>• 퇴근시간(17-19시) 승차 &gt; 하차 (직장에서 퇴근)</li>
                              <li>• 총 교통량 ≥ 2,000명 (평일 러시아워 기준)</li>
                              <li>• 각 시간대별 비중 ≥ 50%</li>
                            </ul>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">**점수 계산 공식:**</p>
                            <div className="bg-green-100 border border-green-200 p-2 rounded text-xs font-mono text-green-800">
                              <p>출근_업무비중 = 출근하차 / (출근승차 + 출근하차)</p>
                              <p>퇴근_업무비중 = 퇴근승차 / (퇴근승차 + 퇴근하차)</p>
                              <p className="mt-1">기본점수 = (출근_업무비중 + 퇴근_업무비중) / 2</p>
                              <p className="mt-1">최종점수 = 기본점수 × 신뢰도가중치 × 100</p>
                            </div>
                          </div>
                          
                          <div>
                            <p className="font-medium mb-1">📊 점수 해석:</p>
                            <ul className="space-y-1 text-xs">
                              <li>• **80점 이상**: 매우 전형적인 업무지역 특성</li>
                              <li>• **70~79점**: 뚜렷한 업무지역 특성</li>
                              <li>• **60~69점**: 보통 업무지역 특성</li>
                              <li>• **50~59점**: 약한 업무지역 특성</li>
                            </ul>
                          </div>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </h5>
                <div className="space-y-3 scrollable-list">
                  {areaTypeData?.data?.business_stations?.map(
                    (item: any, index: number) => (
                      <div
                        key={item.station.station_id}
                        className="flex flex-col p-3 bg-white rounded-lg shadow-sm animate-slide-in border-l-4 border-l-green-400"
                        style={{ animationDelay: `${index * 100}ms` }}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="font-semibold text-base">
                              {formatStationName(
                                item,
                                areaTypeData?.data?.business_stations || []
                              )}
                            </div>
                            <div className="text-green-600 font-semibold text-sm mt-1">
                              불균형 비율: {item.imbalance_ratio?.toFixed(1)}
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          {(() => {
                            const maxValues = getGlobalMaxValues();
                            return (
                              <>
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">출근시간대 승차 ⬆️</div>
                                  <div className="font-medium text-gray-600">
                                    {(item.morning_ride || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.morning_ride || 0, maxValues.morningRide, 'bg-gray-400', index, 0)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">출근시간대 하차 ⬇️</div>
                                  <div className="font-medium text-green-600">
                                    {(item.morning_alight || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.morning_alight || 0, maxValues.morningAlight, 'bg-green-500', index, 25)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">퇴근시간대 승차 ⬆️</div>
                                  <div className="font-medium text-green-600">
                                    {(item.evening_ride || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.evening_ride || 0, maxValues.eveningRide, 'bg-green-600', index, 50)}
                                </div>
                                
                                <div className="space-y-2">
                                  <div className="text-xs text-gray-500 font-medium">퇴근시간대 하차 ⬇️</div>
                                  <div className="font-medium text-gray-600">
                                    {(item.evening_alight || 0).toLocaleString()}명
                                  </div>
                                  {renderProgressBar(item.evening_alight || 0, maxValues.eveningAlight, 'bg-gray-400', index, 75)}
                                </div>
                              </>
                            );
                          })()}
                        </div>
                      </div>
                    )
                  ) || (
                    <div className="text-center text-gray-500 py-4">
                      데이터를 불러오는 중...
                    </div>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 러시아워 고수요 정류장과 저활용 정류장 분석을 나란히 배치 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 러시아워 고수요 정류장 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-orange-500" />
                러시아워 고수요 정류장
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-orange-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="max-w-sm">
                        <p className="font-medium mb-2">
                          ⚡ 출퇴근 시간대 교통 집중 구간
                        </p>
                        <ul className="text-sm space-y-1">
                          <li>• 오전 러시아워: 06:00-08:00</li>
                          <li>• 오후 러시아워: 17:00-19:00</li>
                          <li>• 평상시 대비 높은 승차량</li>
                          <li>• 배차간격 조정 및 증편 필요 지역</li>
                          <li>• 교통 혼잡 완화 대책 우선 지역</li>
                        </ul>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              <CardDescription>
                출퇴근 시간대(06-08시, 17-19시) 교통 집중 구간 (주중)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 오전 러시아워 */}
                <div>
                  <h5 className="font-semibold text-lg text-orange-800 mb-4">
                    🌅 오전 러시아워 (06-08시)
                  </h5>
                  <div className="space-y-4 scrollable-list">
                    {rushHourData?.data?.morning_rush?.map(
                      (item: any, index: number) => (
                        <div
                          key={item.station.station_id}
                          className="p-4 bg-gradient-to-r from-orange-50 to-orange-100 rounded-lg animate-slide-in border-l-4 border-l-orange-500"
                          style={{ animationDelay: `${index * 100}ms` }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                              <div className="text-center">
                                <div className="text-xl font-bold text-orange-600">
                                  #{index + 1}
                                </div>
                              </div>
                              <div>
                                <h4 className="font-semibold text-base">
                                  {formatStationName(
                                    item,
                                    rushHourData?.data?.morning_rush || []
                                  )}
                                </h4>
                                <p className="text-base text-gray-600 mt-1">
                                  오전 승차:{" "}
                                  <span className="font-medium animate-count-up">
                                    {(
                                      animatedNumbers[
                                        `morning-${item.station.station_id}`
                                      ] || 0
                                    ).toLocaleString()}
                                    명
                                  </span>
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <Badge
                                variant="outline"
                                className="text-base px-3 py-1"
                              >
                                {item.vs_district_avg?.toFixed(1)}배
                              </Badge>
                              <p className="text-sm text-gray-600 mt-1">
                                구평균 대비
                              </p>
                            </div>
                          </div>
                        </div>
                      )
                    ) || (
                      <div className="text-center text-gray-500 py-6 text-base">
                        데이터를 불러오는 중...
                      </div>
                    )}
                  </div>
                </div>

                {/* 오후 러시아워 */}
                <div>
                  <h5 className="font-semibold text-lg text-orange-800 mb-4">
                    🌆 오후 러시아워 (17-19시)
                  </h5>
                  <div className="space-y-4 scrollable-list">
                    {rushHourData?.data?.evening_rush?.map(
                      (item: any, index: number) => (
                        <div
                          key={item.station.station_id}
                          className="p-4 bg-gradient-to-r from-orange-50 to-orange-100 rounded-lg animate-slide-in border-l-4 border-l-orange-500"
                          style={{ animationDelay: `${index * 100}ms` }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                              <div className="text-center">
                                <div className="text-xl font-bold text-orange-600">
                                  #{index + 1}
                                </div>
                              </div>
                              <div>
                                <h4 className="font-semibold text-base">
                                  {formatStationName(
                                    item,
                                    rushHourData?.data?.evening_rush || []
                                  )}
                                </h4>
                                <p className="text-base text-gray-600 mt-1">
                                  오후 승차:{" "}
                                  <span className="font-medium animate-count-up">
                                    {(
                                      animatedNumbers[
                                        `evening-${item.station.station_id}`
                                      ] || 0
                                    ).toLocaleString()}
                                    명
                                  </span>
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <Badge
                                variant="outline"
                                className="text-base px-3 py-1"
                              >
                                {item.vs_district_avg?.toFixed(1)}배
                              </Badge>
                              <p className="text-sm text-gray-600 mt-1">
                                구평균 대비
                              </p>
                            </div>
                          </div>
                        </div>
                      )
                    ) || (
                      <div className="text-center text-gray-500 py-6 text-base">
                        데이터를 불러오는 중...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 저활용 정류장 분석 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingDown className="h-5 w-5 text-red-500" />
                저활용 정류장 분석
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-red-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="max-w-sm">
                        <p className="font-medium mb-2">
                          📉 운영 효율성 개선 필요 정류장
                        </p>
                        <ul className="text-sm space-y-1">
                          <li>• 일평균 이용객 수 대비 낮은 효율성</li>
                          <li>• 노선 재배치 또는 운행횟수 조정 검토</li>
                          <li>• DRT(수요응답형 교통) 전환 후보</li>
                          <li>
                            • 효율성 점수: 일평균 승객수 ÷ 연결된 버스 노선수
                          </li>
                          <li>• 구 평균 대비 활용률 (%) 계산</li>
                        </ul>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              <CardDescription>
                운영 효율성 개선이 필요한 정류장들
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 scrollable-list">
                {underutilizedData?.data?.map((item: any, index: number) => {
                  // 정류장 평균 대비 계산 (예: 30%만 이용)
                  const avgComparison = (
                    (item.avg_daily_passengers /
                      (item.station_average || 1000)) *
                    100
                  ).toFixed(1);
                  const comparisonValue = Number(avgComparison);

                  return (
                    <Alert
                      key={item.station.station_id}
                      className="border-l-4 border-l-red-500 animate-slide-in bg-gradient-to-r from-red-50 to-red-100"
                      style={{ animationDelay: `${index * 150}ms` }}
                    >
                      <AlertTriangle className="h-5 w-5" />
                      <div className="flex-1">
                        <div className="space-y-6">
                          {/* 상단: 정류장명 */}
                          <div className="text-center">
                            <h4 className="font-bold text-3xl text-gray-900 mb-2">
                              {formatStationName(
                                item,
                                underutilizedData?.data || []
                              )}
                            </h4>
                            <div className="inline-block px-4 py-1 bg-red-100 text-red-700 rounded-full text-sm font-semibold">
                              저활용 정류장
                            </div>
                          </div>
                          
                          {/* 중단: 주요 지표 2개 - 동일 크기 */}
                          <div className="grid grid-cols-2 gap-6">
                            {/* 평균대비 퍼센테이지 */}
                            <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-lg p-6 border border-red-200 text-center">
                              <div className="text-xs text-red-600 mb-2 font-semibold">평균 대비</div>
                              <div className="text-4xl font-black text-red-700 mb-2">
                                {comparisonValue}%
                              </div>
                              <div className="text-sm text-red-600 font-semibold">
                                {comparisonValue < 100
                                  ? `${(100 - comparisonValue).toFixed(1)}% 낮음 ↓`
                                  : `${(comparisonValue - 100).toFixed(1)}% 높음 ↑`}
                              </div>
                            </div>

                            {/* 일평균이용자 */}
                            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-6 border border-blue-200 text-center">
                              <div className="text-xs text-blue-600 mb-2 font-semibold">일평균 이용자</div>
                              <div className="text-4xl font-black text-blue-700 animate-count-up mb-2">
                                {(
                                  animatedNumbers[
                                    `underutil-${item.station.station_id}`
                                  ] || 0
                                ).toLocaleString()}
                              </div>
                              <div className="text-sm text-blue-600 font-semibold">명/일</div>
                            </div>
                          </div>
                        </div>
                        
                        <AlertDescription>
                          {/* 하단: 세부 정보 3개 - 전체 폭에 맞게 확장 */}
                          <div className="w-full flex gap-6">
                            <div className="flex-1 bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4 border border-orange-200 text-center">
                              <div className="text-xs text-orange-600 mb-2 font-semibold">노선 대비</div>
                              <div className="text-2xl font-black text-orange-700 mb-2">
                                {Math.round(
                                  item.avg_daily_passengers /
                                    Math.max(item.connecting_routes, 1)
                                )}
                              </div>
                              <div className="text-sm font-semibold text-orange-600">명/노선</div>
                            </div>
                            
                            <div className="flex-1 bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200 text-center">
                              <div className="text-xs text-green-600 mb-2 font-semibold">운행 노선</div>
                              <div className="text-2xl font-black text-green-700 mb-2">{item.connecting_routes}</div>
                              <div className="text-sm font-semibold text-green-600">개 노선</div>
                            </div>
                            
                            <div className="flex-1 bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200 text-center">
                              <div className="text-xs text-purple-600 mb-2 font-semibold">최대 일일</div>
                              <div className="text-2xl font-black text-purple-700 mb-2">
                                {(item.max_daily_passengers || 0).toLocaleString()}
                              </div>
                              <div className="text-sm font-semibold text-purple-600">명</div>
                            </div>
                          </div>
                        </AlertDescription>
                      </div>
                    </Alert>
                  );
                }) || (
                  <div className="text-center text-gray-500 py-8">
                    데이터를 불러오는 중...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 나머지 카드들 (주말/심야/점심) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 주말 우세 정류장 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-blue-500" />
                주말 우세 정류장
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-blue-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="max-w-sm">
                        <p className="font-medium mb-2">
                          🎯 주말 특화 교통 수요 지역
                        </p>
                        <ul className="text-sm space-y-1">
                          <li>• 주말 총 교통량(승차 + 하차) 기준 정렬</li>
                          <li>• 관광지, 레저시설, 대형 쇼핑몰 인근확율 높음</li>
                          <li>• 주말 전용 노선 또는 증편 검토 대상</li>
                          <li>• 여가활동 중심의 교통패턴</li>
                          <li>• 구평균 대비 배수로 중요도 측정</li>
                        </ul>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              <CardDescription>
                주말 수요가 높은 관광/레저/쇼핑 지역
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 scrollable-list">
                {weekendData?.data?.map((item: any, index: number) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg animate-slide-in border-l-4 border-l-blue-500"
                    style={{ animationDelay: `${index * 120}ms` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-blue-600">
                          #{item.rank}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {formatStationName(item, weekendData?.data || [])}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          주말 교통량:{" "}
                          <span className="font-medium animate-count-up">
                            {(
                              animatedNumbers[
                                `weekend-${item.station.station_id}`
                              ] || 0
                            ).toLocaleString()}
                            명
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge
                        variant="secondary"
                        className="text-base px-3 py-1"
                      >
                        {item.vs_district_avg?.toFixed(1)}배
                      </Badge>
                      <p className="text-sm text-gray-600 mt-1">구평균 대비</p>
                    </div>
                  </div>
                )) || (
                  <div className="text-center text-gray-500 py-8">
                    데이터를 불러오는 중...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 심야 고수요 정류장 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-purple-500" />
                심야 고수요 정류장
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-purple-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="max-w-sm">
                        <p className="font-medium mb-2">
                          🌙 심야시간대 특화 교통 거점
                        </p>
                        <ul className="text-sm space-y-1">
                          <li>
                            • 심야시간(23,0,1,2,3시) 총 승차인원 기준 정렬
                          </li>
                          <li>• 유흥가, 24시간 상업시설 인근</li>
                          <li>• 교대근무 사업장 및 병원 주변</li>
                          <li>• 심야버스 노선 최적화 대상</li>
                          <li>• 안전 인프라 강화 필요 지역</li>
                        </ul>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              <CardDescription>23:00-03:00 시간대 높은 수요</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 scrollable-list">
                {nightData?.data?.map((item: any, index: number) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-50 to-purple-100 rounded-lg animate-slide-in border-l-4 border-l-purple-500"
                    style={{ animationDelay: `${index * 130}ms` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-purple-600">
                          #{index + 1}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {formatStationName(item, nightData?.data || [])}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          심야 승차:{" "}
                          <span className="font-medium animate-count-up">
                            {(
                              animatedNumbers[
                                `night-${item.station.station_id}`
                              ] || 0
                            ).toLocaleString()}
                            명
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className="text-base px-3 py-1">
                        {item.vs_district_avg?.toFixed(1)}배
                      </Badge>
                      <p className="text-sm text-gray-600 mt-1">구평균 대비</p>
                    </div>
                  </div>
                )) || (
                  <div className="text-center text-gray-500 py-8">
                    데이터를 불러오는 중...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 점심시간 특화 정류장 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-green-500" />
                점심시간 특화 정류장
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-green-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="max-w-sm">
                        <p className="font-medium mb-2">
                          🍽️ 점심시간 교통 집중 지역
                        </p>
                        <ul className="text-sm space-y-1">
                          <li>
                            • 점심시간(11,12,13시) 총 하차인원 기준 정렬
                            (평일만)
                          </li>
                          <li>• 음식점 밀집지역, 업무지구 맛집가</li>
                          <li>• 직장인 외식 수요 반영</li>
                          <li>• 점심시간 배차간격 단축 검토</li>
                          <li>• 업무지역-상업지역 연계 강화</li>
                        </ul>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              <CardDescription>
                점심시간대(11:00-13:00) 하차 집중 구간
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 scrollable-list">
                {lunchTimeData?.data?.map((item: any, index: number) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-green-100 rounded-lg animate-slide-in border-l-4 border-l-green-500"
                    style={{ animationDelay: `${index * 110}ms` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-green-600">
                          #{index + 1}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {formatStationName(item, lunchTimeData?.data || [])}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          점심시간 하차:{" "}
                          <span className="font-medium animate-count-up">
                            {(
                              animatedNumbers[
                                `lunch-${item.station.station_id}`
                              ] || 0
                            ).toLocaleString()}
                            명
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className="text-base px-3 py-1">
                        {item.vs_district_avg?.toFixed(1)}배
                      </Badge>
                      <p className="text-sm text-gray-600 mt-1">구평균 대비</p>
                    </div>
                  </div>
                )) || (
                  <div className="text-center text-gray-500 py-8">
                    데이터를 불러오는 중...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
