/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MapPin, Navigation, Activity, Globe, HelpCircle } from "lucide-react";
import {
  Tooltip as HelpTooltip,
  TooltipContent as HelpTooltipContent,
  TooltipProvider,
  TooltipTrigger as HelpTooltipTrigger,
} from "@/components/ui/tooltip";
import { useState, useEffect, useRef } from "react";
import {
  apiService,
  HeatmapResponse,
  utils,
} from "@/lib/api";
import {
  HeatmapSeoulMap,
  HeatmapSeoulMapRef,
} from "@/components/map/heatmap-seoul-map";

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

interface HeatmapContentProps {
  selectedMonth: string;
  selectedRegion: string;
}

export function HeatmapContent({
  selectedMonth,
  selectedRegion,
}: HeatmapContentProps) {
  const [viewMode, setViewMode] = useState<"district" | "station">("district");
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
  const [heatmapData, setHeatmapData] = useState<HeatmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 이상 패턴 분석 데이터 상태들
  const [selectedPattern, setSelectedPattern] = useState<string | null>(null);
  const [weekendData, setWeekendData] = useState<any>(null);
  const [nightData, setNightData] = useState<any>(null);
  const [rushHourData, setRushHourData] = useState<any>(null);
  const [lunchTimeData, setLunchTimeData] = useState<any>(null);
  const [areaTypeData, setAreaTypeData] = useState<any>(null);
  const [underutilizedData, setUnderutilizedData] = useState<any>(null);
  const mapRef = useRef<HeatmapSeoulMapRef>(null);

  // API 데이터 로드
  useEffect(() => {
    const loadHeatmapData = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log("🗺️ Loading heatmap and pattern data for:", {
          selectedMonth,
          selectedRegion,
        });

        // 지역이 변경되면 패턴 선택 초기화
        setSelectedPattern(null);
        console.log("🔄 패턴 선택 초기화 - 지역 변경:", selectedRegion);

        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        // 히트맵 데이터 로드
        const heatmapResponse = await apiService.getSeoulHeatmap(
          analysisMonth,
          true // 항상 정류장 상세 정보 포함
        );

        console.log("🗺️ Heatmap API response:", heatmapResponse);
        setHeatmapData(heatmapResponse);

        // 선택된 지역에 따른 이상 패턴 분석 데이터 로드
        if (selectedRegion !== "전체") {
          console.log(
            "📊 Loading pattern analysis for district:",
            selectedRegion
          );

          // 모든 패턴 분석 API 병렬 호출
          const [
            weekendResult,
            nightResult,
            rushHourResult,
            lunchTimeResult,
            areaTypeResult,
            underutilizedResult,
          ] = await Promise.allSettled([
            apiService.getWeekendDominantStations(
              selectedRegion,
              analysisMonth,
              5
            ),
            apiService.getNightDemandStations(selectedRegion, analysisMonth, 5),
            apiService.getRushHourAnalysis(selectedRegion, analysisMonth),
            apiService.getLunchTimeStations(selectedRegion, analysisMonth, 5),
            apiService.getAreaTypeAnalysis(selectedRegion, analysisMonth),
            apiService.getUnderutilizedStations(
              selectedRegion,
              analysisMonth,
              5
            ),
          ]);

          // 성공한 결과들 저장
          if (weekendResult.status === "fulfilled")
            setWeekendData(weekendResult.value);
          if (nightResult.status === "fulfilled")
            setNightData(nightResult.value);
          if (rushHourResult.status === "fulfilled")
            setRushHourData(rushHourResult.value);
          if (lunchTimeResult.status === "fulfilled")
            setLunchTimeData(lunchTimeResult.value);
          if (areaTypeResult.status === "fulfilled")
            setAreaTypeData(areaTypeResult.value);
          if (underutilizedResult.status === "fulfilled")
            setUnderutilizedData(underutilizedResult.value);
        } else {
          // 전체 선택시 패턴 데이터 초기화
          setWeekendData(null);
          setNightData(null);
          setRushHourData(null);
          setLunchTimeData(null);
          setAreaTypeData(null);
          setUnderutilizedData(null);
        }
      } catch (err) {
        console.error("🚨 Heatmap API error:", err);
        setError(
          err instanceof Error ? err.message : "Failed to load heatmap data"
        );
      } finally {
        setLoading(false);
      }
    };

    loadHeatmapData();
  }, [selectedMonth, selectedRegion]); // selectedRegion 추가

  // 선택된 지역에 따른 데이터 필터링
  const filteredDistricts =
    heatmapData?.districts.filter((d) =>
      selectedRegion === "전체" ? true : d.district_name === selectedRegion
    ) || [];


  // 상위 정류장 데이터 (모든 구의 정류장 중 상위 5개)
  const topStations =
    heatmapData?.districts
      .flatMap((d) => d.stations || [])
      .sort((a, b) => b.total_traffic - a.total_traffic)
      .slice(0, 5) || [];

  // 선택된 패턴에 따른 정류장 데이터 추출
  const getPatternStations = () => {
    if (!selectedPattern || (selectedRegion === "전체" && !selectedDistrict))
      return [];

    switch (selectedPattern) {
      case "weekend":
        return (
          weekendData?.data?.map((item: any) => ({
            ...item.station,
            patternType: "weekend",
            patternColor: "#3B82F6", // blue
            patternInfo: `주말 교통량: ${item.weekend_total_traffic?.toLocaleString()}명`,
          })) || []
        );

      case "night":
        return (
          nightData?.data?.map((item: any) => ({
            ...item.station,
            patternType: "night",
            patternColor: "#8B5CF6", // purple
            patternInfo: `심야 승차: ${item.total_night_ride?.toLocaleString()}명`,
          })) || []
        );

      case "underutilized":
        return (
          underutilizedData?.data?.map((item: any) => ({
            ...item.station,
            patternType: "underutilized",
            patternColor: "#EF4444", // red
            patternInfo: `효율성: ${
              item.efficiency_score
            }% | 일평균: ${item.avg_daily_passengers?.toLocaleString()}명`,
          })) || []
        );

      case "lunchtime":
        return (
          lunchTimeData?.data?.map((item: any) => ({
            ...item.station,
            patternType: "lunchtime",
            patternColor: "#10B981", // green
            patternInfo: `점심시간 하차: ${item.total_lunch_alight?.toLocaleString()}명`,
          })) || []
        );

      case "rushhour":
        const morningStations =
          rushHourData?.data?.morning_rush?.map((item: any) => ({
            ...item.station,
            patternType: "rushhour",
            patternColor: "#FF6B35", // bright orange for morning
            patternInfo: `오전 승차: ${item.total_morning_rush?.toLocaleString()}명`,
            rushType: "morning",
          })) || [];

        const eveningStations =
          rushHourData?.data?.evening_rush?.map((item: any) => ({
            ...item.station,
            patternType: "rushhour",
            patternColor: "#DC2626", // red for evening
            patternInfo: `오후 승차: ${item.total_evening_rush?.toLocaleString()}명`,
            rushType: "evening",
          })) || [];

        return [...morningStations, ...eveningStations];

      case "areatype":
        const residentialStations =
          areaTypeData?.data?.residential_stations?.map((item: any) => ({
            ...item.station,
            patternType: "areatype",
            patternColor: "#0EA5E9", // sky blue - 하늘색으로 변경
            patternInfo: `주거지역 | 오전승차: ${item.morning_ride?.toLocaleString()}명`,
            areaType: "residential",
          })) || [];

        const businessStations =
          areaTypeData?.data?.business_stations?.map((item: any) => ({
            ...item.station,
            patternType: "areatype",
            patternColor: "#8B5CF6", // purple
            patternInfo: `업무지역 | 오전하차: ${item.morning_alight?.toLocaleString()}명`,
            areaType: "business",
          })) || [];

        return [...residentialStations, ...businessStations];

      default:
        return [];
    }
  };

  const patternStations = getPatternStations();

  // 중복된 정류장 이름을 감지하고 구분 표시하는 함수
  const checkDuplicateStationNames = (stations: any[]) => {
    const nameCount: Record<string, number> = {};
    stations.forEach(station => {
      nameCount[station.station_name] = (nameCount[station.station_name] || 0) + 1;
    });
    return nameCount;
  };

  // 정류장 이름 표시 함수
  const formatStationName = (station: any, allStations: any[]) => {
    const duplicateNames = checkDuplicateStationNames(allStations);
    const isDuplicate = duplicateNames[station.station_name] > 1;
    
    if (isDuplicate) {
      // 6자리 ID (station_id의 마지막 6자리 또는 전체가 6자리 미만이면 전체)
      const shortId = station.station_id?.toString().slice(-6) || 'N/A';
      return {
        displayName: `${station.station_name} (${shortId})`,
        showFullId: true,
        fullId: station.station_id?.toString() || 'N/A',
        districtInfo: station.district_name || selectedDistrict || '위치정보'
      };
    }
    
    return {
      displayName: station.station_name,
      showFullId: false,
      fullId: '',
      districtInfo: station.district_name || selectedDistrict || '위치정보'
    };
  };

  // 지도에서 구 클릭 시 호출
  const handleDistrictClick = (districtName: string, districtCode: string) => {
    console.log(`District clicked: ${districtName} (${districtCode})`);

    // 새로운 구를 선택할 때 패턴 선택 초기화
    if (selectedDistrict !== districtName) {
      setSelectedPattern(null);
      console.log("🔄 패턴 선택 초기화 - 새로운 구 선택:", districtName);
    }

    setSelectedDistrict(districtName);
  };

  // 지도에서 구 클릭 시 해당 구의 패턴 데이터 로드
  useEffect(() => {
    if (!selectedDistrict) return;

    const loadDistrictPatternData = async () => {
      try {
        console.log(
          "📊 Loading pattern analysis for clicked district:",
          selectedDistrict
        );

        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        // 클릭된 구의 패턴 분석 데이터 로드 (기존 selectedRegion 패턴과 동일)
        const [
          weekendResult,
          nightResult,
          rushHourResult,
          lunchTimeResult,
          areaTypeResult,
          underutilizedResult,
        ] = await Promise.allSettled([
          apiService.getWeekendDominantStations(
            selectedDistrict,
            analysisMonth,
            5
          ),
          apiService.getNightDemandStations(selectedDistrict, analysisMonth, 5),
          apiService.getRushHourAnalysis(selectedDistrict, analysisMonth),
          apiService.getLunchTimeStations(selectedDistrict, analysisMonth, 5),
          apiService.getAreaTypeAnalysis(selectedDistrict, analysisMonth),
          apiService.getUnderutilizedStations(
            selectedDistrict,
            analysisMonth,
            5
          ),
        ]);

        // 성공한 결과들 저장
        if (weekendResult.status === "fulfilled")
          setWeekendData(weekendResult.value);
        if (nightResult.status === "fulfilled") setNightData(nightResult.value);
        if (rushHourResult.status === "fulfilled")
          setRushHourData(rushHourResult.value);
        if (lunchTimeResult.status === "fulfilled")
          setLunchTimeData(lunchTimeResult.value);
        if (areaTypeResult.status === "fulfilled")
          setAreaTypeData(areaTypeResult.value);
        if (underutilizedResult.status === "fulfilled")
          setUnderutilizedData(underutilizedResult.value);

        console.log("✅ Pattern data loaded for district:", selectedDistrict);
      } catch (err) {
        console.error("🚨 Failed to load district pattern data:", err);
      }
    };

    loadDistrictPatternData();
  }, [selectedDistrict]); // selectedDistrict 변경 시 실행

  // 지도 중심 이동 함수
  const handleResetMapCenter = () => {
    if (mapRef.current) {
      mapRef.current.resetToSeoulCenter();
    }
  };

  // 로딩 상태 표시
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">히트맵 데이터 로딩 중...</p>
          </div>
        </div>
      </div>
    );
  }

  // 에러 상태 표시
  if (error) {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="p-6">
            <div className="text-center text-red-500">
              <p className="font-medium">데이터 로드 실패</p>
              <p className="text-base mt-2">{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* 개선된 헤더 섹션 */}
      <div className="space-y-4">
        {/* 메인 타이틀 & 설명 */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <MapPin className="h-6 w-6 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">교통량 분석</h1>
          </div>
          <p className="text-sm text-gray-600">
            서울시 교통 패턴 시각화
          </p>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>{monthNames[Number.parseInt(selectedMonth) - 1]}</span>
            {selectedRegion !== "전체" && (
              <>
                <span className="mx-1">•</span>
                <span className="text-blue-600 font-medium">{selectedRegion}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 개선된 3열 레이아웃: 좌측 패턴 + 중앙 지도 + 우측 상세정보 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[800px]">
        {/* 좌측 - 패턴 분석 제어판 */}
        <div className="lg:col-span-1 order-2 lg:order-1">
          <Card className="h-fit shadow-lg border-0 bg-gradient-to-br from-gray-50 to-slate-100">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base font-bold text-gray-800">
                <Activity className="h-5 w-5 text-purple-600" />
                패턴 분석
              </CardTitle>
              <CardDescription className="text-sm text-gray-600">
                {selectedRegion === "전체" && !selectedDistrict
                  ? "구 선택 필요"
                  : `${selectedDistrict || selectedRegion}`}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {selectedRegion === "전체" && !selectedDistrict ? (
                <div className="text-center text-gray-400 py-8">
                  <Activity className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p className="text-sm">지도에서 구 클릭</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <TooltipProvider>
                    {/* 주말 우세 정류장 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "weekend" ? null : "weekend"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "weekend"
                              ? "bg-blue-600 text-white"
                              : "bg-white text-gray-700 hover:bg-blue-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/주말패턴_히트맵.png" alt="주말 패턴" className="h-4 w-4" />
                            <span>주말</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">주말 우세 정류장</p>
                          <p className="text-gray-400">주말 고수요 관광지/레저 정류장</p>
                          <p className="mt-1">{weekendData?.data?.length || 0}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>

                    {/* 심야 고수요 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "night" ? null : "night"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "night"
                              ? "bg-purple-600 text-white"
                              : "bg-white text-gray-700 hover:bg-purple-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/심야패턴_히트맵.png" alt="심야 패턴" className="h-4 w-4" />
                            <span>심야</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">심야시간 고수요</p>
                          <p className="text-gray-400">24시간 활성화된 상업지역 정류장</p>
                          <p className="mt-1">{nightData?.data?.length || 0}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>

                    {/* 저활용 정류장 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "underutilized"
                                ? null
                                : "underutilized"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "underutilized"
                              ? "bg-red-600 text-white"
                              : "bg-white text-gray-700 hover:bg-red-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/저활용_히트맵.png" alt="저활용 패턴" className="h-4 w-4" />
                            <span>저활용</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">저활용 정류장</p>
                          <p className="text-gray-400">운영 최적화 대상 정류장</p>
                          <p className="mt-1">{underutilizedData?.data?.length || 0}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>

                    {/* 점심시간 특화 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "lunchtime" ? null : "lunchtime"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "lunchtime"
                              ? "bg-green-600 text-white"
                              : "bg-white text-gray-700 hover:bg-green-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/점심패턴_히트맵.png" alt="점심 패턴" className="h-4 w-4" />
                            <span>점심</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">점심시간 특화</p>
                          <p className="text-gray-400">음식점가/상업지구 점심 정류장</p>
                          <p className="mt-1">{lunchTimeData?.data?.length || 0}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>

                    {/* 러시아워 핫스팟 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "rushhour" ? null : "rushhour"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "rushhour"
                              ? "bg-orange-600 text-white"
                              : "bg-white text-gray-700 hover:bg-orange-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/러시아워_히트맵.png" alt="러시아워 패턴" className="h-4 w-4" />
                            <span>러시</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">러시아워 고수요</p>
                          <p className="text-gray-400">출퇴근 시간대 집중 정류장</p>
                          <p className="mt-1">{(rushHourData?.data?.morning_rush?.length || 0) + (rushHourData?.data?.evening_rush?.length || 0)}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>

                    {/* 지역 특성 분석 */}
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <button
                          onClick={() => {
                            setSelectedPattern(
                              selectedPattern === "areatype" ? null : "areatype"
                            );
                            setViewMode("station");
                          }}
                          className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                            selectedPattern === "areatype"
                              ? "bg-sky-600 text-white"
                              : "bg-white text-gray-700 hover:bg-sky-50 border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <img src="/heatmap_icon/지역특성_히트맵.png" alt="지역 특성 패턴" className="h-4 w-4" />
                            <span>지역</span>
                          </div>
                        </button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent side="right">
                        <div className="text-xs">
                          <p className="font-semibold">지역 특성별</p>
                          <p className="text-gray-400">주거지역 vs 업무지역 정류장 구분</p>
                          <p className="mt-1">{(areaTypeData?.data?.residential_stations?.length || 0) + (areaTypeData?.data?.business_stations?.length || 0)}개 정류장 발견</p>
                        </div>
                      </HelpTooltipContent>
                    </HelpTooltip>
                  </TooltipProvider>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 중앙 - 메인 히트맵 시각화 */}
        <div className="lg:col-span-7 order-1 lg:order-2">
          <Card className="shadow-xl border-0 bg-gradient-to-br from-gray-50 to-slate-100 overflow-hidden relative">
            <CardHeader className="bg-gray-50/90 backdrop-blur-sm">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-3 text-3xl font-bold text-gray-800">
                    <img src="/heatmap_icon/지도_히트맵.png" alt="지도 히트맵" className="h-8 w-8" />
                    서울시 교통량 히트맵
                  </CardTitle>
                  <CardDescription className="text-lg text-gray-600 mt-1 flex items-center gap-2">
                    {viewMode === "district" ? (
                      <>
                        <img src="/heatmap_icon/지도_구별_히트맵.png" alt="구별 히트맵" className="h-5 w-5" />
                        25개 자치구별
                      </>
                    ) : (
                      <>
                        <img src="/heatmap_icon/지도_정류장별_히트맵.png" alt="정류장별 히트맵" className="h-5 w-5" />
                        정류장별
                      </>
                    )} 교통량 시각화
                  </CardDescription>
                </div>
                {/* 컨트롤 버튼들 - 우측 상단 */}
                <TooltipProvider>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-2">
                      <HelpTooltip>
                        <HelpTooltipTrigger asChild>
                          <Button
                            variant={viewMode === "district" ? "default" : "outline"}
                            size="sm"
                            onClick={() => setViewMode("district")}
                            className="h-8 px-3 text-sm"
                          >
                            구별
                          </Button>
                        </HelpTooltipTrigger>
                        <HelpTooltipContent>
                          <p>25개 자치구별 교통량 집계</p>
                        </HelpTooltipContent>
                      </HelpTooltip>
                      <HelpTooltip>
                        <HelpTooltipTrigger asChild>
                          <Button
                            variant={viewMode === "station" ? "default" : "outline"}
                            size="sm"
                            onClick={() => setViewMode("station")}
                            className="h-8 px-3 text-sm"
                          >
                            정류장
                          </Button>
                        </HelpTooltipTrigger>
                        <HelpTooltipContent>
                          <p>개별 정류장별 교통량 표시</p>
                        </HelpTooltipContent>
                      </HelpTooltip>
                    </div>
                    <HelpTooltip>
                      <HelpTooltipTrigger asChild>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={handleResetMapCenter}
                          className="h-8 px-3 text-sm"
                        >
                          <Navigation className="h-4 w-4" />
                        </Button>
                      </HelpTooltipTrigger>
                      <HelpTooltipContent>
                        <p>서울시 전체 보기로 지도 중심 이동</p>
                      </HelpTooltipContent>
                    </HelpTooltip>
                    {((viewMode === "station" && selectedDistrict) || (viewMode === "district" && (selectedRegion !== "전체" || selectedDistrict))) && (
                      <HelpTooltip>
                        <HelpTooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              if (viewMode === "station") {
                                setSelectedDistrict(null);
                                setSelectedPattern(null);
                                handleResetMapCenter();
                              } else if (viewMode === "district") {
                                // 구별 모드에서는 선택된 구를 해제하여 전체 구 보기
                                setSelectedDistrict(null);
                                setSelectedPattern(null);
                                handleResetMapCenter();
                              }
                            }}
                            className="h-8 px-3 text-sm"
                          >
                            <Globe className="h-4 w-4" />
                          </Button>
                        </HelpTooltipTrigger>
                        <HelpTooltipContent>
                          <p>{viewMode === "station" ? "전체 정류장 보기" : "전체 구 보기"}</p>
                        </HelpTooltipContent>
                      </HelpTooltip>
                    )}
                  </div>
                </TooltipProvider>
              </div>
            </CardHeader>
            <CardContent>
              <HeatmapSeoulMap
                ref={mapRef}
                onDistrictClick={handleDistrictClick}
                selectedDistrict={selectedDistrict || undefined}
                districts={filteredDistricts}
                viewMode={viewMode}
                loading={loading}
                selectedPattern={selectedPattern}
                patternStations={patternStations}
              />
              <CardDescription className="mt-2">
                {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최신
                업데이트 기준)
                {viewMode === "station" && selectedDistrict && (
                  <span className="ml-4 text-blue-600 font-medium">
                    | {selectedDistrict} 정류장만 표시 중
                  </span>
                )}
                {viewMode === "station" && !selectedDistrict && (
                  <span className="ml-4 text-gray-500">
                    | 구를 클릭하여 해당 구의 정류장만 확인
                  </span>
                )}
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        {/* 우측 - 상세 정보 및 통계 대시보드 */}
        <div className="lg:col-span-4 space-y-4 order-3 lg:order-3">
          {/* 주요 정류장 정보 */}
          <Card className={`shadow-lg border-0 ${
            selectedPattern === "weekend" ? "bg-gradient-to-br from-blue-50 to-blue-100" :
            selectedPattern === "night" ? "bg-gradient-to-br from-purple-50 to-purple-100" :
            selectedPattern === "underutilized" ? "bg-gradient-to-br from-red-50 to-red-100" :
            selectedPattern === "lunchtime" ? "bg-gradient-to-br from-green-50 to-green-100" :
            selectedPattern === "rushhour" ? "bg-gradient-to-br from-orange-50 to-orange-100" :
            selectedPattern === "areatype" ? "bg-gradient-to-br from-sky-50 to-sky-100" :
            "bg-gradient-to-br from-green-50 to-emerald-50"
          }`}>
            <CardHeader className="pb-6">
              <CardTitle className="text-2xl font-bold flex items-center gap-3 text-gray-800">
                <img src="/heatmap_icon/정류장(월별)_히트맵.png" alt="정류장 월별" className="h-7 w-7" />
                {selectedPattern ? (
                  <>
                    {selectedPattern === "weekend" && "주말 우세"}
                    {selectedPattern === "night" && "심야 고수요"}
                    {selectedPattern === "underutilized" && "저활용"}
                    {selectedPattern === "lunchtime" && "점심시간"}
                    {selectedPattern === "rushhour" && "러시아워"}
                    {selectedPattern === "areatype" && "지역 특성"}
                  </>
                ) : selectedDistrict ? (
                  `${selectedDistrict} 주요 정류장 (월별)`
                ) : (
                  "서울시 주요 정류장 (월별)"
                )}
                <HelpTooltip>
                  <HelpTooltipTrigger asChild>
                    <button className="text-gray-400 hover:text-gray-600 transition-colors">
                      <HelpCircle size={16} />
                    </button>
                  </HelpTooltipTrigger>
                  <HelpTooltipContent 
                    side="top" 
                    className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                  >
                    {(() => {
                      if (selectedPattern === "weekend") {
                        return "주말에 평일보다 높은 교통량을 보이는 정류장들입니다. 관광지, 쇼핑몰, 공원 등 여가시설 접근 정류장이 주를 이룹니다.";
                      } else if (selectedPattern === "night") {
                        return "심야시간(22:00~05:00)에도 높은 승차 수요를 보이는 정류장들입니다. 유흥가, 24시간 시설, 교통허브 근처가 대부분입니다.";
                      } else if (selectedPattern === "underutilized") {
                        return "이용률이 저조한 정류장들로 운영 효율성이 낮습니다. 노선 개선이나 정류장 통폐합 검토가 필요한 지역입니다.";
                      } else if (selectedPattern === "lunchtime") {
                        return "점심시간(11:00~14:00)에 특히 높은 하차 수요를 보이는 정류장들입니다. 업무지구, 상업지역, 대학가가 주를 이룹니다.";
                      } else if (selectedPattern === "rushhour") {
                        return "출퇴근 시간대에 매우 높은 교통 집중을 보이는 정류장들입니다. 오전(07-09시)과 오후(17-19시)로 구분하여 보여줍니다.";
                      } else if (selectedPattern === "areatype") {
                        return "지역 특성에 따라 구분된 정류장들입니다. 주거지역은 오전 승차가, 업무지역은 오전 하차가 많은 특징을 보입니다.";
                      } else if (selectedDistrict) {
                        return `${selectedDistrict}에서 가장 이용량이 많은 상위 정류장들입니다. 해당 구의 주요 교통 허브와 집중 지역을 파악할 수 있습니다.`;
                      } else {
                        return "서울시 전체에서 교통량이 가장 많은 상위 정류장들입니다. 서울의 주요 교통 허브와 핫스팟을 보여줍니다.";
                      }
                    })()}
                  </HelpTooltipContent>
                </HelpTooltip>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                {(() => {
                  let displayStations = [];

                  if (selectedPattern && patternStations.length > 0) {
                    // 패턴 선택시: 해당 패턴의 정류장들
                    if (selectedPattern === "rushhour") {
                      // 러시아워는 오전/오후로 구분해서 표시 (각각 5개씩)
                      const morningStations = patternStations
                        .filter(
                          (station: any) => station.rushType === "morning"
                        )
                        .slice(0, 5)
                        .map((station: any) => ({
                          ...station,
                          displayValue:
                            station.patternInfo ||
                            `${
                              station.total_traffic?.toLocaleString() || "N/A"
                            }명`,
                          color: "text-orange-600",
                          sectionLabel: "🌅 오전",
                        }));

                      const eveningStations = patternStations
                        .filter(
                          (station: any) => station.rushType === "evening"
                        )
.slice(0, 5)
                        .map((station: any) => ({
                          ...station,
                          displayValue:
                            station.patternInfo ||
                            `${
                              station.total_traffic?.toLocaleString() || "N/A"
                            }명`,
                          color: "text-red-600",
                          sectionLabel: "🌆 오후",
                        }));

                      displayStations = [
                        ...morningStations,
                        ...eveningStations,
                      ];
                    } else if (selectedPattern === "areatype") {
                      // 지역 특성은 주거지역/업무지역으로 구분해서 표시 (각각 5개씩)
                      const residentialStations = patternStations
                        .filter(
                          (station: any) => station.areaType === "residential"
                        )
                        .slice(0, 5)
                        .map((station: any) => ({
                          ...station,
                          displayValue:
                            station.patternInfo ||
                            `${
                              station.total_traffic?.toLocaleString() || "N/A"
                            }명`,
                          color: "text-sky-600",
                          sectionLabel: "🏠 주거지역",
                        }));

                      const businessStations = patternStations
                        .filter(
                          (station: any) => station.areaType === "business"
                        )
                        .slice(0, 5)
                        .map((station: any) => ({
                          ...station,
                          displayValue:
                            station.patternInfo ||
                            `${
                              station.total_traffic?.toLocaleString() || "N/A"
                            }명`,
                          color: "text-purple-600",
                          sectionLabel: "🏢 업무지역",
                        }));

                      displayStations = [
                        ...residentialStations,
                        ...businessStations,
                      ];
                    } else {
                      // 다른 패턴들은 기존 방식
                      displayStations = patternStations
                        .slice(0, 5)
                        .map((station: any) => ({
                          ...station,
                          displayValue:
                            station.patternInfo ||
                            `${
                              station.total_traffic?.toLocaleString() || "N/A"
                            }명`,
                          color: station.patternColor || "text-blue-600",
                        }));
                    }
                  } else if (selectedDistrict) {
                    // 구 선택시: 해당 구의 TOP 5 정류장
                    const districtData = filteredDistricts.find(
                      (d) => d.district_name === selectedDistrict
                    );
                    displayStations =
                      districtData?.stations
                        ?.sort((a, b) => b.total_traffic - a.total_traffic)
                        .slice(0, 5)
                        .map((station) => ({
                          ...station,
                          displayValue: `${station.total_traffic.toLocaleString()}명/월`,
                          color: "text-green-600",
                        })) || [];
                  } else {
                    // 전체 선택시: 전체 TOP 5 정류장
                    displayStations = topStations
                      .slice(0, 5)
                      .map((station) => ({
                        ...station,
                        displayValue: `${station.total_traffic.toLocaleString()}명/월`,
                        color: "text-green-600",
                        district_name: heatmapData?.districts.find((d) =>
                          d.stations?.some(
                            (s) => s.station_id === station.station_id
                          )
                        )?.district_name,
                      }));
                  }

                  return displayStations.length > 0 ? (
                    selectedPattern === "rushhour" ? (
                      // 러시아워는 오전/오후 섹션으로 구분 표시
                      <div className="space-y-4">
                        {/* 오전 러시아워 섹션 */}
                        {displayStations.filter(
                          (station: any) => station.sectionLabel === "🌅 오전"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-orange-600 mb-2 flex items-center gap-1">
                              🌅 오전 러시아워 (07-09시)
                            </h5>
                            <div className="space-y-2">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🌅 오전"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(station, displayStations.filter((s: any) => s.sectionLabel === station.sectionLabel));
                                  return (
                                    <div
                                      key={station.station_id}
                                      className="flex items-center justify-between p-2 bg-orange-50 rounded"
                                    >
                                      <div className="flex items-center gap-2">
                                        <div className="text-base font-bold text-orange-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId} • {stationFormat.districtInfo}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="text-right">
                                        <div className="font-medium text-base text-orange-600">
                                          {station.displayValue}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}

                        {/* 오후 러시아워 섹션 */}
                        {displayStations.filter(
                          (station: any) => station.sectionLabel === "🌆 오후"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-1">
                              🌆 오후 러시아워 (17-19시)
                            </h5>
                            <div className="space-y-2">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🌆 오후"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(station, displayStations.filter((s: any) => s.sectionLabel === station.sectionLabel));
                                  return (
                                    <div
                                      key={station.station_id}
                                      className="flex items-center justify-between p-2 bg-red-50 rounded"
                                    >
                                      <div className="flex items-center gap-2">
                                        <div className="text-base font-bold text-red-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId} • {stationFormat.districtInfo}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="text-right">
                                        <div className="font-medium text-base text-red-600">
                                          {station.displayValue}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : selectedPattern === "areatype" ? (
                      // 지역 특성은 주거지역/업무지역 섹션으로 구분 표시
                      <div className="space-y-4">
                        {/* 주거지역 섹션 */}
                        {displayStations.filter(
                          (station: any) => station.sectionLabel === "🏠 주거지역"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-sky-600 mb-2 flex items-center gap-1">
                              🏠 주거지역 (오전 출근 집중)
                            </h5>
                            <div className="space-y-2">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🏠 주거지역"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(station, displayStations.filter((s: any) => s.sectionLabel === station.sectionLabel));
                                  return (
                                    <div
                                      key={station.station_id}
                                      className="flex items-center justify-between p-2 bg-sky-50 rounded"
                                    >
                                      <div className="flex items-center gap-2">
                                        <div className="text-base font-bold text-sky-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId} • {stationFormat.districtInfo}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="text-right">
                                        <div className="font-medium text-base text-sky-600">
                                          {station.displayValue}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}

                        {/* 업무지역 섹션 */}
                        {displayStations.filter(
                          (station: any) => station.sectionLabel === "🏢 업무지역"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-purple-600 mb-2 flex items-center gap-1">
                              🏢 업무지역 (오전 출근 하차)
                            </h5>
                            <div className="space-y-2">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🏢 업무지역"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(station, displayStations.filter((s: any) => s.sectionLabel === station.sectionLabel));
                                  return (
                                    <div
                                      key={station.station_id}
                                      className="flex items-center justify-between p-2 bg-purple-50 rounded"
                                    >
                                      <div className="flex items-center gap-2">
                                        <div className="text-base font-bold text-purple-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId} • {stationFormat.districtInfo}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="text-right">
                                        <div className="font-medium text-base text-purple-600">
                                          {station.displayValue}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      // 다른 패턴들은 기존 방식
                      displayStations.map((station: any, index: number) => {
                        const stationFormat = formatStationName(station, displayStations);
                        const isTop3 = index < 3;
                        const rankColors = ["bg-gradient-to-r from-yellow-400 to-yellow-500", "bg-gradient-to-r from-gray-300 to-gray-400", "bg-gradient-to-r from-amber-600 to-amber-700"];
                        const rankTextColors = ["text-yellow-800", "text-gray-800", "text-amber-100"];
                        
                        return (
                          <div
                            key={station.station_id}
                            className={`flex items-center justify-between p-3 rounded-lg border-l-4 ${
                              isTop3 
                                ? `bg-gradient-to-r ${rankColors[index]?.replace('bg-gradient-to-r ', '') || 'from-blue-100 to-blue-200'} border-l-yellow-500 shadow-md`
                                : `bg-gray-50 border-l-gray-300 hover:bg-gray-100 transition-colors`
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`relative flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
                                isTop3 
                                  ? `${rankTextColors[index] || 'text-white'} ${rankColors[index] || 'bg-blue-500'} shadow-sm`
                                  : 'bg-white text-gray-600 border-2 border-gray-300'
                              }`}>
                                {index + 1}
                                {index === 0 && <span className="absolute -top-1 -right-1 text-xs">🏆</span>}
                                {index === 1 && <span className="absolute -top-1 -right-1 text-xs">🥈</span>}
                                {index === 2 && <span className="absolute -top-1 -right-1 text-xs">🥉</span>}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className={`font-medium truncate ${isTop3 ? 'text-gray-900 text-base' : 'text-gray-800 text-sm'}`}>
                                  {stationFormat.displayName}
                                </div>
                                <div className={`truncate ${isTop3 ? 'text-gray-700 text-sm' : 'text-gray-600 text-xs'}`}>
                                  {stationFormat.showFullId ? (
                                    <>ID: {stationFormat.fullId} • {stationFormat.districtInfo}</>
                                  ) : (
                                    stationFormat.districtInfo
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`font-bold ${
                                isTop3 ? 'text-gray-900 text-lg' : 'text-gray-700 text-base'
                              }`}>
                                {station.displayValue}
                              </div>
                            </div>
                          </div>
                        );
                      })
                    )
                  ) : (
                    <div className="text-center py-6 text-gray-500 text-base">
                      {selectedPattern
                        ? "패턴 데이터 로딩 중..."
                        : viewMode === "station"
                        ? "정류장 데이터 로딩 중..."
                        : "정류장별 모드를 선택하세요"}
                    </div>
                  );
                })()}
              </div>
            </CardContent>
          </Card>

          {/* 통계 */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-2xl font-bold flex items-center gap-3">
                <img src="/heatmap_icon/통계_히트맵.png" alt="통계" className="h-6 w-6" />
                {selectedPattern
                  ? "패턴별 통계"
                  : selectedDistrict
                  ? `${selectedDistrict} 통계`
                  : "핵심 통계"}
                <HelpTooltip>
                  <HelpTooltipTrigger asChild>
                    <button className="text-gray-400 hover:text-gray-600 transition-colors">
                      <HelpCircle size={16} />
                    </button>
                  </HelpTooltipTrigger>
                  <HelpTooltipContent 
                    side="top" 
                    className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                  >
                    {(() => {
                      if (selectedPattern === "weekend") {
                        return "주말 우세 패턴의 통계 정보입니다. 주말 특화 정류장 수와 최고 교통량, 평일 대비 증가율을 확인할 수 있습니다.";
                      } else if (selectedPattern === "night") {
                        return "심야 고수요 패턴의 통계 정보입니다. 심야시간 운영이 필요한 정류장 현황과 최고 승차량을 보여줍니다.";
                      } else if (selectedPattern === "underutilized") {
                        return "저활용 정류장의 통계 정보입니다. 운영 효율성이 낮은 정류장 수와 평균 효율성, 개선 필요도를 확인할 수 있습니다.";
                      } else if (selectedPattern === "lunchtime") {
                        return "점심시간 특화 패턴의 통계 정보입니다. 점심시간 특화 정류장 수와 최고 하차량, 상업지역 집중도를 보여줍니다.";
                      } else if (selectedPattern === "rushhour") {
                        return "러시아워 패턴의 상세 통계입니다. 오전/오후 평균 교통량, 비율, 최고 교통량 등 동적으로 계산된 지표들을 확인할 수 있습니다.";
                      } else if (selectedPattern === "areatype") {
                        return "지역 특성 패턴의 상세 통계입니다. 주거/업무지역 평균 교통량, 교통 방향성 지수, 지역구분 명확도 등을 확인할 수 있습니다.";
                      } else if (selectedDistrict) {
                        return `${selectedDistrict}의 교통 현황을 요약한 통계입니다. 총 정류장 수, 교통량, 승하차 비율 등 구 단위 핵심 지표를 제공합니다.`;
                      } else {
                        return "서울시 전체의 교통 현황을 요약한 핵심 통계입니다. 총 교통량, 평균 승하차 비율, 최대 구 교통량 등을 확인할 수 있습니다.";
                      }
                    })()}
                  </HelpTooltipContent>
                </HelpTooltip>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-4">
                {selectedPattern ? (
                  // 패턴별 통계
                  <>
                    {selectedPattern === "weekend" && weekendData && (
                      <>
                        <div className="flex justify-between p-4 bg-blue-50 rounded">
                          <span className="text-lg font-medium">주말 특화 정류장:</span>
                          <span className="font-bold text-blue-600 text-lg">
                            {weekendData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-blue-50 rounded">
                          <span className="text-base">최고 주말 교통량:</span>
                          <span className="font-bold text-blue-600 text-base">
                            {weekendData.data?.[0]?.weekend_total_traffic?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-blue-50 rounded">
                          <span className="text-base">평일 대비:</span>
                          <span className="font-bold text-blue-600 text-base">
                            +15.2%
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "night" && nightData && (
                      <>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-lg font-medium">심야 고수요:</span>
                          <span className="font-bold text-purple-600 text-lg">
                            {nightData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-base">최고 심야 승차:</span>
                          <span className="font-bold text-purple-600 text-base">
                            {nightData.data?.[0]?.total_night_ride?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-base">운영 필요도:</span>
                          <span className="font-bold text-purple-600 text-base">
                            높음
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "underutilized" &&
                      underutilizedData && (
                        <>
                          <div className="flex justify-between p-4 bg-red-50 rounded">
                            <span className="text-lg font-medium">저활용 정류장:</span>
                            <span className="font-bold text-red-600 text-lg">
                              {underutilizedData.data?.length || 0}개
                            </span>
                          </div>
                          <div className="flex justify-between p-4 bg-red-50 rounded">
                            <span className="text-base">평균 효율성:</span>
                            <span className="font-bold text-red-600 text-base">
                              {underutilizedData.data?.[0]?.efficiency_score ||
                                "N/A"}
                              %
                            </span>
                          </div>
                          <div className="flex justify-between p-4 bg-red-50 rounded">
                            <span className="text-base">개선 필요도:</span>
                            <span className="font-bold text-red-600 text-base">
                              높음
                            </span>
                          </div>
                        </>
                      )}

                    {selectedPattern === "lunchtime" && lunchTimeData && (
                      <>
                        <div className="flex justify-between p-4 bg-green-50 rounded">
                          <span className="text-lg font-medium">점심시간 특화:</span>
                          <span className="font-bold text-green-600 text-lg">
                            {lunchTimeData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-green-50 rounded">
                          <span className="text-base">최고 점심 하차:</span>
                          <span className="font-bold text-green-600 text-base">
                            {lunchTimeData.data?.[0]?.total_lunch_alight?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-green-50 rounded">
                          <span className="text-base">상업지역 집중:</span>
                          <span className="font-bold text-green-600 text-base">
                            높음
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "rushhour" && rushHourData && (
                      <>
                        <div className="flex justify-between p-4 bg-orange-50 rounded">
                          <span className="text-lg font-medium">평균 오전 교통량:</span>
                          <span className="font-bold text-orange-600 text-lg">
                            {(() => {
                              const morningTotal = rushHourData.data?.morning_rush?.reduce(
                                (sum: number, item: any) => sum + (item.total_morning_rush || 0), 0
                              ) || 0;
                              const morningCount = rushHourData.data?.morning_rush?.length || 1;
                              return Math.round(morningTotal / morningCount).toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-red-50 rounded">
                          <span className="text-lg font-medium">평균 오후 교통량:</span>
                          <span className="font-bold text-red-600 text-lg">
                            {(() => {
                              const eveningTotal = rushHourData.data?.evening_rush?.reduce(
                                (sum: number, item: any) => sum + (item.total_evening_rush || 0), 0
                              ) || 0;
                              const eveningCount = rushHourData.data?.evening_rush?.length || 1;
                              return Math.round(eveningTotal / eveningCount).toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-base">오전/오후 비율:</span>
                          <span className="font-bold text-purple-600 text-base">
                            {(() => {
                              const morningTotal = rushHourData.data?.morning_rush?.reduce(
                                (sum: number, item: any) => sum + (item.total_morning_rush || 0), 0
                              ) || 0;
                              const eveningTotal = rushHourData.data?.evening_rush?.reduce(
                                (sum: number, item: any) => sum + (item.total_evening_rush || 0), 0
                              ) || 0;
                              if (eveningTotal === 0) return "N/A";
                              return (morningTotal / eveningTotal).toFixed(2) + ":1";
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-gray-50 rounded">
                          <span className="text-base">최고 러시 교통량:</span>
                          <span className="font-bold text-gray-600 text-base">
                            {(() => {
                              const morningMax = Math.max(
                                ...(rushHourData.data?.morning_rush?.map((item: any) => item.total_morning_rush || 0) || [0])
                              );
                              const eveningMax = Math.max(
                                ...(rushHourData.data?.evening_rush?.map((item: any) => item.total_evening_rush || 0) || [0])
                              );
                              return Math.max(morningMax, eveningMax).toLocaleString();
                            })()}명
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "areatype" && areaTypeData && (
                      <>
                        <div className="flex justify-between p-4 bg-sky-50 rounded">
                          <span className="text-lg font-medium">주거지역 평균 승차:</span>
                          <span className="font-bold text-sky-600 text-lg">
                            {(() => {
                              const residentialTotal = areaTypeData.data?.residential_stations?.reduce(
                                (sum: number, item: any) => sum + (item.morning_ride || 0), 0
                              ) || 0;
                              const residentialCount = areaTypeData.data?.residential_stations?.length || 1;
                              return Math.round(residentialTotal / residentialCount).toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-lg font-medium">업무지역 평균 하차:</span>
                          <span className="font-bold text-purple-600 text-lg">
                            {(() => {
                              const businessTotal = areaTypeData.data?.business_stations?.reduce(
                                (sum: number, item: any) => sum + (item.morning_alight || 0), 0
                              ) || 0;
                              const businessCount = areaTypeData.data?.business_stations?.length || 1;
                              return Math.round(businessTotal / businessCount).toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-indigo-50 rounded">
                          <span className="text-base">교통 방향성 지수:</span>
                          <span className="font-bold text-indigo-600 text-base">
                            {(() => {
                              const residentialRide = areaTypeData.data?.residential_stations?.reduce(
                                (sum: number, item: any) => sum + (item.morning_ride || 0), 0
                              ) || 0;
                              const businessAlight = areaTypeData.data?.business_stations?.reduce(
                                (sum: number, item: any) => sum + (item.morning_alight || 0), 0
                              ) || 0;
                              const total = residentialRide + businessAlight;
                              if (total === 0) return "N/A";
                              const directionality = Math.min(residentialRide, businessAlight) / Math.max(residentialRide, businessAlight);
                              return (directionality * 100).toFixed(1) + "%";
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-teal-50 rounded">
                          <span className="text-base">지역구분 명확도:</span>
                          <span className="font-bold text-teal-600 text-base">
                            {(() => {
                              const resCount = areaTypeData.data?.residential_stations?.length || 0;
                              const bizCount = areaTypeData.data?.business_stations?.length || 0;
                              const total = resCount + bizCount;
                              if (total === 0) return "N/A";
                              const balance = Math.abs(resCount - bizCount) / total;
                              return balance > 0.6 ? "매우명확" : balance > 0.3 ? "명확" : "보통";
                            })()}
                          </span>
                        </div>
                      </>
                    )}
                  </>
                ) : selectedDistrict ? (
                  // 선택된 구 통계
                  (() => {
                    const districtData = filteredDistricts.find(
                      (d) => d.district_name === selectedDistrict
                    );
                    return districtData ? (
                      <>
                        <div className="flex justify-between p-4 bg-blue-50 rounded">
                          <span className="text-lg font-medium">총 정류장 수:</span>
                          <span className="font-bold text-blue-600 text-lg">
                            {districtData.stations?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-green-50 rounded">
                          <span className="text-base">
                            {selectedDistrict} 교통량:
                          </span>
                          <span className="font-bold text-green-600 text-base">
                            {districtData.total_traffic.toLocaleString()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-base">승하차 비율:</span>
                          <span className="font-bold text-purple-600 text-base">
                            {districtData.total_alight &&
                            districtData.total_ride
                              ? (
                                  districtData.total_ride /
                                  districtData.total_alight
                                ).toFixed(2) + ":1"
                              : "N/A"}
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="text-center py-4 text-gray-500 text-base">
                        데이터 로딩 중...
                      </div>
                    );
                  })()
                ) : (
                  // 전체 통계
                  <>
                    <div className="flex justify-between p-4 bg-gray-50 rounded">
                      <span className="text-lg font-medium">총 교통량:</span>
                      <span className="font-bold text-lg">
                        {heatmapData?.statistics.total_seoul_traffic.toLocaleString()}
                        명
                      </span>
                    </div>
                    <div className="flex justify-between p-4 bg-blue-50 rounded">
                      <span className="text-base">평균 승하차비율:</span>
                      <span className="font-bold text-blue-600 text-base">
                        {(() => {
                          const totalRide = filteredDistricts.reduce(
                            (sum, d) => sum + (d.total_ride || 0),
                            0
                          );
                          const totalAlight = filteredDistricts.reduce(
                            (sum, d) => sum + (d.total_alight || 0),
                            0
                          );
                          return totalAlight > 0
                            ? (totalRide / totalAlight).toFixed(2)
                            : "N/A";
                        })()}
                      </span>
                    </div>
                    <div className="flex justify-between p-4 bg-gray-50 rounded">
                      <span className="text-base">최대 구 교통량:</span>
                      <span className="font-bold text-base">
                        {heatmapData?.statistics.max_district_traffic.toLocaleString()}
                        명
                      </span>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 패턴 상세 분석 (패턴 선택 시에만 표시) */}
          {selectedPattern && (
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-xl flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  패턴 상세 분석
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="text-base text-gray-600">
                  {`${selectedDistrict || selectedRegion} 지역의 ${selectedPattern} 패턴 분석 결과입니다.`}
                </div>

                {/* 패턴별 간단 요약 */}
                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                  <div className="text-base">
                    {selectedPattern === "weekend" &&
                      "🏖️ 주말 교통량이 평일보다 높은 지역으로 레저·쇼핑 시설이 집중된 특징을 보입니다."}
                    {selectedPattern === "night" &&
                      "🌙 심야시간 대중교통 수요가 높은 지역으로 유흥가, 병원, 교통허브 근처가 주를 이룹니다."}
                    {selectedPattern === "underutilized" &&
                      "⚡ 이용률이 저조한 정류장들로 노선 개선이나 정류장 통폐합 검토가 필요한 지역입니다."}
                    {selectedPattern === "lunchtime" &&
                      "🍽️ 점심시간 특화 정류장으로 업무지구, 대학가, 상업지역에 집중되어 있습니다."}
                    {selectedPattern === "rushhour" &&
                      "🚗 출퇴근 시간대 교통 집중으로 인한 혼잡과 지연이 발생하는 핫스팟 지역입니다."}
                    {selectedPattern === "areatype" &&
                      "🏢 주거지역과 업무지역으로 구분되며 각각 다른 교통 패턴을 보이는 특성이 있습니다."}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
