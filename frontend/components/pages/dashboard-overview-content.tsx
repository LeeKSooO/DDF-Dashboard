"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MapPin, Users, Activity, Zap } from "lucide-react";
import Image from "next/image";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { useState, useEffect, useMemo, useCallback } from "react";
import { apiService, HeatmapResponse, DistrictData, utils } from "@/lib/api";
import dynamic from "next/dynamic";
import { SparkBar } from "@/components/charts/SparkBar";

// InteractiveMap을 동적으로 로드하여 SSR 문제 방지
const InteractiveMap = dynamic(
  () => import("@/components/dashboard/interactive-map.client").then((mod) => mod.InteractiveMapClient),
  { 
    ssr: false,
    loading: () => (
      <div className="w-full h-[1000px] bg-gradient-to-br from-blue-50 to-green-50 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-600">지도 로딩 중...</p>
        </div>
      </div>
    )
  }
);

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

interface DashboardOverviewContentProps {
  selectedMonth: string;
  selectedRegion: string;
  onNavigateToTab?: (tabId: string) => void;
}

// 색상 팔레트 (참고 이미지와 유사하게)
const kpiColors = [
  "#60A5FA", // 파란색
  "#34D399", // 민트
  "#A78BFA", // 보라색
  "#F87171", // 빨간색
  "#FBBF24", // 노란색
  "#FB7185", // 핑크색
];

