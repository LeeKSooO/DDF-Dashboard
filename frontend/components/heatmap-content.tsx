"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapPin, Users, Navigation, Activity } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useState, useEffect, useRef } from "react";
import {
  apiService,
  HeatmapResponse,
  DistrictData,
  StationData,
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

        const analysisMonth = "2025-07-01";

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

  // 랭킹을 위한 정렬된 구 데이터
  const rankedDistricts = [...filteredDistricts]
    .sort((a, b) => b.total_traffic - a.total_traffic)
    .map((district, index) => ({ ...district, rank: index + 1 }));

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

        const analysisMonth = "2025-07-01";

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
    <div className="space-y-6">
      {/* 컨트롤 패널 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            서울시 교통량 히트맵 제어판
          </CardTitle>
          <CardDescription>지도 시각화 옵션 및 필터 설정</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-base font-medium">보기 모드:</label>
              <Select
                value={viewMode}
                onValueChange={(value: "district" | "station") =>
                  setViewMode(value)
                }
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="district">구별 집계</SelectItem>
                  <SelectItem value="station">정류장별</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button variant="outline" size="sm" onClick={handleResetMapCenter}>
              <Navigation className="h-4 w-4 mr-2" />
              지도 중심 이동
            </Button>
            {viewMode === "station" && selectedDistrict && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedDistrict(null);
                  setSelectedPattern(null); // 패턴도 함께 초기화
                  console.log("🔄 패턴 선택 초기화 - 전체 정류장 보기");
                }}
                className="ml-2"
              >
                전체 정류장 보기
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 3열 레이아웃: 좌측 패턴 버튼 + 가운데 지도 + 우측 상세정보 */}
      <div className="grid grid-cols-12 gap-6">
        {/* 좌측 - 컴팩트 패턴 탐지 버튼들 */}
        <div className="col-span-2">
          <Card className="h-fit">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2 text-xl">
                <Activity className="h-5 w-5" />
                패턴 탐지
              </CardTitle>
              <CardDescription className="text-base">
                {selectedRegion === "전체" && !selectedDistrict
                  ? "구 선택시 활성화"
                  : `${selectedDistrict || selectedRegion}`}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {selectedRegion === "전체" && !selectedDistrict ? (
                <div className="text-center text-gray-500 py-6">
                  <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-lg">구 선택 필요</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {/* 주말 우세 정류장 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "weekend" ? null : "weekend"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "weekend"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🏖️</span>
                      <span className="text-sm">주말 우세</span>
                      <span className="text-sm opacity-75">
                        {weekendData?.data?.length || 0}개
                      </span>
                    </div>
                  </button>

                  {/* 심야 고수요 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "night" ? null : "night"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "night"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🌙</span>
                      <span className="text-sm">심야 고수요</span>
                      <span className="text-sm opacity-75">
                        {nightData?.data?.length || 0}개
                      </span>
                    </div>
                  </button>

                  {/* 저활용 정류장 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "underutilized"
                          ? null
                          : "underutilized"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "underutilized"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">⚡</span>
                      <span className="text-sm">저활용</span>
                      <span className="text-sm opacity-75">
                        {underutilizedData?.data?.length || 0}개
                      </span>
                    </div>
                  </button>

                  {/* 점심시간 특화 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "lunchtime" ? null : "lunchtime"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "lunchtime"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🍽️</span>
                      <span className="text-sm">점심시간</span>
                      <span className="text-sm opacity-75">
                        {lunchTimeData?.data?.length || 0}개
                      </span>
                    </div>
                  </button>

                  {/* 러시아워 핫스팟 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "rushhour" ? null : "rushhour"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "rushhour"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🚗</span>
                      <span className="text-sm">러시아워</span>
                      <span className="text-sm opacity-75">
                        {(rushHourData?.data?.morning_rush?.length || 0) +
                          (rushHourData?.data?.evening_rush?.length || 0)}
                        개
                      </span>
                    </div>
                  </button>

                  {/* 지역 특성 분석 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(
                        selectedPattern === "areatype" ? null : "areatype"
                      );
                      setViewMode("station");
                    }}
                    className={`w-full p-2 text-base font-medium rounded transition-all ${
                      selectedPattern === "areatype"
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🏢</span>
                      <span className="text-sm">지역 특성</span>
                      <span className="text-sm opacity-75">
                        {(areaTypeData?.data?.residential_stations?.length ||
                          0) +
                          (areaTypeData?.data?.business_stations?.length || 0)}
                        개
                      </span>
                    </div>
                  </button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 가운데 - 메인 히트맵 */}
        <div className="col-span-6">
          <Card>
            <CardHeader>
              <CardTitle>서울시 교통량 히트맵</CardTitle>
              <CardDescription>
                {viewMode === "district" ? "25개 자치구별" : "정류장별"} 교통량
                시각화
              </CardDescription>
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

        {/* 우측 - 상세 정보 (주요 정류장 + 통계 + 상세 분석) */}
        <div className="col-span-4 space-y-4">
          {/* 주요 정류장 */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-xl flex items-center gap-2">
                <Users className="h-4 w-4" />
                {selectedPattern ? (
                  <>
                    {selectedPattern === "weekend" && "🏖️ 주말 우세"}
                    {selectedPattern === "night" && "🌙 심야 고수요"}
                    {selectedPattern === "underutilized" && "⚡ 저활용"}
                    {selectedPattern === "lunchtime" && "🍽️ 점심시간"}
                    {selectedPattern === "rushhour" && "🚗 러시아워"}
                    {selectedPattern === "areatype" && "🏢 지역 특성"}
                  </>
                ) : selectedDistrict ? (
                  `🎯 ${selectedDistrict} 주요`
                ) : (
                  "🌐 서울시 주요"
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                {(() => {
                  let displayStations = [];

                  if (selectedPattern && patternStations.length > 0) {
                    // 패턴 선택시: 해당 패턴의 정류장들
                    if (selectedPattern === "rushhour") {
                      // 러시아워는 오전/오후로 구분해서 표시 (각각 3개씩)
                      const morningStations = patternStations
                        .filter(
                          (station: any) => station.rushType === "morning"
                        )
                        .slice(0, 3)
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
                        .slice(0, 3)
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
                                .map((station: any, index: number) => (
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
                                          {station.station_name}
                                        </div>
                                        <div className="text-sm text-gray-600 truncate">
                                          {station.district_name ||
                                            selectedDistrict ||
                                            "위치정보"}
                                        </div>
                                      </div>
                                    </div>
                                    <div className="text-right">
                                      <div className="font-medium text-base text-orange-600">
                                        {station.displayValue}
                                      </div>
                                    </div>
                                  </div>
                                ))}
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
                                .map((station: any, index: number) => (
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
                                          {station.station_name}
                                        </div>
                                        <div className="text-sm text-gray-600 truncate">
                                          {station.district_name ||
                                            selectedDistrict ||
                                            "위치정보"}
                                        </div>
                                      </div>
                                    </div>
                                    <div className="text-right">
                                      <div className="font-medium text-base text-red-600">
                                        {station.displayValue}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      // 다른 패턴들은 기존 방식
                      displayStations.map((station: any, index: number) => (
                        <div
                          key={station.station_id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`text-base font-bold ${
                                station.color?.replace("text-", "text-") ||
                                "text-blue-600"
                              }`}
                            >
                              #{index + 1}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="font-medium text-base truncate">
                                {station.station_name}
                              </div>
                              <div className="text-sm text-gray-600 truncate">
                                {station.district_name ||
                                  selectedDistrict ||
                                  "위치정보"}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div
                              className={`font-medium text-base ${
                                station.color || "text-green-600"
                              }`}
                            >
                              {station.displayValue}
                            </div>
                          </div>
                        </div>
                      ))
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
              <CardTitle className="text-xl">
                📊{" "}
                {selectedPattern
                  ? "패턴별 통계"
                  : selectedDistrict
                  ? `${selectedDistrict} 통계`
                  : "핵심 통계"}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-2">
                {selectedPattern ? (
                  // 패턴별 통계
                  <>
                    {selectedPattern === "weekend" && weekendData && (
                      <>
                        <div className="flex justify-between p-3 bg-blue-50 rounded">
                          <span className="text-base">주말 특화 정류장:</span>
                          <span className="font-medium text-blue-600 text-base">
                            {weekendData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-blue-50 rounded">
                          <span className="text-sm">최고 주말 교통량:</span>
                          <span className="font-medium text-blue-600 text-sm">
                            {weekendData.data?.[0]?.weekend_total_traffic?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-blue-50 rounded">
                          <span className="text-sm">평일 대비:</span>
                          <span className="font-medium text-blue-600 text-sm">
                            +15.2%
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "night" && nightData && (
                      <>
                        <div className="flex justify-between p-3 bg-purple-50 rounded">
                          <span className="text-sm">심야 고수요:</span>
                          <span className="font-medium text-purple-600 text-sm">
                            {nightData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-purple-50 rounded">
                          <span className="text-sm">최고 심야 승차:</span>
                          <span className="font-medium text-purple-600 text-sm">
                            {nightData.data?.[0]?.total_night_ride?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-purple-50 rounded">
                          <span className="text-sm">운영 필요도:</span>
                          <span className="font-medium text-purple-600 text-sm">
                            높음
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "underutilized" &&
                      underutilizedData && (
                        <>
                          <div className="flex justify-between p-3 bg-red-50 rounded">
                            <span className="text-sm">저활용 정류장:</span>
                            <span className="font-medium text-red-600 text-sm">
                              {underutilizedData.data?.length || 0}개
                            </span>
                          </div>
                          <div className="flex justify-between p-3 bg-red-50 rounded">
                            <span className="text-sm">평균 효율성:</span>
                            <span className="font-medium text-red-600 text-sm">
                              {underutilizedData.data?.[0]?.efficiency_score ||
                                "N/A"}
                              %
                            </span>
                          </div>
                          <div className="flex justify-between p-3 bg-red-50 rounded">
                            <span className="text-sm">개선 필요도:</span>
                            <span className="font-medium text-red-600 text-sm">
                              높음
                            </span>
                          </div>
                        </>
                      )}

                    {selectedPattern === "lunchtime" && lunchTimeData && (
                      <>
                        <div className="flex justify-between p-3 bg-green-50 rounded">
                          <span className="text-sm">점심시간 특화:</span>
                          <span className="font-medium text-green-600 text-sm">
                            {lunchTimeData.data?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-green-50 rounded">
                          <span className="text-sm">최고 점심 하차:</span>
                          <span className="font-medium text-green-600 text-sm">
                            {lunchTimeData.data?.[0]?.total_lunch_alight?.toLocaleString() ||
                              "N/A"}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-green-50 rounded">
                          <span className="text-sm">상업지역 집중:</span>
                          <span className="font-medium text-green-600 text-sm">
                            높음
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "rushhour" && rushHourData && (
                      <>
                        <div className="flex justify-between p-3 bg-orange-50 rounded">
                          <span className="text-sm">🌅 오전 러시아워:</span>
                          <span className="font-medium text-orange-600 text-sm">
                            {rushHourData.data?.morning_rush?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-red-50 rounded">
                          <span className="text-sm">🌆 오후 러시아워:</span>
                          <span className="font-medium text-red-600 text-sm">
                            {rushHourData.data?.evening_rush?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-gray-50 rounded">
                          <span className="text-sm">혼잡도 수준:</span>
                          <span className="font-medium text-gray-600 text-sm">
                            매우높음
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "areatype" && areaTypeData && (
                      <>
                        <div className="flex justify-between p-3 bg-sky-50 rounded">
                          <span className="text-sm">주거지역:</span>
                          <span className="font-medium text-sky-600 text-sm">
                            {areaTypeData.data?.residential_stations?.length ||
                              0}
                            개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-purple-50 rounded">
                          <span className="text-sm">업무지역:</span>
                          <span className="font-medium text-purple-600 text-sm">
                            {areaTypeData.data?.business_stations?.length || 0}
                            개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-blue-50 rounded">
                          <span className="text-sm">특성화도:</span>
                          <span className="font-medium text-blue-600 text-sm">
                            높음
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
                        <div className="flex justify-between p-3 bg-blue-50 rounded">
                          <span className="text-sm">총 정류장 수:</span>
                          <span className="font-medium text-blue-600 text-sm">
                            {districtData.stations?.length || 0}개
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-green-50 rounded">
                          <span className="text-sm">
                            {selectedDistrict} 교통량:
                          </span>
                          <span className="font-medium text-green-600 text-sm">
                            {districtData.total_traffic.toLocaleString()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-3 bg-purple-50 rounded">
                          <span className="text-sm">승하차 비율:</span>
                          <span className="font-medium text-purple-600 text-sm">
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
                      <div className="text-center py-4 text-gray-500 text-sm">
                        데이터 로딩 중...
                      </div>
                    );
                  })()
                ) : (
                  // 전체 통계
                  <>
                    <div className="flex justify-between p-2 bg-gray-50 rounded">
                      <span className="text-sm">총 교통량:</span>
                      <span className="font-medium text-sm">
                        {heatmapData?.statistics.total_seoul_traffic.toLocaleString()}
                        명
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-blue-50 rounded">
                      <span className="text-sm">평균 승하차비율:</span>
                      <span className="font-medium text-blue-600 text-sm">
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
                    <div className="flex justify-between p-2 bg-gray-50 rounded">
                      <span className="text-sm">최대 구 교통량:</span>
                      <span className="font-medium text-sm">
                        {heatmapData?.statistics.max_district_traffic.toLocaleString()}
                        명
                      </span>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 상세 분석 (기존에 하단에 있던 큰 카드 내용을 우측에 컴팩트하게) */}
          {(selectedDistrict || selectedPattern) && (
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-xl flex items-center gap-2">
                  {selectedPattern ? (
                    <>
                      <Activity className="h-4 w-4" />
                      패턴 상세 분석
                    </>
                  ) : (
                    <>
                      <MapPin className="h-4 w-4" />
                      지역 상세 분석
                    </>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="text-base text-gray-600">
                  {selectedPattern
                    ? `${
                        selectedDistrict || selectedRegion
                      } 지역의 ${selectedPattern} 패턴 분석 결과입니다.`
                    : `${selectedDistrict} 지역의 교통량 현황과 주요 특징입니다.`}
                </div>

                {selectedPattern ? (
                  // 패턴별 간단 요약
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <div className="text-base">
                      {selectedPattern === "weekend" &&
                        "🏖️ 주말 교통량이 평일보다 높은 지역으로 레저·쇼핑 시설이 집중된 특징을 보입니다."}
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
                ) : (
                  selectedDistrict && (
                    // 구별 간단 요약
                    <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                      <div className="text-base">
                        {selectedDistrict}는 서울시 25개 자치구 중 교통량 기준
                        상위권 지역으로, 주요 교통 허브 정류장들이 집중되어 있어
                        대중교통 접근성이 우수합니다.
                      </div>
                    </div>
                  )
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
