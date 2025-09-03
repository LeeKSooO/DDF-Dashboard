"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MapPin, Users, Activity, Zap } from "lucide-react";
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
import { useState, useEffect } from "react";
import { apiService, HeatmapResponse } from "@/lib/api";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          "2025-07-01", // 고정 날짜 사용
          true // 정류장 상세 정보 포함
        );

        console.log("📊 Heatmap API response:", heatmapResponse);
        setHeatmapData(heatmapResponse);
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

  // TOP 5 정류장 (선택된 지역에 따라 달라짐)
  const topStations =
    selectedRegion === "전체"
      ? heatmapData?.districts
          .flatMap((d) => d.stations || [])
          .sort((a, b) => b.total_traffic - a.total_traffic)
          .slice(0, 5) || []
      : filteredDistricts[0]?.stations
          ?.sort((a, b) => b.total_traffic - a.total_traffic)
          .slice(0, 5) || [];

  // 구 평균 교통량 계산
  const districtAverageTraffic = heatmapData?.districts.length
    ? heatmapData.districts.reduce((sum, d) => sum + d.total_traffic, 0) /
      heatmapData.districts.length
    : 0;

  // 정류장 증강 배수 계산 (해당 구 평균 대비)
  const getStationAmplificationRatio = (
    stationTraffic: number,
    districtName: string
  ) => {
    const district = heatmapData?.districts.find(
      (d) => d.district_name === districtName
    );
    if (!district || !district.stations?.length) return 0;

    const districtStationAvg =
      district.stations.reduce((sum, s) => sum + s.total_traffic, 0) /
      district.stations.length;
    return districtStationAvg > 0 ? stationTraffic / districtStationAvg : 0;
  };

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

  // KPI 계산 (동적으로 변경)
  const kpiData = [
    // 1. 총 교통량
    {
      title:
        selectedRegion === "전체" ? "총 교통량" : `${selectedRegion} 교통량`,
      value: Math.round(currentData.totalTraffic / 1000000).toFixed(1) + "M",
      subtitle: currentData.regionName,
      income:
        Math.round(currentData.totalTraffic / 1000).toLocaleString() + "K",
      color: "#3B82F6", // 파란색 (총 교통량)
      icon: "🚌",
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
          ? Math.round(districtAverageTraffic / 100) + "00명"
          : Math.round(
              currentData.totalTraffic /
                Math.max(currentData.stationCount, 1) /
                100
            ) + "00명",
      color: "#10B981", // 초록색 (평균)
      icon: "📊",
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
          ? Math.round(
              (heatmapData?.statistics.max_district_traffic || 0) / 100
            ) + "00명"
          : Math.round(
              (filteredDistricts[0]?.stations?.reduce(
                (max, s) => (s.total_traffic > max ? s.total_traffic : max),
                0
              ) || 0) / 100
            ) + "00명",
      color: "#F59E0B", // 주황색 (최대)
      icon: "🔥",
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
          ? Math.round(
              (heatmapData?.statistics.min_district_traffic || 0) / 100
            ) + "00명"
          : Math.round(
              (filteredDistricts[0]?.stations?.reduce(
                (min, s) => (s.total_traffic < min ? s.total_traffic : min),
                Number.MAX_SAFE_INTEGER
              ) || 0) / 100
            ) + "00명",
      color: "#FB7185",
      icon: "📉",
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
      icon: "🚏",
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
      icon: "⚖️",
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
      icon: "🎯",
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
      icon: "📊",
    },
  ];

  // 탭 네비게이션 카드들 (기존 카드 뒤에 추가)
  const navigationCards = [
    {
      title: "교통 패턴 분석",
      value: "24시간",
      subtitle: "주중/주말 패턴",
      income: `피크: 8시, 18시`,
      color: "#8B5CF6",
      icon: "📊",
      tabId: "traffic",
      description: "시간대별 교통 흐름 분석",
    },
    {
      title: "지역별 교통량 분석",
      value: selectedRegion === "전체" ? "25개구" : "정류장별",
      subtitle: "교통량 분포 분석",
      income: "이상 패턴 6가지 분석",
      color: "#F97316",
      icon: "🗺️",
      tabId: "heatmap",
      description: "지역별 교통량 히트맵",
    },
    {
      title: "이상 패턴 분석",
      value: "6가지",
      subtitle: "특수 패턴 랭킹",
      income: "야간/주말/지역별 등",
      color: "#DC2626",
      icon: "⚡",
      tabId: "traffic-analysis",
      description: "교통 패턴 & 최적화",
    },
    {
      title: "DRT 적합성",
      value: selectedRegion === "전체" ? "3모델" : "스코어",
      subtitle: "수요응답형 교통",
      income: "교통취약지/출퇴근/관광",
      color: "#059669",
      icon: "🎯",
      tabId: "drt-analysis",
      description: "DRT 적합도 분석",
    },
    {
      title: "성과 & 리포트",
      value: "월간",
      subtitle: "종합 성과 분석",
      income: "ROI, 정책 제언",
      color: "#7C2D12",
      icon: "📈",
      tabId: "reports",
      description: "성과 및 경제성 평가",
    },
  ];

  // 구별/정류장별 교통량 분포 데이터 (파이 차트용)
  const pieChartData =
    selectedRegion === "전체"
      ? (heatmapData?.districts || [])
          .sort((a, b) => b.total_traffic - a.total_traffic)
          .slice(0, 5)
          .map((district, index) => ({
            name: district.district_name,
            value: Math.round(district.total_traffic / 1000),
            color: kpiColors[index % kpiColors.length],
          }))
      : topStations.map((station, index) => ({
          name: station.station_name,
          value: Math.round(station.total_traffic / 1000),
          color: kpiColors[index % kpiColors.length],
        }));

  // 디버깅을 위한 로그
  console.log("🔍 Pie chart debug:", {
    selectedRegion,
    filteredDistricts: filteredDistricts.length,
    allDistricts: heatmapData?.districts?.length || 0,
    pieChartData: pieChartData.length,
    pieChartDataSample: pieChartData.slice(0, 3),
  });

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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            📋 기본 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpiData.map((kpi, index) => (
              <Card
                key={index}
                className="relative overflow-hidden"
                style={{ backgroundColor: kpi.color + "20" }}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">{kpi.icon}</span>
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
                    <div className="w-16 h-12 opacity-60">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={[
                            { value: 10 },
                            { value: 15 },
                            { value: 12 },
                            { value: 18 },
                          ]}
                        >
                          <Bar dataKey="value" fill={kpi.color} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* 탭 네비게이션 카드들 */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            🎯 상세 분석 바로가기
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {navigationCards.map((card, index) => (
              <Card
                key={`nav-${index}`}
                className="relative overflow-hidden cursor-pointer hover:shadow-lg transition-all duration-200 transform hover:scale-105"
                style={{ backgroundColor: card.color + "20" }}
                onClick={() => onNavigateToTab?.(card.tabId)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">{card.icon}</span>
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
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* 왼쪽: TOP 5 교통량 분포 */}
              <div>
                <h3 className="text-lg font-medium mb-4">
                  📊{" "}
                  {selectedRegion === "전체"
                    ? "상위 5개 구 이용현황"
                    : `${selectedRegion} 상위 5개 정류장`}
                </h3>
                <ResponsiveContainer width="100%" height={450}>
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      outerRadius={180}
                      innerRadius={50}
                      dataKey="value"
                      labelLine={false}
                      label={({
                        name,
                        percent,
                        cx,
                        cy,
                        midAngle,
                        innerRadius,
                        outerRadius,
                      }) => {
                        const RADIAN = Math.PI / 180;
                        const radius =
                          (innerRadius || 0) +
                          ((outerRadius || 0) - (innerRadius || 0)) * 0.5;
                        const x =
                          (cx || 0) +
                          radius * Math.cos(-((midAngle || 0) * RADIAN));
                        const y =
                          (cy || 0) +
                          radius * Math.sin(-((midAngle || 0) * RADIAN));
                        const displayName =
                          selectedRegion === "전체"
                            ? name.split(" ")[0]
                            : name.split(" ")[0];

                        return (
                          <text
                            x={x}
                            y={y}
                            fill="black"
                            textAnchor={x > (cx || 0) ? "start" : "end"}
                            dominantBaseline="central"
                            fontSize="14"
                            fontWeight="bold"
                          >
                            {`${displayName}`}
                            <tspan x={x} dy="1.2em" fontSize="12">
                              {`${((percent || 0) * 100).toFixed(0)}%`}
                            </tspan>
                          </text>
                        );
                      }}
                    >
                      {pieChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value}K명`, "교통량"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* 오른쪽: 교통량 상위 정류장 */}
              <div>
                <h3 className="text-lg font-medium mb-4">
                  🚏{" "}
                  {selectedRegion === "전체"
                    ? "인기 정류장 TOP 5"
                    : `${selectedRegion} 인기 정류장 TOP 5`}
                </h3>
                <div className="space-y-3">
                  {topStations.map((station, index) => {
                    const stationDistrict =
                      selectedRegion === "전체"
                        ? heatmapData?.districts.find((d) =>
                            d.stations?.some(
                              (s) => s.station_id === station.station_id
                            )
                          )
                        : filteredDistricts[0];
                    const amplificationRatio = getStationAmplificationRatio(
                      station.total_traffic,
                      stationDistrict?.district_name || ""
                    );

                    return (
                      <div
                        key={station.station_id}
                        className="flex items-center justify-between p-3 rounded-lg"
                        style={{
                          backgroundColor:
                            kpiColors[index % kpiColors.length] + "20",
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <div className="text-center">
                            <div
                              className="text-base font-bold"
                              style={{
                                color: kpiColors[index % kpiColors.length],
                              }}
                            >
                              #{index + 1}
                            </div>
                          </div>
                          <div>
                            <div className="font-medium">
                              {station.station_name}
                            </div>
                            <div className="text-base text-gray-600">
                              {selectedRegion === "전체"
                                ? stationDistrict?.district_name
                                : selectedRegion}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div
                            className="text-lg font-bold"
                            style={{
                              color: kpiColors[index % kpiColors.length],
                            }}
                          >
                            {amplificationRatio.toFixed(1)}X
                          </div>
                          <div className="text-base text-gray-600">
                            구 내 점유율
                          </div>
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