export function DashboardOverviewContent({
  selectedMonth,
  selectedRegion,
  onNavigateToTab,
}: DashboardOverviewContentProps) {
  const [heatmapData, setHeatmapData] = useState<HeatmapResponse | null>(null);
  const [districtData, setDistrictData] = useState<DistrictData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlightedStationId, setHighlightedStationId] = useState<string | null>(null);
  const [openPopupStationId, setOpenPopupStationId] = useState<string | null>(null);

  // 부모-자식 상태 루프 차단을 위한 useCallback + identity guards
  const handleStationClick = useCallback((id: string) => {
    setHighlightedStationId(prev => (prev === id ? prev : id));
  }, []);

  const handlePopupToggle = useCallback((id: string | null) => {
    setOpenPopupStationId(prev => (prev === id ? prev : id));
  }, []);

  // 카드 클릭 핸들러
  const handleCardClick = useCallback((stationId: string) => {
    handleStationClick(stationId);
    // 팝업 토글
    setOpenPopupStationId(prev => prev === stationId ? null : stationId);
  }, [handleStationClick]);

  const handleMouseEnter = useCallback((stationId: string) => {
    handleStationClick(stationId);
  }, [handleStationClick]);

  const handleMouseLeave = useCallback(() => {
    setHighlightedStationId(null);
  }, []);

  // API 데이터 로드
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log(
          "📊 Loading dashboard overview data for month:",
          selectedMonth,
          "region:",
          selectedRegion
        );

        const heatmapResponse = await apiService.getSeoulHeatmap(
          utils.formatSelectedMonth(selectedMonth),
          true // 정류장 상세 정보 포함
        );

        console.log("📊 Heatmap API response:", heatmapResponse);
        setHeatmapData(heatmapResponse);

        // 특정 구 선택 시 실제 좌표가 있는 구별 데이터 추가 로드
        if (selectedRegion !== "전체") {
          const districtResponse = await apiService.getDistrictHeatmap(
            selectedRegion,
            utils.formatSelectedMonth(selectedMonth)
          );
          setDistrictData(districtResponse);
        } else {
          setDistrictData(null);
        }
      } catch (err) {
        console.error("🚨 Dashboard API error:", err);
        setError(
          err instanceof Error ? err.message : "Failed to load dashboard data"
        );
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [selectedMonth, selectedRegion]);

  // 선택된 지역에 따른 데이터 필터링
  const filteredDistricts =
    heatmapData?.districts.filter((d) =>
      selectedRegion === "전체" ? true : d.district_name === selectedRegion
    ) || [];

  // TOP 5 정류장 (선택된 지역에 따라 달라짐) - useMemo로 참조 안정화
  const topStations = useMemo(() => {
    if (!heatmapData) return [];
    
    if (selectedRegion === "전체") {
      const allStations = heatmapData.districts
        .flatMap((d) => d.stations || [])
        .sort((a, b) => b.total_traffic - a.total_traffic)
        .slice(0, 5);
      
      console.log("🔍 Seoul TOP 5 stations:", allStations.map(s => ({
        name: s.station_name,
        id: s.station_id,
        coordinate: s.coordinate,
        traffic: s.total_traffic
      })));
      
      // 전체 지역에서도 좌표 형식 변환 (만약 lat/lng 형식이라면)
      return allStations.map(station => {
        if (station.coordinate && typeof (station.coordinate as any).lat === 'number') {
          // lat/lng 형식인 경우 latitude/longitude로 변환
          return {
            ...station,
            coordinate: {
              latitude: (station.coordinate as any).lat,
              longitude: (station.coordinate as any).lng
            }
          };
        }
        // 이미 latitude/longitude 형식이거나 좌표가 없는 경우 그대로 반환
        return station;
      });
    } else {
      // 구별 데이터가 있으면 실제 좌표가 포함된 정류장 데이터 사용
      if (districtData && districtData.stations) {
        console.log("🗺️ Converting district station coordinates from lat/lng to latitude/longitude");
        return districtData.stations
          .map(station => ({
            ...station,
            coordinate: {
              latitude: (station.coordinate as any).lat,
              longitude: (station.coordinate as any).lng
            }
          }))
          .sort((a, b) => b.total_traffic - a.total_traffic)
          .slice(0, 5);
      }
      // fallback to original data
      return filteredDistricts[0]?.stations
        ?.sort((a, b) => b.total_traffic - a.total_traffic)
        .slice(0, 5) || [];
    }
  }, [heatmapData, districtData, selectedRegion, filteredDistricts]);

  // TOP 5 정류장에 대한 표시 이름 생성 - useMemo로 파생값 계산
  const stationDisplayNames = useMemo(() => {
    if (topStations && topStations.length > 0) {
      return utils.getStationDisplayNames(topStations);
    }
    return new Map<string, string>();
  }, [topStations]);


  // 구 평균 교통량 계산
  const districtAverageTraffic = heatmapData?.districts.length
    ? heatmapData.districts.reduce((sum, d) => sum + d.total_traffic, 0) /
      heatmapData.districts.length
    : 0;


  // 선택된 지역에 따른 동적 KPI 계산
  const getCurrentData = () => {
    if (selectedRegion === "전체") {
      // 전체 선택 시 서울시 전체 데이터
      return {
        totalTraffic: heatmapData?.statistics.total_seoul_traffic || 0,
        totalStations: heatmapData?.statistics.total_stations || 0,
        totalRide:
          heatmapData?.districts.reduce(
            (sum, d) => sum + (d.total_ride || 0),
            0
          ) || 0,
        totalAlight:
          heatmapData?.districts.reduce(
            (sum, d) => sum + (d.total_alight || 0),
            0
          ) || 0,
        regionName: "서울시 전체",
        stationCount:
          heatmapData?.districts.reduce(
            (sum, d) => sum + (d.stations?.length || 0),
            0
          ) || 0,
      };
    } else {
      // 특정 구 선택 시 해당 구 데이터
      const selectedDistrict = filteredDistricts[0];
      return {
        totalTraffic: selectedDistrict?.total_traffic || 0,
        totalStations: selectedDistrict?.stations?.length || 0,
        totalRide: selectedDistrict?.total_ride || 0,
        totalAlight: selectedDistrict?.total_alight || 0,
        regionName: selectedRegion,
        stationCount: selectedDistrict?.stations?.length || 0,
      };
    }
  };

  const currentData = getCurrentData();

  // KPI 계산에 필요한 기본 값들을 메모이제이션
  const basicMetrics = useMemo(() => ({
    totalTraffic: currentData.totalTraffic,
    stationCount: currentData.stationCount,
    totalRide: currentData.totalRide,
    totalAlight: currentData.totalAlight,
    regionName: currentData.regionName,
    maxDistrictTraffic: heatmapData?.statistics.max_district_traffic || 0,
    maxDistrictName: heatmapData?.districts.find(
      (d) => d.total_traffic === heatmapData?.statistics.max_district_traffic
    )?.district_name || "최고 수치",
    districtAvg: districtAverageTraffic
  }), [currentData.totalTraffic, currentData.stationCount, currentData.totalRide, currentData.totalAlight, currentData.regionName, heatmapData?.statistics.max_district_traffic, districtAverageTraffic, heatmapData?.districts]);

  // KPI 계산 (동적으로 변경) - useMemo로 메모이제이션하여 무한 렌더링 방지
  const kpiData = useMemo(() => [
    // 1. 총 교통량
    {
      key: "totalTraffic",
      title:
        selectedRegion === "전체" ? "총 교통량" : `${selectedRegion} 교통량`,
      value: Math.round(basicMetrics.totalTraffic / 1000000).toFixed(1) + "M",
      subtitle: basicMetrics.regionName,
      income:
        Math.round(basicMetrics.totalTraffic / 1000).toLocaleString() + "K",
      color: "#3B82F6", // 파란색 (총 교통량)
      icon: <Image src="/icon/총교통량.png" alt="총 교통량" width={20} height={20} />,
    },
    // 2. 평균 구별 교통량
    {
      title:
        selectedRegion === "전체"
          ? "평균 구별 교통량"
          : `${selectedRegion} 평균 정류장 교통량`,
      value:
        selectedRegion === "전체"
          ? Math.round(districtAverageTraffic / 1000).toLocaleString() + "K"
          : Math.round(
              currentData.totalTraffic /
                Math.max(currentData.stationCount, 1) /
                1000
            ).toLocaleString() + "K",
      subtitle: selectedRegion === "전체" ? "25개 구 평균" : "정류장당 평균",
      income:
        selectedRegion === "전체"
          ? Math.round(districtAverageTraffic).toLocaleString() + "명"
          : Math.round(
              currentData.totalTraffic /
                Math.max(currentData.stationCount, 1)
            ).toLocaleString() + "명",
      color: "#10B981", // 초록색 (평균)
      icon: <Image src="/icon/평균구별교통량.png" alt="평균 구별 교통량" width={20} height={20} />,
    },
    // 3. 최대 교통량 구
    {
      title:
        selectedRegion === "전체"
          ? "최대 교통량 구"
          : `${selectedRegion} 최대 정류장`,
      value:
        selectedRegion === "전체"
          ? Math.round(
              (heatmapData?.statistics.max_district_traffic || 0) / 1000
            ).toLocaleString() + "K"
          : Math.round(
              (filteredDistricts[0]?.stations?.reduce(
                (max, s) => (s.total_traffic > max ? s.total_traffic : max),
                0
              ) || 0) / 1000
            ).toLocaleString() + "K",
      subtitle:
        selectedRegion === "전체"
          ? heatmapData?.districts.find(
              (d) =>
                d.total_traffic === heatmapData?.statistics.max_district_traffic
            )?.district_name || "최고 수치"
          : "정류장 최고 수치",
      income:
        selectedRegion === "전체"
          ? (heatmapData?.statistics.max_district_traffic || 0).toLocaleString() + "명"
          : (filteredDistricts[0]?.stations?.reduce(
              (max, s) => (s.total_traffic > max ? s.total_traffic : max),
              0
            ) || 0).toLocaleString() + "명",
      color: "#F59E0B", // 주황색 (최대)
      icon: <Image src="/icon/최대교통량.png" alt="최대 교통량" width={20} height={20} />,
    },
    // 4. 최소 교통량 구 (기존 8번)
    {
      title:
        selectedRegion === "전체"
          ? "최소 교통량 구"
          : `${selectedRegion} 최소 정류장`,
      value:
        selectedRegion === "전체"
          ? Math.round(
              (heatmapData?.statistics.min_district_traffic || 0) / 1000
            ).toLocaleString() + "K"
          : Math.round(
              (filteredDistricts[0]?.stations?.reduce(
                (min, s) => (s.total_traffic < min ? s.total_traffic : min),
                Number.MAX_SAFE_INTEGER
              ) || 0) / 1000
            ).toLocaleString() + "K",
      subtitle:
        selectedRegion === "전체"
          ? heatmapData?.districts.find(
              (d) =>
                d.total_traffic === heatmapData?.statistics.min_district_traffic
            )?.district_name || "최저 수치"
          : "정류장 최저 수치",
      income:
        selectedRegion === "전체"
          ? (heatmapData?.statistics.min_district_traffic || 0).toLocaleString() + "명"
          : (filteredDistricts[0]?.stations?.reduce(
              (min, s) => (s.total_traffic < min ? s.total_traffic : min),
              Number.MAX_SAFE_INTEGER
            ) || 0).toLocaleString() + "명",
      color: "#FB7185",
      icon: <Image src="/icon/최소교통량.png" alt="최소 교통량" width={20} height={20} priority unoptimized />,
    },
    // 5. 총 정류장 수 (기존 4번)
    {
      title:
        selectedRegion === "전체"
          ? "총 정류장 수"
          : `${selectedRegion} 정류장 수`,
      value:
        selectedRegion === "전체"
          ? Math.round(currentData.totalStations / 1000).toFixed(1) + "K"
          : currentData.stationCount.toLocaleString(),
      subtitle: selectedRegion === "전체" ? "버스정류장" : "버스정류장",
      income: currentData.stationCount.toLocaleString() + "개",
      color: "#8B5CF6", // 보라색 (정류장 수)
      icon: <Image src="/icon/총정류장.png" alt="총 정류장 수" width={20} height={20} />,
    },
    // 6. 승하차 비율 (기존 7번)
    {
      title: "승하차 비율",
      value:
        currentData.totalAlight > 0
          ? (currentData.totalRide / currentData.totalAlight).toFixed(2)
          : "0.00",
      subtitle: "승차/하차",
      income: `승차 ${Math.round(
        currentData.totalRide / 1000
      ).toLocaleString()}K / 하차 ${Math.round(
        currentData.totalAlight / 1000
      ).toLocaleString()}K`,
      color: "#EC4899", // 핑크색 (승하차 비율)
      icon: <Image src="/icon/승하차비율.png" alt="승하차 비율" width={20} height={20} />,
    },
    // 7. 교통 집중도 (기존 5번)
    {
      title: "교통 집중도",
      value:
        (() => {
          if (selectedRegion === "전체") {
            // 구별 상위 5개구의 교통량 점유율
            const districts = heatmapData?.districts || [];
            if (districts.length === 0) return "0.0";
            const sortedDistricts = districts.sort(
              (a, b) => b.total_traffic - a.total_traffic
            );
            const top5Traffic = sortedDistricts
              .slice(0, 5)
              .reduce((sum, d) => sum + d.total_traffic, 0);
            const totalTraffic = districts.reduce(
              (sum, d) => sum + d.total_traffic,
              0
            );
            return ((top5Traffic / totalTraffic) * 100).toFixed(1);
          } else {
            // 정류장별 상위 5개 정류장의 점유율
            const stations = filteredDistricts[0]?.stations || [];
            if (stations.length === 0) return "0.0";
            const sortedStations = stations.sort(
              (a, b) => b.total_traffic - a.total_traffic
            );
            const top5Traffic = sortedStations
              .slice(0, Math.min(5, stations.length))
              .reduce((sum, s) => sum + s.total_traffic, 0);
            const totalTraffic = stations.reduce(
              (sum, s) => sum + s.total_traffic,
              0
            );
            return ((top5Traffic / totalTraffic) * 100).toFixed(1);
          }
        })() + "%",
      subtitle:
        selectedRegion === "전체"
          ? "상위 5개구 점유율"
          : "상위 5개 정류장 점유율",
      income: (() => {
        if (selectedRegion === "전체") {
          const districts = heatmapData?.districts || [];
          if (districts.length === 0) return "데이터 없음";
          const sortedDistricts = districts.sort(
            (a, b) => b.total_traffic - a.total_traffic
          );
          const top5Traffic = sortedDistricts
            .slice(0, 5)
            .reduce((sum, d) => sum + d.total_traffic, 0);
          return `상위 5개구: ${Math.round(top5Traffic / 1000000).toFixed(
            1
          )}M명`;
        } else {
          const stations = filteredDistricts[0]?.stations || [];
          if (stations.length === 0) return "데이터 없음";
          const sortedStations = stations.sort(
            (a, b) => b.total_traffic - a.total_traffic
          );
          const top5Traffic = sortedStations
            .slice(0, Math.min(5, stations.length))
            .reduce((sum, s) => sum + s.total_traffic, 0);
          return `상위 5개: ${Math.round(
            top5Traffic / 1000
          ).toLocaleString()}K명`;
        }
      })(),
      color: "#06B6D4", // 청록색 (집중도)
      icon: <Image src="/icon/교통집중도.png" alt="교통 집중도" width={20} height={20} />,
    },
    // 8. 교통 불평등 지수 (기존 6번)
    {
      title: "교통 불평등 지수",
      value:
        (() => {
          if (selectedRegion === "전체") {
            // 구별 최대/최소 교통량 비율
            const districts = heatmapData?.districts || [];
            if (districts.length === 0) return "1.0";
            const traffics = districts
              .map((d) => d.total_traffic)
              .sort((a, b) => b - a);
            const ratio = traffics[0] / traffics[traffics.length - 1];
            return ratio.toFixed(1);
          } else {
            // 정류장별 최대/최소 교통량 비율
            const stations = filteredDistricts[0]?.stations || [];
            if (stations.length === 0) return "1.0";
            const traffics = stations
              .map((s) => s.total_traffic)
              .sort((a, b) => b - a);
            const ratio = traffics[0] / traffics[traffics.length - 1];
            return ratio.toFixed(1);
          }
        })() + ":1",
      subtitle:
        selectedRegion === "전체" ? "구별 격차 비율" : "정류장별 격차 비율",
      income: (() => {
        const value = parseFloat(
          (() => {
            if (selectedRegion === "전체") {
              const districts = heatmapData?.districts || [];
              if (districts.length === 0) return "1.0";
              const traffics = districts
                .map((d) => d.total_traffic)
                .sort((a, b) => b - a);
              return (traffics[0] / traffics[traffics.length - 1]).toFixed(1);
            } else {
              const stations = filteredDistricts[0]?.stations || [];
              if (stations.length === 0) return "1.0";
              const traffics = stations
                .map((s) => s.total_traffic)
                .sort((a, b) => b - a);
              return (traffics[0] / traffics[traffics.length - 1]).toFixed(1);
            }
          })()
        );

        // DRT 필요성 판단 (PDF 기준)
        return value > 10
          ? "DRT 필요성 매우 높음"
          : value > 5
          ? "DRT 필요성 높음"
          : value > 3
          ? "DRT 필요성 보통"
          : "DRT 필요성 낮음";
      })(),
      color: "#E11D48", // 빨간색 (불평등)
      icon: <Image src="/icon/불평등.png" alt="교통 불평등 지수" width={20} height={20} />,
    },
  ], [selectedRegion, basicMetrics, filteredDistricts]);

  // 탭 네비게이션 카드들 (기존 카드 뒤에 추가) - useMemo로 메모이제이션
  const navigationCards = useMemo(() => [
    {
      key: "traffic",
      title: "교통 패턴 분석",
      value: "24시간",
      subtitle: "주중/주말 패턴",
      income: `피크: 8시, 18시`,
      color: "#8B5CF6",
      tabId: "traffic",
      description: "시간대별 교통 흐름 분석",
      icon: <Image src="/navigation_icon/교통패턴분석.png" alt="교통 패턴 분석" width={20} height={20} />,
    },
    {
      key: "heatmap",
      title: "교통량 분석",
      value: selectedRegion === "전체" ? "25개구" : "정류장별",
      subtitle: "교통량 분포 분석",
      income: "이상 패턴 6가지 분석",
      color: "#F97316",
      tabId: "heatmap",
      description: "지역별 교통량 히트맵",
      icon: <Image src="/navigation_icon/교통량분석.png" alt="교통량 분석" width={20} height={20} />,
    },
    {
      key: "traffic-analysis",
      title: "이상 패턴 분석",
      value: "6가지",
      subtitle: "특수 패턴 랭킹",
      income: "야간/주말/지역별 등",
      color: "#DC2626",
      tabId: "traffic-analysis",
      description: "교통 패턴 & 최적화",
      icon: <Image src="/navigation_icon/이상패턴분석.png" alt="이상 패턴 분석" width={20} height={20} />,
    },
    {
      key: "drt-analysis",
      title: "DRT 적합성",
      value: selectedRegion === "전체" ? "3모델" : "스코어",
      subtitle: "수요응답형 교통",
      income: "교통취약지/출퇴근/관광",
      color: "#059669",
      tabId: "drt-analysis",
      description: "DRT 적합도 분석",
      icon: <Image src="/navigation_icon/DRT분석.png" alt="DRT 분석" width={20} height={20} />,
    },
  ], [selectedRegion]);


  // 로딩 상태
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">대시보드 데이터 로딩 중...</p>
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
              <p className="text-base mt-2">{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 기본 KPI 카드 그리드 */}
      <div className="space-y-6">
        {/* 기본 정보 카드들 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Image src="/icon/기본현황.png" alt="기본 현황" width={24} height={24} />
            <h2 className="text-lg font-semibold text-gray-900">
              기본 현황
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpiData.map((kpi) => (
              <Card
                key={kpi.key}
                className="relative overflow-hidden bg-gray-50"
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {kpi.icon || <span className="text-lg">📊</span>}
                        <span className="text-base font-bold text-gray-700">
                          {kpi.title}
                        </span>
                      </div>
                      <div
                        className="text-2xl font-bold"
                        style={{ color: kpi.color }}
                      >
                        {kpi.value}
                      </div>
                      <div className="text-base text-gray-600">
                        {kpi.subtitle}
                      </div>

                      <div className="mt-3">
                        <div className="text-base font-medium text-gray-800">
                          {kpi.income}
                        </div>
                      </div>
                    </div>

                    {/* 오른쪽 미니 차트 영역 (참고 이미지 스타일) */}
                    <SparkBar fill={kpi.color} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* 탭 네비게이션 카드들 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Image src="/icon/상세분석바로가기.png" alt="상세 분석 바로가기" width={24} height={24} />
            <h2 className="text-lg font-semibold text-gray-900">
              상세 분석 바로가기
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {navigationCards.map((card) => (
              <Card
                key={card.key}
                className="relative overflow-hidden cursor-pointer hover:shadow-lg transition-all duration-200 transform hover:scale-105"
                style={{ backgroundColor: card.color + "20" }}
                onClick={() => onNavigateToTab?.(card.tabId)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {card.icon || <span className="text-lg">🎯</span>}
                        <span className="text-base font-bold text-gray-700">
                          {card.title}
                        </span>
                      </div>
                      <div
                        className="text-2xl font-bold"
                        style={{ color: card.color }}
                      >
                        {card.value}
                      </div>
                      <div className="text-base text-gray-600">
                        {card.subtitle}
                      </div>

                      <div className="mt-3">
                        <div className="text-base font-medium text-gray-800">
                          {card.income}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {card.description}
                        </div>
                      </div>
                    </div>

                    {/* 화살표 아이콘 */}
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: card.color + "40" }}
                    >
                      <span className="text-base" style={{ color: card.color }}>
                        →
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* 하단 분석 섹션 */}
      <Card>
        <CardHeader>
          <CardTitle>🚌 교통량 현황</CardTitle>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]}{" "}
            {currentData.regionName} 버스 이용량 분석
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-8">
            {/* 첫 번째 행: 구별 분포와 정류장 랭킹 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 relative">
              {/* 왼쪽: 교통량 지도 */}
              <div className="relative z-10">
                <h3 className="text-lg font-medium mb-4">
                  🗺️{" "}
                  {selectedRegion === "전체"
                    ? "서울시 전체 교통량 현황"
                    : `${selectedRegion} 인기 정류장 지도`}
                </h3>
                <InteractiveMap 
                  selectedRegion={selectedRegion}
                  topStations={topStations}
                  highlightedStationId={highlightedStationId || undefined}
                  onStationClick={handleStationClick}
                  openPopupStationId={openPopupStationId || undefined}
                  onPopupToggle={handlePopupToggle}
                  stationDisplayNames={stationDisplayNames}
                />
              </div>

              {/* 오른쪽: 교통량 상위 정류장 (랭킹 사이트 스타일) */}
              <div className="relative z-50">
                <div className="flex items-center justify-center gap-3 mb-6">
                  <Image src="/icon/인기정류장.png" alt="인기 정류장" width={28} height={28} />
                  <h3 className="text-2xl font-bold">
                    {selectedRegion === "전체" ? "전국" : selectedRegion} 인기 정류장 TOP 5
                  </h3>
                </div>
                <div className="space-y-4">
                  {topStations.map((station, index) => {
                    const stationDistrict =
                      selectedRegion === "전체"
                        ? heatmapData?.districts.find((d) =>
                            d.stations?.some(
                              (s) => s.station_id === station.station_id
                            )
                          )
                        : filteredDistricts[0];
                    
                    // 랭킹별 스타일
                    const getRankStyle = (rank: number) => {
                      switch (rank) {
                        case 0: // 1위
                          return {
                            bgColor: "linear-gradient(135deg, #FFD700 0%, #FFA500 100%)", // 골드
                            textColor: "#8B4513",
                            medal: "🥇",
                            scale: "1.05",
                            shadow: "0 8px 20px rgba(255, 215, 0, 0.3)"
                          };
                        case 1: // 2위
                          return {
                            bgColor: "linear-gradient(135deg, #C0C0C0 0%, #A8A8A8 100%)", // 실버
                            textColor: "#4A4A4A",
                            medal: "🥈",
                            scale: "1.02",
                            shadow: "0 6px 15px rgba(192, 192, 192, 0.3)"
                          };
                        case 2: // 3위
                          return {
                            bgColor: "linear-gradient(135deg, #CD7F32 0%, #B87333 100%)", // 브론즈
                            textColor: "#2C1810",
                            medal: "🥉",
                            scale: "1.01",
                            shadow: "0 4px 12px rgba(205, 127, 50, 0.3)"
                          };
                        default:
                          return {
                            bgColor: "linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%)",
                            textColor: "#374151",
                            medal: `${rank + 1}️⃣`,
                            scale: "1.0",
                            shadow: "0 2px 8px rgba(0, 0, 0, 0.1)"
                          };
                      }
                    };
                    
                    const rankStyle = getRankStyle(index);

                    return (
                      <div
                        key={station.station_id}
                        className={`relative transform transition-all duration-300 cursor-pointer z-50 ${
                          highlightedStationId === station.station_id 
                            ? 'hover:scale-105 scale-105 ring-4 ring-blue-300' 
                            : 'hover:scale-102'
                        } ${
                          openPopupStationId === station.station_id 
                            ? 'ring-2 ring-orange-400' 
                            : ''
                        }`}
                        style={{
                          background: highlightedStationId === station.station_id 
                            ? `linear-gradient(135deg, #FF1493, #FF1493dd)` 
                            : openPopupStationId === station.station_id
                            ? `linear-gradient(135deg, ${rankStyle.bgColor.replace('100%', '80%')}, #FFA500)`
                            : rankStyle.bgColor,
                          transform: highlightedStationId === station.station_id 
                            ? `scale(1.05)` 
                            : `scale(${rankStyle.scale})`,
                          boxShadow: highlightedStationId === station.station_id 
                            ? "0 12px 32px rgba(255, 20, 147, 0.4)" 
                            : openPopupStationId === station.station_id
                            ? "0 8px 24px rgba(255, 165, 0, 0.3)"
                            : rankStyle.shadow,
                          borderRadius: "16px",
                          border: index < 3 ? "3px solid rgba(255, 255, 255, 0.3)" : "2px solid rgba(0, 0, 0, 0.1)"
                        }}
                        onClick={() => handleCardClick(station.station_id)}
                        onMouseEnter={() => handleMouseEnter(station.station_id)}
                        onMouseLeave={handleMouseLeave}
                      >
                        <div className="p-5">
                          <div className="flex items-center justify-between">
                            {/* 왼쪽: 순위와 정보 */}
                            <div className="flex items-center gap-4 flex-1">
                              {/* 메달/순위 */}
                              <div className="text-center">
                                <div className="text-4xl mb-1">
                                  {rankStyle.medal}
                                </div>
                                <div 
                                  className="text-3xl font-black tracking-wider"
                                  style={{ color: rankStyle.textColor }}
                                >
                                  #{index + 1}
                                </div>
                              </div>
                              
                              {/* 정류장 정보 */}
                              <div className="flex-1">
                                <div 
                                  className="text-xl font-bold mb-1 leading-tight"
                                  style={{ color: rankStyle.textColor }}
                                >
                                  {stationDisplayNames.get(station.station_id) || station.station_name}
                                </div>
                                <div 
                                  className="text-xs opacity-60 mb-1"
                                  style={{ color: rankStyle.textColor }}
                                >
                                  ID: {station.station_id}
                                </div>
                                <div 
                                  className="text-lg font-medium opacity-80"
                                  style={{ color: rankStyle.textColor }}
                                >
                                  📍 {selectedRegion === "전체"
                                    ? stationDistrict?.district_name
                                    : selectedRegion}
                                </div>
                                <div 
                                  className="text-base mt-2 font-semibold"
                                  style={{ color: rankStyle.textColor }}
                                >
                                  일일 이용객: {station.total_traffic.toLocaleString()}명
                                </div>
                              </div>
                            </div>

                            {/* 오른쪽: 수치 정보 */}
                            <div className="text-right ml-4">
                              <div 
                                className="text-3xl font-black mb-2"
                                style={{ color: rankStyle.textColor }}
                              >
                                {station.total_traffic > 10000 
                                  ? `${(station.total_traffic / 1000).toFixed(0)}K`
                                  : station.total_traffic.toLocaleString()
                                }
                              </div>
                              <div 
                                className="text-lg font-bold px-3 py-1 rounded-full"
                                style={{ 
                                  color: rankStyle.textColor,
                                  backgroundColor: "rgba(255, 255, 255, 0.3)"
                                }}
                              >
                                {index === 0 ? "🔥 최고" : 
                                 index === 1 ? "⚡ 우수" : 
                                 index === 2 ? "✨ 양호" : 
                                 `TOP ${index + 1}`}
                              </div>
                              <div 
                                className="text-base mt-1 font-medium opacity-90"
                                style={{ color: rankStyle.textColor }}
                              >
                                승차: {(station.total_ride || 0).toLocaleString()}
                              </div>
                              <div 
                                className="text-base font-medium opacity-90"
                                style={{ color: rankStyle.textColor }}
                              >
                                하차: {(station.total_alight || 0).toLocaleString()}
                              </div>
                            </div>
                          </div>
                          
                          {/* 1위 특별 효과 */}
                          {index === 0 && !openPopupStationId && (
                            <div className="absolute -top-1 -right-1">
                              <div className="animate-bounce">
                                <div className="bg-red-500 text-white px-2 py-1 rounded-full text-xs font-bold">
                                  BEST
                                </div>
                              </div>
                            </div>
                          )}
                          
                          {/* 팝업 열린 상태 표시 */}
                          {openPopupStationId === station.station_id && (
                            <div className="absolute -top-1 -right-1">
                              <div className="animate-pulse">
                                <div className="bg-orange-500 text-white px-2 py-1 rounded-full text-xs font-bold flex items-center gap-1">
                                  <span>📍</span>
                                  <span>OPEN</span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
