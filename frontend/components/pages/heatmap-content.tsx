/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/exhaustive-deps */
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
import Image from "next/image";
import {
  Tooltip as HelpTooltip,
  TooltipContent as HelpTooltipContent,
  TooltipProvider,
  TooltipTrigger as HelpTooltipTrigger,
} from "@/components/ui/tooltip";
import { useState, useEffect, useRef } from "react";
import { apiService, HeatmapResponse, utils } from "@/lib/api";
import {
  HeatmapSeoulMap,
  HeatmapSeoulMapRef,
} from "@/components/map/heatmap-seoul-map";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

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
  const [selectedAreaType, setSelectedAreaType] = useState<"residential" | "business">("residential");
  const mapRef = useRef<HeatmapSeoulMapRef>(null);

  // 안정적인 키 생성 유틸
  const stableKey = (s: any, idx: number) => {
    const id = s.station_id ?? s.station?.station_id ?? '';
    const name = s.station_name ?? s.station?.station_name ?? '';
    const rush = s.rushType ?? '';
    const area = s.areaType ?? '';
    const pat = s.patternType ?? selectedPattern ?? '';
    return `${pat}::${rush}::${area}::${id || name}::${idx}`;
  };

  // 안전한 fallback ID 생성
  const fallbackId = (item: any) =>
    item.station?.station_id ??
    `${item.station?.station_name || 'unknown'}:${item.station?.latitude ?? 'x'}:${item.station?.longitude ?? 'y'}`;

  // 패턴별 색상 매핑 (현재 사용하지 않음 - 추후 기능 추가시 활용)
  // const getPatternColor = (pattern: string) => {
  //   const colorMap = {
  //     weekend: "#10B981",     // 주말 - 에메랄드 그린
  //     night: "#8B5CF6",       // 심야 - 보라색
  //     underutilized: "#FBBF24", // 저활용 - 밝은 노란색
  //     lunchtime: "#10B981",   // 점심시간 - 에메랄드 그린
  //     rushhour: "#EC4899",    // 러시아워 - 핑크 (아침) / 보라 (오후)
  //     areatype: "#0EA5E9"     // 지역특성 - 하늘색
  //   };
  //   return colorMap[pattern as keyof typeof colorMap] || "#6B7280";
  // };

  // 패턴별 배경 그라데이션 클래스
  const getPatternBgClass = (pattern: string) => {
    const bgMap = {
      weekend: "bg-gradient-to-r from-emerald-500 to-emerald-600",
      night: "bg-gradient-to-r from-purple-500 to-purple-600", 
      underutilized: "bg-gradient-to-r from-yellow-400 to-yellow-500",
      lunchtime: "bg-gradient-to-r from-emerald-500 to-emerald-600",
      rushhour: "bg-gradient-to-r from-pink-500 to-purple-500",
      areatype: "bg-gradient-to-r from-sky-500 to-sky-600"
    };
    return bgMap[pattern as keyof typeof bgMap] || "bg-gradient-to-r from-gray-500 to-gray-600";
  };

  // 패턴별 카드 배경 클래스 (연한 톤)
  const getPatternCardBgClass = (pattern: string) => {
    const cardBgMap = {
      weekend: "bg-gradient-to-br from-emerald-50 to-emerald-100",
      night: "bg-gradient-to-br from-purple-50 to-purple-100", 
      underutilized: "bg-gradient-to-br from-yellow-50 to-yellow-100",
      lunchtime: "bg-gradient-to-br from-emerald-50 to-emerald-100",
      rushhour: "bg-gradient-to-br from-pink-50 to-purple-100",
      areatype: "bg-gradient-to-br from-sky-50 to-sky-100"
    };
    return cardBgMap[pattern as keyof typeof cardBgMap] || "bg-gradient-to-br from-gray-50 to-gray-100";
  };

  // 패턴별 데이터 가용성 체크
  const underutilizedAvailable = !!(underutilizedData?.success && underutilizedData?.data?.length > 0);

  // API 데이터 로드
  useEffect(() => {
    const loadHeatmapData = async () => {
      try {
        setLoading(true);
        setError(null);


        // 지역이 변경되면 패턴 선택 초기화
        setSelectedPattern(null);

        // 지역 변경 시 패턴 데이터도 초기화
        setWeekendData(null);
        setNightData(null);
        setRushHourData(null);
        setLunchTimeData(null);
        setAreaTypeData(null);
        setUnderutilizedData(null);

        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        // 히트맵 데이터 로드
        const heatmapResponse = await apiService.getSeoulHeatmap(
          analysisMonth,
          true // 항상 정류장 상세 정보 포함
        );

        setHeatmapData(heatmapResponse);

        // 통합 패턴 분석 API 호출 (전체 또는 구별)
        try {
          const integrationResponse = await apiService.getIntegratedPatterns(
            analysisMonth,
            selectedRegion !== "전체" ? selectedRegion : undefined,
            5
          );


          if (integrationResponse?.success && integrationResponse?.data) {
            const d = integrationResponse.data;
            
            // 각 패턴별로 기존 state 형태에 맞게 변환
            setWeekendData(d.weekend_dominant_stations ? { 
              success: true, 
              data: d.weekend_dominant_stations 
            } : null);
            
            setNightData(d.night_demand_stations ? { 
              success: true, 
              data: d.night_demand_stations 
            } : null);
            
            setRushHourData(d.rush_hour_stations ? { 
              success: true, 
              data: d.rush_hour_stations 
            } : null);
            
            setLunchTimeData(d.lunch_time_stations ? { 
              success: true, 
              data: d.lunch_time_stations 
            } : null);
            
            setAreaTypeData(d.area_type_analysis ? { 
              success: true, 
              data: d.area_type_analysis 
            } : null);
            
            setUnderutilizedData(d.underutilized_stations ? { 
              success: true, 
              data: d.underutilized_stations 
            } : null);
          } else {
            // 통합 API 실패시 모든 패턴 데이터 초기화
            setWeekendData(null);
            setNightData(null);
            setRushHourData(null);
            setLunchTimeData(null);
            setAreaTypeData(null);
            setUnderutilizedData(null);
          }
        } catch {
          // 실패해도 UI는 계속 동작하도록
          setWeekendData(null);
          setNightData(null);
          setRushHourData(null);
          setLunchTimeData(null);
          setAreaTypeData(null);
          setUnderutilizedData(null);
        }
      } catch (err) {
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
          weekendData?.success && weekendData?.data?.length > 0 
            ? weekendData.data.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "weekend",
            patternColor: "#3B82F6", // blue
            patternInfo: `주말 교통량: ${item.weekend_total_traffic?.toLocaleString()}명`,
            weekend_total_traffic: item.weekend_total_traffic,
          }))
            : []
        );

      case "night":
        return (
          nightData?.success && nightData?.data?.length > 0
            ? nightData.data.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "night",
            patternColor: "#8B5CF6", // purple
            patternInfo: `심야 승차: ${item.total_night_ride?.toLocaleString()}명`,
            total_night_ride: item.total_night_ride,
          }))
            : []
        );

      case "underutilized":
        return (
          underutilizedData?.success && underutilizedData?.data?.length > 0
            ? underutilizedData.data.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "underutilized",
            patternColor: "#FBBF24", // bright yellow
            patternInfo: `효율성: ${
              item.efficiency_score
            }% | 일평균: ${item.avg_daily_passengers?.toLocaleString()}명`,
            efficiency_score: item.efficiency_score,
            avg_daily_passengers: item.avg_daily_passengers,
          }))
            : []
        );

      case "lunchtime":
        return (
          lunchTimeData?.success && lunchTimeData?.data?.length > 0
            ? lunchTimeData.data.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "lunchtime",
            patternColor: "#10B981", // green
            patternInfo: `점심시간 하차: ${item.total_lunch_alight?.toLocaleString()}명`,
            total_lunch_alight: item.total_lunch_alight,
          }))
            : []
        );

      case "rushhour":
        const morningStations =
          rushHourData?.data?.morning_rush?.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "rushhour",
            patternColor: "#EC4899", // hot pink for morning
            patternInfo: `오전 승차: ${item.total_morning_rush?.toLocaleString()}명`,
            rushType: "morning",
            total_morning_rush: item.total_morning_rush,
          })) || [];

        const eveningStations =
          rushHourData?.data?.evening_rush?.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "rushhour",
            patternColor: "#8B5CF6", // purple for evening
            patternInfo: `오후 승차: ${item.total_evening_rush?.toLocaleString()}명`,
            rushType: "evening",
            total_evening_rush: item.total_evening_rush,
          })) || [];

        return [...morningStations, ...eveningStations];

      case "areatype":
        const residentialStations =
          areaTypeData?.data?.residential_stations?.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "areatype",
            patternColor: "#0EA5E9", // sky blue - 하늘색으로 변경
            patternInfo: `승차: ${item.morning_ride?.toLocaleString()} (오전) | 하차: ${item.evening_alight?.toLocaleString()} (오후) | 불균형: ${item.imbalance_ratio?.toFixed(1)}배`,
            areaType: "residential",
            total_traffic: item.total_traffic,
            imbalance_ratio: item.imbalance_ratio,
            morning_ride: item.morning_ride,
            morning_alight: item.morning_alight,
            evening_ride: item.evening_ride,
            evening_alight: item.evening_alight,
            sectionLabel: "🏠 주거지역",
          })) || [];

        const businessStations =
          areaTypeData?.data?.business_stations?.map((item: any) => ({
            station_id: fallbackId(item),
            station_name: item.station?.station_name,
            latitude: item.station?.latitude,
            longitude: item.station?.longitude,
            district_name: item.station?.district_name,
            administrative_dong: item.station?.administrative_dong,
            patternType: "areatype",
            patternColor: "#8B5CF6", // purple
            patternInfo: `하차: ${item.morning_alight?.toLocaleString()} (오전) | 승차: ${item.evening_ride?.toLocaleString()} (오후) | 불균형: ${item.imbalance_ratio?.toFixed(1)}배`,
            areaType: "business",
            total_traffic: item.total_traffic,
            imbalance_ratio: item.imbalance_ratio,
            morning_ride: item.morning_ride,
            morning_alight: item.morning_alight,
            evening_ride: item.evening_ride,
            evening_alight: item.evening_alight,
            sectionLabel: "🏢 업무지역",
          })) || [];

        return [...residentialStations, ...businessStations];

      default:
        return [];
    }
  };

  const patternStations = getPatternStations();

  // 불균형 비율 파이차트 데이터 생성 함수
  const generatePieChartData = (station: any) => {
    if (station.areaType === "residential") {
      // 주거지역: (출근승차/출근하차) × (퇴근하차/퇴근승차) 비율 시각화
      const morningRide = station.morning_ride || 0;
      const morningAlight = station.morning_alight || 0;
      const eveningRide = station.evening_ride || 0;
      const eveningAlight = station.evening_alight || 0;
      
      // 주거지역 특성 지표들을 비율로 계산
      const morningRatio = morningAlight > 0 ? morningRide / morningAlight : morningRide;
      const eveningRatio = eveningRide > 0 ? eveningAlight / eveningRide : eveningAlight;
      
      const total = morningRatio + eveningRatio;
      if (total === 0) return [];
      
      return [
        { name: "출근승차/출근하차", value: morningRatio, color: "#3B82F6" },
        { name: "퇴근하차/퇴근승차", value: eveningRatio, color: "#10B981" }
      ];
    } else if (station.areaType === "business") {
      // 업무지역: (출근하차/출근승차) × (퇴근승차/퇴근하차) 비율 시각화
      const morningRide = station.morning_ride || 0;
      const morningAlight = station.morning_alight || 0;
      const eveningRide = station.evening_ride || 0;
      const eveningAlight = station.evening_alight || 0;
      
      // 업무지역 특성 지표들을 비율로 계산
      const morningRatio = morningRide > 0 ? morningAlight / morningRide : morningAlight;
      const eveningRatio = eveningAlight > 0 ? eveningRide / eveningAlight : eveningRide;
      
      const total = morningRatio + eveningRatio;
      if (total === 0) return [];
      
      return [
        { name: "출근하차/출근승차", value: morningRatio, color: "#10B981" },
        { name: "퇴근승차/퇴근하차", value: eveningRatio, color: "#3B82F6" }
      ];
    }
    return [];
  };

  // 중복된 정류장 이름을 감지하고 구분 표시하는 함수
  const checkDuplicateStationNames = (stations: any[]) => {
    const nameCount: Record<string, number> = {};
    stations.forEach((station) => {
      nameCount[station.station_name] =
        (nameCount[station.station_name] || 0) + 1;
    });
    return nameCount;
  };

  // 정류장 이름 표시 함수
  const formatStationName = (station: any, allStations: any[]) => {
    const duplicateNames = checkDuplicateStationNames(allStations);
    const isDuplicate = duplicateNames[station.station_name] > 1;

    if (isDuplicate) {
      // 6자리 ID (station_id의 마지막 6자리 또는 전체가 6자리 미만이면 전체)
      const shortId = station.station_id?.toString().slice(-6) || "N/A";
      return {
        displayName: `${station.station_name} (${shortId})`,
        showFullId: true,
        fullId: station.station_id?.toString() || "N/A",
        districtInfo: station.district_name || selectedDistrict || "위치정보",
      };
    }

    return {
      displayName: station.station_name,
      showFullId: false,
      fullId: "",
      districtInfo: station.district_name || selectedDistrict || "위치정보",
    };
  };

  // 지도에서 구 클릭 시 호출
  const handleDistrictClick = (districtName: string) => {
    // 새로운 구를 선택할 때 패턴 선택 초기화
    if (selectedDistrict !== districtName) {
      setSelectedPattern(null);
    }

    setSelectedDistrict(districtName);
  };

  // 지도에서 구 클릭 시 해당 구의 패턴 데이터 로드
  useEffect(() => {
    if (!selectedDistrict) return;

    const loadDistrictPatternData = async () => {
      try {

        // 새로운 구를 클릭할 때 이전 데이터 즉시 초기화
        setWeekendData(null);
        setNightData(null);
        setRushHourData(null);
        setLunchTimeData(null);
        setAreaTypeData(null);
        setUnderutilizedData(null);

        const analysisMonth = utils.formatSelectedMonth(selectedMonth);

        // 통합 패턴 분석 API 호출 (클릭된 구)
        const integrationResponse = await apiService.getIntegratedPatterns(
          analysisMonth,
          selectedDistrict,
          5
        );


        if (integrationResponse?.success && integrationResponse?.data) {
          const d = integrationResponse.data;
          
          // 각 패턴별로 기존 state 형태에 맞게 변환
          setWeekendData(d.weekend_dominant_stations ? { 
            success: true, 
            data: d.weekend_dominant_stations 
          } : null);
          
          setNightData(d.night_demand_stations ? { 
            success: true, 
            data: d.night_demand_stations 
          } : null);
          
          setRushHourData(d.rush_hour_stations ? { 
            success: true, 
            data: d.rush_hour_stations 
          } : null);
          
          setLunchTimeData(d.lunch_time_stations ? { 
            success: true, 
            data: d.lunch_time_stations 
          } : null);
          
          setAreaTypeData(d.area_type_analysis ? { 
            success: true, 
            data: d.area_type_analysis 
          } : null);
          
          setUnderutilizedData(d.underutilized_stations ? { 
            success: true, 
            data: d.underutilized_stations 
          } : null);
        } else {
          // 통합 API 실패시 모든 패턴 데이터 초기화
          setWeekendData(null);
          setNightData(null);
          setRushHourData(null);
          setLunchTimeData(null);
          setAreaTypeData(null);
          setUnderutilizedData(null);
        }
      } catch {
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
          <p className="text-sm text-gray-600">서울시 교통 패턴 시각화</p>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>{monthNames[Number.parseInt(selectedMonth) - 1]}</span>
            {selectedRegion !== "전체" && (
              <>
                <span className="mx-1">•</span>
                <span className="text-blue-600 font-medium">
                  {selectedRegion}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

{/* 2열 레이아웃: 지도 + 우측 상세정보 */}
<div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[800px]">
        {/* 메인 히트맵 시각화 */}
        <div className="lg:col-span-8 order-1">
          <Card className="shadow-xl border-0 bg-gradient-to-br from-gray-50 to-slate-100 overflow-hidden relative">
            <CardHeader className="bg-gray-50/90 backdrop-blur-sm">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <CardTitle className="flex items-center gap-3 text-3xl font-bold text-gray-800">
                    <Image
                      src="/heatmap_icon/지도_히트맵.png"
                      alt="지도 히트맵"
                      className="h-8 w-8"
                      width={32}
                      height={32}
                    />
                    서울시 교통량 히트맵
                  </CardTitle>
                  <CardDescription className="text-lg text-gray-600 mt-1 flex items-center gap-2">
                    {viewMode === "district" ? (
                      <>
                        <Image
                          src="/heatmap_icon/지도_구별_히트맵.png"
                          alt="구별 히트맵"
                          className="h-5 w-5"
                          width={20}
                          height={20}
                        />
                        25개 자치구별
                      </>
                    ) : (
                      <>
                        <Image
                          src="/heatmap_icon/지도_정류장별_히트맵.png"
                          alt="정류장별 히트맵"
                          className="h-5 w-5"
                          width={20}
                          height={20}
                        />
                        정류장별
                      </>
                    )}{" "}
                    교통량 시각화
                  </CardDescription>
                </div>
                {/* 컨트롤 버튼들 - 우측 상단 */}
                <TooltipProvider>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-2">
                      <HelpTooltip>
                        <HelpTooltipTrigger asChild>
                          <Button
                            variant={
                              viewMode === "district" ? "default" : "outline"
                            }
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
                            variant={
                              viewMode === "station" ? "default" : "outline"
                            }
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
                    {((viewMode === "station" && selectedDistrict) ||
                      (viewMode === "district" &&
                        (selectedRegion !== "전체" || selectedDistrict))) && (
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
                          <p>
                            {viewMode === "station"
                              ? "전체 정류장 보기"
                              : "전체 구 보기"}
                          </p>
                        </HelpTooltipContent>
                      </HelpTooltip>
                    )}
                  </div>
                </TooltipProvider>
              </div>
              
              {/* 패턴 분석 버튼들 - 지도 위에 배치 */}
              {(selectedDistrict || selectedRegion !== "전체") && (
                <div className="border-t border-gray-200 pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Activity className="h-4 w-4 text-purple-600" />
                    <span className="text-sm font-semibold text-gray-700">패턴 분석</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {/* 주말 패턴 버튼 */}
                    <button
                      onClick={() => {
                        setSelectedPattern(selectedPattern === "weekend" ? null : "weekend");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "weekend"
                          ? "bg-emerald-500 text-white"
                          : "bg-white text-gray-700 hover:bg-emerald-50 border border-gray-200"
                      }`}
                    >
                      <Image
                        src="/heatmap_icon/주말패턴_히트맵.png"
                        alt="주말 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>주말</span>
                    </button>
                    
                    {/* 심야 패턴 버튼 */}
                    <button
                      onClick={() => {
                        setSelectedPattern(selectedPattern === "night" ? null : "night");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "night"
                          ? "bg-purple-500 text-white"
                          : "bg-white text-gray-700 hover:bg-purple-50 border border-gray-200"
                      }`}
                    >
                      <Image
                        src="/heatmap_icon/심야패턴_히트맵.png"
                        alt="심야 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>심야</span>
                    </button>
                    
                    {/* 저활용 패턴 버튼 */}
                    <button
                      disabled={!underutilizedAvailable}
                      onClick={() => {
                        if (!underutilizedAvailable) return;
                        setSelectedPattern(selectedPattern === "underutilized" ? null : "underutilized");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "underutilized"
                          ? "bg-yellow-500 text-white"
                          : "bg-white text-gray-700 hover:bg-yellow-50 border border-gray-200"
                      } ${!underutilizedAvailable ? "opacity-60 cursor-not-allowed" : ""}`}
                    >
                      <Image
                        src="/heatmap_icon/저활용_히트맵.png"
                        alt="저활용 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>저활용</span>
                    </button>
                    
                    {/* 점심시간 패턴 버튼 */}
                    <button
                      onClick={() => {
                        setSelectedPattern(selectedPattern === "lunchtime" ? null : "lunchtime");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "lunchtime"
                          ? "bg-green-500 text-white"
                          : "bg-white text-gray-700 hover:bg-green-50 border border-gray-200"
                      }`}
                    >
                      <Image
                        src="/heatmap_icon/점심패턴_히트맵.png"
                        alt="점심 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>점심</span>
                    </button>
                    
                    {/* 러시아워 패턴 버튼 */}
                    <button
                      onClick={() => {
                        setSelectedPattern(selectedPattern === "rushhour" ? null : "rushhour");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "rushhour"
                          ? "bg-pink-500 text-white"
                          : "bg-white text-gray-700 hover:bg-pink-50 border border-gray-200"
                      }`}
                    >
                      <Image
                        src="/heatmap_icon/러시아워_히트맵.png"
                        alt="러시아워 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>러시</span>
                    </button>
                    
                    {/* 지역특성 패턴 버튼 */}
                    <button
                      onClick={() => {
                        setSelectedPattern(selectedPattern === "areatype" ? null : "areatype");
                        setViewMode("station");
                      }}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                        selectedPattern === "areatype"
                          ? "bg-sky-500 text-white"
                          : "bg-white text-gray-700 hover:bg-sky-50 border border-gray-200"
                      }`}
                    >
                      <Image
                        src="/heatmap_icon/지역특성_히트맵.png"
                        alt="지역 특성 패턴"
                        className="h-4 w-4"
                        width={16}
                        height={16}
                      />
                      <span>지역</span>
                    </button>
                  </div>
                </div>
              )}
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
          <Card
            className={`shadow-lg border-0 ${
              selectedPattern 
                ? getPatternCardBgClass(selectedPattern)
                : "bg-gradient-to-br from-gray-50 to-slate-100"
            }`}
          >
            <CardHeader className="pb-6">
              <CardTitle className="text-2xl font-bold flex items-center justify-between text-gray-800">
                <div className="flex items-center gap-3">
                  <Image
                    src="/heatmap_icon/정류장(월별)_히트맵.png"
                    alt="정류장 월별"
                    className="h-7 w-7"
                    width={28}
                    height={28}
                  />
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
                </div>
                
                {/* 지역 특성 토글 버튼 */}
                {selectedPattern === "areatype" && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedAreaType("residential")}
                      className={`px-3 py-1 text-sm rounded-full transition-all ${
                        selectedAreaType === "residential"
                          ? "bg-sky-600 text-white"
                          : "bg-white text-gray-600 hover:bg-sky-50 border border-gray-200"
                      }`}
                    >
                      🏠 주거지역
                    </button>
                    <button
                      onClick={() => setSelectedAreaType("business")}
                      className={`px-3 py-1 text-sm rounded-full transition-all ${
                        selectedAreaType === "business"
                          ? "bg-purple-600 text-white"
                          : "bg-white text-gray-600 hover:bg-purple-50 border border-gray-200"
                      }`}
                    >
                      🏢 업무지역
                    </button>
                  </div>
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
                        return "출퇴근 시간대에 매우 높은 교통 집중을 보이는 정류장들입니다. 오전(06-08시)과 오후(17-19시)로 구분하여 보여줍니다.";
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
                              🌅 오전 러시아워 (06-08시)
                            </h5>
                            <div className="space-y-2">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🌅 오전"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(
                                    station,
                                    displayStations.filter(
                                      (s: any) =>
                                        s.sectionLabel === station.sectionLabel
                                    )
                                  );
                                  return (
                                    <div
                                      key={stableKey(station, index)}
                                      className="flex items-center justify-between p-2 bg-orange-50 rounded"
                                    >
                                      <div className="flex items-center justify-center gap-2">
                                        <div className="text-base font-bold text-orange-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>
                                                ID: {stationFormat.fullId} •{" "}
                                                {stationFormat.districtInfo}
                                              </>
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
                                  const stationFormat = formatStationName(
                                    station,
                                    displayStations.filter(
                                      (s: any) =>
                                        s.sectionLabel === station.sectionLabel
                                    )
                                  );
                                  return (
                                    <div
                                      key={stableKey(station, index)}
                                      className="flex items-center justify-between p-2 bg-red-50 rounded"
                                    >
                                      <div className="flex items-center justify-center gap-2">
                                        <div className="text-base font-bold text-red-600">
                                          #{index + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium text-base truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>
                                                ID: {stationFormat.fullId} •{" "}
                                                {stationFormat.districtInfo}
                                              </>
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
                      // 지역 특성은 선택된 타입에 따라 표시
                      <div className="space-y-4">
                        {/* 주거지역 섹션 */}
                        {selectedAreaType === "residential" && displayStations.filter(
                          (station: any) =>
                            station.sectionLabel === "🏠 주거지역"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-sky-600 mb-2 flex items-center gap-1">
                              🏠 주거지역 (오전 출근 승차 집중)
                            </h5>
                            <div className="space-y-3">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🏠 주거지역"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(
                                    station,
                                    displayStations.filter(
                                      (s: any) =>
                                        s.sectionLabel === station.sectionLabel
                                    )
                                  );
                                  return (
                                    <div
                                      key={stableKey(station, index)}
                                      className="bg-white border border-sky-200 rounded-lg shadow-sm"
                                    >
                                      {/* 상단: 순위와 정류장명 */}
                                      <div className="flex items-center gap-3 p-3 border-b border-gray-200 bg-sky-50">
                                        <div className="flex-shrink-0">
                                          <div className="w-6 h-6 bg-sky-600 text-white rounded-full flex items-center justify-center text-xs font-bold">
                                            {index + 1}
                                          </div>
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-bold text-lg text-gray-900 truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>

                                      {/* 2x2 격자 */}
                                      <div className="grid grid-cols-2 h-32">
                                        <div className="bg-blue-50 border-r border-b border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-blue-600 mb-1">승차(오전)</div>
                                            <div className="text-base font-bold text-blue-700">
                                              {station.morning_ride?.toLocaleString() || '-'}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-orange-50 border-b border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-orange-600 mb-1">불균형 점수</div>
                                            <div className="text-base font-bold text-orange-700">
                                              {station.imbalance_ratio?.toFixed(1) || station.displayValue}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-green-50 border-r border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-green-600 mb-1">하차(오후)</div>
                                            <div className="text-base font-bold text-green-700">
                                              {station.evening_alight?.toLocaleString() || '-'}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-white border-gray-200 flex items-center justify-center p-1">
                                          {(() => {
                                            const pieData = generatePieChartData(station);
                                            return pieData.length > 0 ? (
                                              <ResponsiveContainer width="100%" height={50}>
                                                <PieChart>
                                                  <Pie
                                                    data={pieData}
                                                    dataKey="value"
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={8}
                                                    outerRadius={20}
                                                    stroke="none"
                                                  >
                                                    {pieData.map((entry, index) => (
                                                      <Cell key={`cell-${index}`} fill={entry.color} />
                                                    ))}
                                                  </Pie>
                                                </PieChart>
                                              </ResponsiveContainer>
                                            ) : (
                                              <div className="text-xs text-gray-400">데이터 없음</div>
                                            );
                                          })()}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}

                        {/* 업무지역 섹션 */}
                        {selectedAreaType === "business" && displayStations.filter(
                          (station: any) =>
                            station.sectionLabel === "🏢 업무지역"
                        ).length > 0 && (
                          <div>
                            <h5 className="text-sm font-medium text-purple-600 mb-2 flex items-center gap-1">
                              🏢 업무지역 (오후 퇴근 하차 집중)
                            </h5>
                            <div className="space-y-3">
                              {displayStations
                                .filter(
                                  (station: any) =>
                                    station.sectionLabel === "🏢 업무지역"
                                )
                                .map((station: any, index: number) => {
                                  const stationFormat = formatStationName(
                                    station,
                                    displayStations.filter(
                                      (s: any) =>
                                        s.sectionLabel === station.sectionLabel
                                    )
                                  );
                                  return (
                                    <div
                                      key={stableKey(station, index)}
                                      className="bg-white border border-purple-200 rounded-lg shadow-sm"
                                    >
                                      {/* 상단: 순위와 정류장명 */}
                                      <div className="flex items-center gap-3 p-3 border-b border-gray-200 bg-purple-50">
                                        <div className="flex-shrink-0">
                                          <div className="w-6 h-6 bg-purple-600 text-white rounded-full flex items-center justify-center text-xs font-bold">
                                            {index + 1}
                                          </div>
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-bold text-lg text-gray-900 truncate">
                                            {stationFormat.displayName}
                                          </div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {stationFormat.showFullId ? (
                                              <>ID: {stationFormat.fullId}</>
                                            ) : (
                                              stationFormat.districtInfo
                                            )}
                                          </div>
                                        </div>
                                      </div>

                                      {/* 2x2 격자 */}
                                      <div className="grid grid-cols-2 h-32">
                                        <div className="bg-green-50 border-r border-b border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-green-600 mb-1">하차(오전)</div>
                                            <div className="text-base font-bold text-green-700">
                                              {station.morning_alight?.toLocaleString() || '-'}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-orange-50 border-b border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-orange-600 mb-1">불균형 점수</div>
                                            <div className="text-base font-bold text-orange-700">
                                              {station.imbalance_ratio?.toFixed(1) || station.displayValue}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-blue-50 border-r border-gray-200 flex items-center justify-center">
                                          <div className="text-center">
                                            <div className="text-sm text-blue-600 mb-1">승차(오후)</div>
                                            <div className="text-base font-bold text-blue-700">
                                              {station.evening_ride?.toLocaleString() || '-'}
                                            </div>
                                          </div>
                                        </div>
                                        <div className="bg-white border-gray-200 flex items-center justify-center p-1">
                                          {(() => {
                                            const pieData = generatePieChartData(station);
                                            return pieData.length > 0 ? (
                                              <ResponsiveContainer width="100%" height={50}>
                                                <PieChart>
                                                  <Pie
                                                    data={pieData}
                                                    dataKey="value"
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={8}
                                                    outerRadius={20}
                                                    stroke="none"
                                                  >
                                                    {pieData.map((entry, index) => (
                                                      <Cell key={`cell-${index}`} fill={entry.color} />
                                                    ))}
                                                  </Pie>
                                                </PieChart>
                                              </ResponsiveContainer>
                                            ) : (
                                              <div className="text-xs text-gray-400">데이터 없음</div>
                                            );
                                          })()}
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
                        const stationFormat = formatStationName(
                          station,
                          displayStations
                        );
                        const isTop3 = index < 3;
                        const rankColors = [
                          "bg-gradient-to-r from-yellow-400 to-yellow-500",
                          "bg-gradient-to-r from-gray-300 to-gray-400",
                          "bg-gradient-to-r from-amber-600 to-amber-700",
                        ];
                        const rankTextColors = [
                          "text-yellow-800",
                          "text-gray-800",
                          "text-amber-100",
                        ];

                        return (
                          <div
                            key={stableKey(station, index)}
                            className={`flex items-center justify-between p-3 rounded-lg border-l-4 ${
                              isTop3
                                ? `bg-gradient-to-r ${
                                    rankColors[index]?.replace(
                                      "bg-gradient-to-r ",
                                      ""
                                    ) || "from-blue-100 to-blue-200"
                                  } border-l-yellow-500 shadow-md`
                                : `bg-gray-50 border-l-gray-300 hover:bg-gray-100 transition-colors`
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div
                                className={`relative flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
                                  isTop3
                                    ? `${
                                        rankTextColors[index] || "text-white"
                                      } ${
                                        rankColors[index] || "bg-blue-500"
                                      } shadow-sm`
                                    : "bg-white text-gray-600 border-2 border-gray-300"
                                }`}
                              >
                                {index + 1}
                                {index === 0 && (
                                  <span className="absolute -top-1 -right-1 text-xs">
                                    🏆
                                  </span>
                                )}
                                {index === 1 && (
                                  <span className="absolute -top-1 -right-1 text-xs">
                                    🥈
                                  </span>
                                )}
                                {index === 2 && (
                                  <span className="absolute -top-1 -right-1 text-xs">
                                    🥉
                                  </span>
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div
                                  className={`font-medium truncate ${
                                    isTop3
                                      ? "text-gray-900 text-base"
                                      : "text-gray-800 text-sm"
                                  }`}
                                >
                                  {stationFormat.displayName}
                                </div>
                                <div
                                  className={`truncate ${
                                    isTop3
                                      ? "text-gray-700 text-sm"
                                      : "text-gray-600 text-xs"
                                  }`}
                                >
                                  {stationFormat.showFullId ? (
                                    <>
                                      ID: {stationFormat.fullId} •{" "}
                                      {stationFormat.districtInfo}
                                    </>
                                  ) : (
                                    stationFormat.districtInfo
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div
                                className={`font-bold ${
                                  isTop3
                                    ? "text-gray-900 text-lg"
                                    : "text-gray-700 text-base"
                                }`}
                              >
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
                <Image
                  src="/heatmap_icon/통계_히트맵.png"
                  alt="통계"
                  className="h-6 w-6"
                  width={24}
                  height={24}
                />
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
                          <span className="text-lg font-medium">
                            주말 특화 정류장:
                          </span>
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
                          <span className="text-lg font-medium">
                            심야 고수요:
                          </span>
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
                            <span className="text-lg font-medium">
                              저활용 정류장:
                            </span>
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
                          <span className="text-lg font-medium">
                            점심시간 특화:
                          </span>
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
                        <div className="flex justify-between p-4 bg-indigo-50 rounded">
                          <span className="text-base">오전 총 교통량 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-indigo-600 text-base">
                            {(() => {
                              const morningTotal =
                                rushHourData.data?.morning_rush?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.total_morning_rush || 0),
                                  0
                                ) || 0;
                              return morningTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-pink-50 rounded">
                          <span className="text-base">오후 총 교통량 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-pink-600 text-base">
                            {(() => {
                              const eveningTotal =
                                rushHourData.data?.evening_rush?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.total_evening_rush || 0),
                                  0
                                ) || 0;
                              return eveningTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-purple-50 rounded">
                          <span className="text-base">오전/오후 비율:</span>
                          <span className="font-bold text-purple-600 text-base">
                            {(() => {
                              const morningTotal =
                                rushHourData.data?.morning_rush?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.total_morning_rush || 0),
                                  0
                                ) || 0;
                              const eveningTotal =
                                rushHourData.data?.evening_rush?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.total_evening_rush || 0),
                                  0
                                ) || 0;
                              if (eveningTotal === 0) return "N/A";
                              return (
                                (morningTotal / eveningTotal).toFixed(2) + ":1"
                              );
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-gray-50 rounded">
                          <span className="text-base">최고 오전 교통량 <span className="text-xs text-gray-500">(상위기준)</span>:</span>
                          <span className="font-bold text-gray-600 text-base">
                            {(() => {
                              const morningMax = Math.max(
                                ...(rushHourData.data?.morning_rush?.map(
                                  (item: any) => item.total_morning_rush || 0
                                ) || [0])
                              );
                              return morningMax.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-slate-50 rounded">
                          <span className="text-base">최고 오후 교통량 <span className="text-xs text-gray-500">(상위기준)</span>:</span>
                          <span className="font-bold text-slate-600 text-base">
                            {(() => {
                              const eveningMax = Math.max(
                                ...(rushHourData.data?.evening_rush?.map(
                                  (item: any) => item.total_evening_rush || 0
                                ) || [0])
                              );
                              return eveningMax.toLocaleString();
                            })()}명
                          </span>
                        </div>
                      </>
                    )}

                    {selectedPattern === "areatype" && areaTypeData && (
                      <>
                        <div className="flex justify-between p-4 bg-indigo-50 rounded">
                          <span className="text-base">주거지역 총 출근승차 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-indigo-600 text-base">
                            {(() => {
                              const residentialTotal =
                                areaTypeData.data?.residential_stations?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.morning_ride || 0),
                                  0
                                ) || 0;
                              return residentialTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-pink-50 rounded">
                          <span className="text-base">업무지역 총 출근하차 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-pink-600 text-base">
                            {(() => {
                              const businessTotal =
                                areaTypeData.data?.business_stations?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.morning_alight || 0),
                                  0
                                ) || 0;
                              return businessTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-emerald-50 rounded">
                          <span className="text-base">주거지역 총 퇴근하차 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-emerald-600 text-base">
                            {(() => {
                              const residentialTotal =
                                areaTypeData.data?.residential_stations?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.evening_alight || 0),
                                  0
                                ) || 0;
                              return residentialTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-orange-50 rounded">
                          <span className="text-base">업무지역 총 퇴근승차 <span className="text-xs text-gray-500">(상위기준)</span></span>
                          <span className="font-bold text-orange-600 text-base">
                            {(() => {
                              const businessTotal =
                                areaTypeData.data?.business_stations?.reduce(
                                  (sum: number, item: any) =>
                                    sum + (item.evening_ride || 0),
                                  0
                                ) || 0;
                              return businessTotal.toLocaleString();
                            })()}명
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-cyan-50 rounded">
                          <span className="text-base">최고 불균형 비율 <span className="text-xs text-gray-500">(상위기준)</span>:</span>
                          <span className="font-bold text-cyan-600 text-base">
                            {(() => {
                              const allStations = [
                                ...(areaTypeData.data?.residential_stations || []),
                                ...(areaTypeData.data?.business_stations || [])
                              ];
                              if (allStations.length === 0) return "N/A";
                              const maxRatio = Math.max(
                                ...allStations.map(station => station.imbalance_ratio || 0)
                              );
                              return maxRatio.toFixed(1) + ":1";
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between p-4 bg-amber-50 rounded">
                          <span className="text-base">평균 불균형 비율 <span className="text-xs text-gray-500">(상위기준)</span>:</span>
                          <span className="font-bold text-amber-600 text-base">
                            {(() => {
                              const allStations = [
                                ...(areaTypeData.data?.residential_stations || []),
                                ...(areaTypeData.data?.business_stations || [])
                              ];
                              if (allStations.length === 0) return "N/A";
                              const avgRatio = allStations.reduce(
                                (sum, station) => sum + (station.imbalance_ratio || 0),
                                0
                              ) / allStations.length;
                              return avgRatio.toFixed(1) + ":1";
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
                          <span className="text-lg font-medium">
                            총 정류장 수:
                          </span>
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
                  {`${
                    selectedDistrict || selectedRegion
                  } 지역의 ${(() => {
                    switch (selectedPattern) {
                      case "weekend":
                        return "주말";
                      case "night":
                        return "심야";
                      case "underutilized":
                        return "저활용";
                      case "lunchtime":
                        return "점심";
                      case "rushhour":
                        return "러시아워";
                      case "areatype":
                        return "지역 특성";
                      default:
                        return "";
                    }
                  })()} 패턴 분석 결과입니다.`}
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
