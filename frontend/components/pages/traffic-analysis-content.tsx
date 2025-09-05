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

  // 동적 숫자 애니메이션 훅
  const animateNumber = useCallback(
    (key: string, targetValue: number, duration: number = 1500) => {
      // 이미 애니메이션이 진행 중이거나 완료된 경우 건너뛰기
      if (animatedNumbers[key] === targetValue) {
        return;
      }

      const startValue = 0; // 항상 0에서 시작
      const startTime = Date.now();

      const easeOutCubic = (t: number): number => {
        return 1 - Math.pow(1 - t, 3);
      };

      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = easeOutCubic(progress);
        const currentValue = Math.floor(
          startValue + (targetValue - startValue) * easeProgress
        );

        setAnimatedNumbers((prev) => ({
          ...prev,
          [key]: currentValue,
        }));

        // 완료되지 않았으면 계속 진행
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          // 완료 시 정확한 목표값으로 설정
          setAnimatedNumbers((prev) => ({
            ...prev,
            [key]: targetValue,
          }));
        }
      };

      requestAnimationFrame(animate);
    },
    [animatedNumbers]
  );

  // 애니메이션 트리거 - 한 번만 실행되도록 useRef로 관리
  const animationTriggered = useRef(false);

  useEffect(() => {
    if (!loading && !error && !animationTriggered.current) {
      animationTriggered.current = true; // 플래그 설정으로 중복 실행 방지

      // 데이터가 로드되면 애니메이션 시작
      setTimeout(() => {
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

  // 데이터 로드
  useEffect(() => {
    const loadTrafficAnalysisData = async () => {
      try {
        setLoading(true);
        setError(null);

        // 새로운 데이터 로드 시 애니메이션 플래그 리셋
        animationTriggered.current = false;
        setAnimatedNumbers({}); // 애니메이션 숫자 상태 초기화

        console.log("🚌 Loading integrated traffic analysis data for:", {
          selectedMonth,
          selectedRegion,
        });

        // 분석할 구 목록 결정
        const districtsToAnalyze =
          selectedRegion === "전체"
            ? ["강남구", "서초구", "송파구", "영등포구", "마포구"] // 샘플 구들
            : [selectedRegion];

        // 첫 번째 구로 데이터 로드 (데모용)
        const targetDistrict = districtsToAnalyze[0];
        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        // 통합 API 호출
        const integrationResult = await apiService.getIntegratedAnomalyAnalysis(
          targetDistrict,
          analysisMonth
        );

        console.log("🚌 Integrated API Result:", integrationResult);

        // 통합 API 응답 데이터를 개별 상태로 분리
        if (integrationResult?.success && integrationResult?.data) {
          const data = integrationResult.data;

          // 각 패턴 데이터를 기존 형식에 맞게 변환
          setWeekendData({
            success: true,
            data: data.weekend_dominant_stations || [],
          });

          setNightData({
            success: true,
            data: data.night_demand_stations || [],
          });

          setRushHourData({
            success: true,
            data: data.rush_hour_stations || {},
          });

          setLunchTimeData({
            success: true,
            data: data.lunch_time_stations || [],
          });

          setAreaTypeData({
            success: true,
            data: data.area_type_analysis || {},
          });

          setUnderutilizedData({
            success: true,
            data: data.underutilized_stations || [],
          });

          // setIntegrationData(integrationResult); // 추후 필요시 활성화
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
                        🏠 주거지역 vs 🏢 업무지역 구분 분석
                      </p>
                      <ul className="text-sm space-y-1">
                        <li>• 출퇴근 승하차 패턴으로 지역 특성 파악</li>
                        <li>• 주거지역: 오전 승차↑, 오후 하차↑</li>
                        <li>• 업무지역: 오전 하차↑, 오후 승차↑</li>
                        <li>• 도시계획 및 교통정책 수립에 활용</li>
                      </ul>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
            <CardDescription>
              출퇴근 승하차 패턴으로 주거지역과 업무지역 구분
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 주거지역 특성 정류장 */}
              <div className="p-4 bg-blue-50 rounded-lg">
                <h5 className="font-semibold text-lg text-blue-800 mb-3 flex items-center gap-2">
                  🏠 주거지역 특성
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
                              주거지 특성도: {item.imbalance_ratio?.toFixed(1)}
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-600">
                              오전 승차
                            </span>
                            <span className="font-medium animate-count-up">
                              {(
                                animatedNumbers[
                                  `residential-morning-${item.station.station_id}`
                                ] || 0
                              ).toLocaleString()}
                              명
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-gradient-to-r from-blue-400 to-blue-600 h-2 rounded-full animate-progress"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((item.morning_ride || 0) /
                                    Math.max(
                                      ...(areaTypeData?.data?.residential_stations?.map(
                                        (s: any) => s.morning_ride
                                      ) || [1])
                                    )) *
                                    100
                                )}%`,
                                animationDelay: `${index * 100 + 200}ms`,
                              }}
                            ></div>
                          </div>

                          <div className="flex items-center justify-between mt-3">
                            <span className="text-sm text-gray-600">
                              오후 하차
                            </span>
                            <span className="font-medium animate-count-up">
                              {(
                                animatedNumbers[
                                  `residential-evening-${item.station.station_id}`
                                ] || 0
                              ).toLocaleString()}
                              명
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-gradient-to-r from-blue-500 to-blue-700 h-2 rounded-full animate-progress"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((item.evening_alight || 0) /
                                    Math.max(
                                      ...(areaTypeData?.data?.residential_stations?.map(
                                        (s: any) => s.evening_alight
                                      ) || [1])
                                    )) *
                                    100
                                )}%`,
                                animationDelay: `${index * 100 + 300}ms`,
                              }}
                            ></div>
                          </div>
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
                  🏢 업무지역 특성
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
                              업무지 특성도: {item.imbalance_ratio?.toFixed(1)}
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-600">
                              오전 하차
                            </span>
                            <span className="font-medium animate-count-up">
                              {(
                                animatedNumbers[
                                  `business-morning-${item.station.station_id}`
                                ] || 0
                              ).toLocaleString()}
                              명
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-gradient-to-r from-green-400 to-green-600 h-2 rounded-full animate-progress"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((item.morning_alight || 0) /
                                    Math.max(
                                      ...(areaTypeData?.data?.business_stations?.map(
                                        (s: any) => s.morning_alight
                                      ) || [1])
                                    )) *
                                    100
                                )}%`,
                                animationDelay: `${index * 100 + 200}ms`,
                              }}
                            ></div>
                          </div>

                          <div className="flex items-center justify-between mt-3">
                            <span className="text-sm text-gray-600">
                              오후 승차
                            </span>
                            <span className="font-medium animate-count-up">
                              {(
                                animatedNumbers[
                                  `business-evening-${item.station.station_id}`
                                ] || 0
                              ).toLocaleString()}
                              명
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-gradient-to-r from-green-500 to-green-700 h-2 rounded-full animate-progress"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((item.evening_ride || 0) /
                                    Math.max(
                                      ...(areaTypeData?.data?.business_stations?.map(
                                        (s: any) => s.evening_ride
                                      ) || [1])
                                    )) *
                                    100
                                )}%`,
                                animationDelay: `${index * 100 + 300}ms`,
                              }}
                            ></div>
                          </div>
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
                          <li>• 오전 러시아워: 06:00-09:00</li>
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
                출퇴근 시간대(06-09시, 17-19시) 교통 집중 구간
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 오전 러시아워 */}
                <div>
                  <h5 className="font-semibold text-lg text-orange-800 mb-4">
                    🌅 오전 러시아워 (06-09시)
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
                                {item.vs_district_avg?.toFixed(1)}X
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
                                {item.vs_district_avg?.toFixed(1)}X
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
                          <li>• 운영비용 절감 효과 기대</li>
                          <li>• 서비스 품질 유지하며 최적화</li>
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
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-semibold text-base">
                            {formatStationName(
                              item,
                              underutilizedData?.data || []
                            )}
                          </h4>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-red-600">
                              평균 대비
                            </span>
                            <Badge
                              variant="destructive"
                              className="text-base px-3 py-1"
                            >
                              {comparisonValue}%
                            </Badge>
                          </div>
                        </div>
                        <AlertDescription>
                          {/* 시각적 비교 표현 - Progress Bar */}
                          <div className="mb-3">
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="text-gray-600">
                                정류장 평균 대비
                              </span>
                              <span className="text-red-600 font-medium">
                                {comparisonValue < 100
                                  ? `▼ ${(100 - comparisonValue).toFixed(
                                      1
                                    )}% 낮음`
                                  : `▲ ${(comparisonValue - 100).toFixed(
                                      1
                                    )}% 높음`}
                              </span>
                            </div>
                            <div className="relative w-full h-8 bg-gray-100 rounded-lg overflow-hidden border border-gray-200">
                              {/* 평균선 표시 (50% 위치) */}
                              <div className="absolute inset-y-0 left-1/2 w-0.5 bg-gray-600 z-10">
                                <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs text-gray-600 font-medium">
                                  평균
                                </span>
                              </div>
                              {/* 실제 사용률 바 */}
                              <div
                                className="relative h-full bg-gradient-to-r from-red-500 to-red-400 transition-all duration-1000 ease-out"
                                style={{
                                  width: `${Math.min(
                                    comparisonValue / 2,
                                    50
                                  )}%`,
                                  animation: "slideInLeft 1s ease-out",
                                }}
                              >
                                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-white font-bold">
                                  {comparisonValue}%
                                </span>
                              </div>
                              {/* 작은 삼각형 인디케이터 */}
                              <div
                                className="absolute top-full mt-1 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-red-500"
                                style={{
                                  left: `${Math.min(comparisonValue / 2, 50)}%`,
                                }}
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4 text-base">
                            <div>
                              <span className="text-gray-600">
                                일평균 이용:
                              </span>{" "}
                              <span className="font-semibold text-red-700 animate-count-up">
                                {(
                                  animatedNumbers[
                                    `underutil-${item.station.station_id}`
                                  ] || 0
                                ).toLocaleString()}
                                명
                              </span>
                            </div>
                            <div>
                              <span className="text-gray-600">노선 대비:</span>{" "}
                              <span className="font-semibold text-red-700">
                                {Math.round(
                                  item.avg_daily_passengers /
                                    Math.max(item.connecting_routes, 1)
                                )}
                                명/노선
                              </span>
                            </div>
                          </div>
                          <div className="mt-2 text-sm text-gray-600">
                            <strong>운행 노선:</strong> {item.connecting_routes}
                            개 | <strong>최대 일일:</strong>{" "}
                            {item.max_daily_passengers?.toLocaleString()}명
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
                          <li>• 토요일, 일요일 교통량이 평일 대비 높음</li>
                          <li>• 관광지, 레저시설, 대형 쇼핑몰 인근</li>
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
                        {item.vs_district_avg?.toFixed(1)}X
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
                          <li>• 23:00-03:00 시간대 높은 승차량</li>
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
                        {item.vs_district_avg?.toFixed(1)}X
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
                          <li>• 11:00-13:00 시간대 하차량 집중</li>
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
                        {item.vs_district_avg?.toFixed(1)}X
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
