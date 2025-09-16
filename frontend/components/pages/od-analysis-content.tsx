"use client";

import { useState, useEffect, useMemo } from "react";
import DeckGL from "@deck.gl/react";
import {
  ArcLayer,
  ScatterplotLayer,
  GeoJsonLayer,
  BitmapLayer,
} from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { MapPin, Clock, AlertTriangle, X, HelpCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ensureFeatureCollection } from "@/lib/geojson-utils";
import {
  odAPI,
  ODAnalysisUtils,
  type TimeBasedOriginAnalysisResponse,
  type DemandSupplyMismatchData,
  type ODPairHourlyAnalysis,
  type Station,
  type TimeBasedOriginAnalysis,
  type DestinationStation,
} from "@/lib/od-api";

// TypeScript interfaces - 2개 분석 모드
interface AnalysisMode {
  type: "time_based" | "mismatch";
  label: string;
  description: string;
}

// 시간대별 분석 데이터
interface TimeAnalysisData {
  morning_peak?: TimeBasedOriginAnalysisResponse;
  evening_peak?: TimeBasedOriginAnalysisResponse;
  daytime?: TimeBasedOriginAnalysisResponse;
  night?: TimeBasedOriginAnalysisResponse;
}

// 미스매치 분석 데이터
interface MismatchAnalysisData {
  data: DemandSupplyMismatchData[];
  loading: boolean;
  error: string | null;
}

interface ODAnalysisContentProps {
  selectedMonth?: string;
}

// 분석 모드 정의 (2개만)
const ANALYSIS_MODES: AnalysisMode[] = [
  {
    type: "time_based",
    label: "시간대별 분석",
    description: "4개 시간대별 출발지 패턴 분석",
  },
  {
    type: "mismatch",
    label: "수요-공급 불균형",
    description: "DRT 도입 필요성 분석 (24시간 상세분석 포함)",
  },
];

// 시간대 정의
const TIME_PERIODS = [
  { key: "morning_peak", label: "출근시간", time: "07-09시", color: "#ef4444" },
  { key: "evening_peak", label: "퇴근시간", time: "17-19시", color: "#f97316" },
  { key: "daytime", label: "주간시간", time: "10-16시", color: "#3b82f6" },
  { key: "night", label: "심야시간", time: "23-06시", color: "#8b5cf6" },
] as const;

// 수요 레벨별 색상
const getDemandLevelColor = (
  demand: number
): [number, number, number, number] => {
  if (demand >= 1000) return [220, 38, 38, 220]; // 고수요 - 빨간색
  if (demand >= 500) return [249, 115, 22, 200]; // 중수요 - 주황색
  if (demand >= 100) return [59, 130, 246, 180]; // 일반 - 파란색
  if (demand >= 50) return [34, 197, 94, 160]; // 저수요 - 초록색
  return [156, 163, 175, 140]; // 카테고리 외 - 회색
};

// 24시간 차트 데이터 포맷팅
const formatHourlyChartData = (
  hourlyPassengers: Record<string, number>,
  dailyAvg: number
) => {
  return Array.from({ length: 24 }, (_, hour) => ({
    hour: `${hour}시`,
    passengers: hourlyPassengers[hour.toString()] || 0,
    평균선: Math.round(dailyAvg / 24),
    hourNumber: hour,
  }));
};

// 패턴 타입별 색상 및 설정
const getPatternTypeConfig = (patternType: string) => {
  const configs = {
    "출근시간 집중형": {
      color: "#ef4444",
      bgColor: "bg-red-100",
      textColor: "text-red-800",
      icon: "🌅",
    },
    "퇴근시간 집중형": {
      color: "#f97316",
      bgColor: "bg-orange-100",
      textColor: "text-orange-800",
      icon: "🌆",
    },
    "주간 분산형": {
      color: "#3b82f6",
      bgColor: "bg-blue-100",
      textColor: "text-blue-800",
      icon: "☀️",
    },
    "균등 분산형": {
      color: "#059669",
      bgColor: "bg-emerald-100",
      textColor: "text-emerald-800",
      icon: "⚖️",
    },
  };
  return configs[patternType as keyof typeof configs] || configs["균등 분산형"];
};

// 서비스 품질 점수별 색상
const getServiceQualityColor = (
  score: number
): [number, number, number, number] => {
  if (score >= 80) return [34, 197, 94, 180]; // 우수 - 초록색
  if (score >= 60) return [59, 130, 246, 180]; // 양호 - 파란색
  if (score >= 40) return [249, 115, 22, 200]; // 보통 - 주황색
  return [220, 38, 38, 220]; // 불량 - 빨간색
};

// 수요집중도별 색상 (DRT 도입 필요성 기준)
const getDemandRatioColor = (
  ratio: number
): [number, number, number, number] => {
  if (ratio >= 25) return [220, 38, 38, 220]; // 긴급검토 (25배+) - 빨간색
  if (ratio >= 20) return [249, 115, 22, 200]; // 검토필요 (20배+) - 주황색
  if (ratio >= 10) return [59, 130, 246, 180]; // 관찰대상 (10배+) - 파란색
  return [34, 197, 94, 180]; // 양호 (5배미만) - 초록색
};

export const ODAnalysisContent = ({
  selectedMonth = "2025-07-01",
}: ODAnalysisContentProps) => {
  // 기본 상태 관리
  const [selectedStation, setSelectedStation] = useState<string | null>(null);
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);
  const [stationData, setStationData] = useState<Station[]>([]);
  const [seoulCtprvnGeoJson, setSeoulCtprvnGeoJson] = useState<any>(null);
  const [seoulSigGeoJson, setSeoulSigGeoJson] = useState<any>(null);
  const [seoulEmdGeoJson, setSeoulEmdGeoJson] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [viewState, setViewState] = useState({
    longitude: 127.0276,
    latitude: 37.4979,
    zoom: 11,
    pitch: 45,
    bearing: 0,
  });

  // 분석 모드 상태
  const [currentMode, setCurrentMode] =
    useState<AnalysisMode["type"]>("time_based");

  // 시간대별 분석 데이터
  const [timeAnalysis, setTimeAnalysis] = useState<TimeAnalysisData>({});
  const [selectedTimePeriod, setSelectedTimePeriod] =
    useState<(typeof TIME_PERIODS)[number]["key"]>("morning_peak");

  // 미스매치 분석 데이터
  const [mismatchAnalysis, setMismatchAnalysis] =
    useState<MismatchAnalysisData>({
      data: [],
      loading: false,
      error: null,
    });

  // 24시간 상세분석 상태
  const [hourlyAnalysis, setHourlyAnalysis] = useState<{
    data: ODPairHourlyAnalysis | null;
    loading: boolean;
    error: string | null;
  }>({
    data: null,
    loading: false,
    error: null,
  });

  // 필터 상태
  const [filters, setFilters] = useState({
    // 시간대별 분석용
    showTimeBasedOrigins: true,
    showTopDestinations: true,
    minDemand: 50,

    // 미스매치 분석용
    minDemandRatio: 2.0,
    showHighRiskOnly: false,

    // 일반 설정
    flowDirection: "both" as "outbound" | "inbound" | "both",
    showMapBackground: true,
    showDistrictBoundaries: false,
    showDetailedBoundaries: false,
  });

  // 데이터 로드 - 지도 데이터 및 API 데이터
  useEffect(() => {
    const loadMapData = async () => {
      setLoading(true);
      try {
        // GeoJSON 데이터 로드
        const loadPromises = [
          fetch("/reference/seoul_ctprvn_fixed.json")
            .then((r) => r.json())
            .then((data) => {
              setSeoulCtprvnGeoJson(ensureFeatureCollection(data));
            })
            .catch((e) => console.warn("시도 지도 로드 실패:", e)),

          fetch("/reference/seoul_sig_fixed.json")
            .then((r) => r.json())
            .then((data) => {
              setSeoulSigGeoJson(ensureFeatureCollection(data));
            })
            .catch((e) => console.warn("구 단위 지도 로드 실패:", e)),

          fetch("/reference/seoul_emd_fixed.json")
            .then((r) => r.json())
            .then((data) => {
              setSeoulEmdGeoJson(ensureFeatureCollection(data));
            })
            .catch((e) => console.warn("동 단위 지도 로드 실패:", e)),
        ];

        await Promise.allSettled(loadPromises);

        // 즉시 fallback 데이터부터 로드하여 시각화가 바로 표시되도록 함
        console.log("🔄 Loading fallback data for immediate visualization...");
        loadFallbackTimeBasedData();

        // 그 다음 실제 API 호출 시도
        await loadAnalysisData();
      } catch (error) {
        console.error("Failed to load map data:", error);
        // 오류 발생시에도 fallback 데이터 로드
        loadFallbackTimeBasedData();
      } finally {
        setLoading(false);
      }
    };

    loadMapData();
  }, []);

  // 분석 데이터 로드 함수
  const loadAnalysisData = async () => {
    try {
      if (currentMode === "time_based") {
        await loadTimeBasedAnalysis();
      } else if (currentMode === "mismatch") {
        await loadMismatchAnalysis();
      }
    } catch (error) {
      console.error("Failed to load analysis data:", error);
    }
  };

  // 시간대별 분석 데이터 로드
  const loadTimeBasedAnalysis = async () => {
    try {
      const results = await odAPI.getAllTimeBasedAnalysis(selectedMonth, 20);
      setTimeAnalysis(results);

      // 정류장 데이터 업데이트
      const allStations = new Map<string, Station>();
      Object.values(results).forEach((timeData) => {
        timeData.origins.forEach((origin) => {
          if (origin.from_station) {
            allStations.set(
              origin.from_station.station_id,
              origin.from_station
            );
          }
          origin.to_stations.forEach((dest) => {
            allStations.set(dest.station_id, {
              station_id: dest.station_id,
              station_name: dest.station_name,
              station_num: dest.station_num,
              district_name: dest.district_name,
              coordinates: dest.coordinates,
            });
          });
        });
      });
      setStationData(Array.from(allStations.values()));
    } catch (error) {
      console.error("Failed to load time-based analysis:", error);
      // Fallback 데이터 사용
      loadFallbackTimeBasedData();
    }
  };

  // 미스매치 분석 데이터 로드
  const loadMismatchAnalysis = async () => {
    setMismatchAnalysis((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await odAPI.getDemandSupplyMismatchAnalysis(
        selectedMonth,
        10,
        50
      );
      setMismatchAnalysis({ data, loading: false, error: null });

      // 정류장 데이터 업데이트 - 미스매치 데이터에서 직접 추출
      const stationMap = new Map<string, Station>();
      data.forEach((item) => {
        // 출발지 정류장
        if (!stationMap.has(item.od_pair.from_station_id)) {
          stationMap.set(item.od_pair.from_station_id, {
            station_id: item.od_pair.from_station_id,
            station_name: item.od_pair.from_station_name,
            station_num: item.od_pair.from_station_num,
            district_name: item.od_pair.from_district,
            coordinates: item.od_pair.from_coordinates,
          });
        }
        // 도착지 정류장
        if (!stationMap.has(item.od_pair.to_station_id)) {
          stationMap.set(item.od_pair.to_station_id, {
            station_id: item.od_pair.to_station_id,
            station_name: item.od_pair.to_station_name,
            station_num: item.od_pair.to_station_num,
            district_name: item.od_pair.to_district,
            coordinates: item.od_pair.to_coordinates,
          });
        }
      });
      setStationData(Array.from(stationMap.values()));
    } catch (error) {
      console.error("Failed to load mismatch analysis:", error);
      // Fallback 데이터 사용
      loadFallbackMismatchData();
      setMismatchAnalysis((prev) => ({
        ...prev,
        loading: false,
        error: "API 연결 실패 - 샘플 데이터 표시 중",
      }));
    }
  };

  // Fallback 시간대별 데이터 로드
  const loadFallbackTimeBasedData = () => {
    const fallbackTimeAnalysis: TimeAnalysisData = {
      morning_peak: {
        time_period: "morning_peak",
        time_period_name: "출근시간 (07-09시)",
        analysis_month: selectedMonth,
        total_origins: 15,
        total_demand: 8500,
        avg_destinations_per_origin: 12.5,
        origins: [
          {
            from_station: {
              station_id: "118000215",
              station_name: "대방역",
              station_num: "19306",
              district_name: "영등포구",
              coordinates: { x: 126.9267, y: 37.5136 },
            },
            destination_count: 15,
            time_period_demand: 850,
            avg_distance_km: 5.2,
            drt_potential: "높음",
            service_recommendation: "DRT 서비스 도입 권장",
            to_stations: [
              {
                station_id: "100000023",
                station_name: "광화문역2번출구.KT광화문지사",
                station_num: "1118",
                district_name: "종로구",
                coordinates: { x: 126.9768, y: 37.5709 },
                demand: 158,
                rank: 1,
              },
              {
                station_id: "121000001",
                station_name: "강남역",
                station_num: "21001",
                district_name: "강남구",
                coordinates: { x: 127.0276, y: 37.4979 },
                demand: 142,
                rank: 2,
              },
              {
                station_id: "102000226",
                station_name: "남산서울타워",
                station_num: "3320",
                district_name: "중구",
                coordinates: { x: 126.9882, y: 37.5512 },
                demand: 138,
                rank: 3,
              },
            ],
          },
          {
            from_station: {
              station_id: "121000001",
              station_name: "강남역",
              station_num: "21001",
              district_name: "강남구",
              coordinates: { x: 127.0276, y: 37.4979 },
            },
            destination_count: 18,
            time_period_demand: 1200,
            avg_distance_km: 8.1,
            drt_potential: "보통",
            service_recommendation: "기존 노선 개선 검토",
            to_stations: [
              {
                station_id: "100000023",
                station_name: "광화문역2번출구.KT광화문지사",
                station_num: "1118",
                district_name: "종로구",
                coordinates: { x: 126.9768, y: 37.5709 },
                demand: 320,
                rank: 1,
              },
              {
                station_id: "121000002",
                station_name: "역삼역",
                station_num: "21002",
                district_name: "강남구",
                coordinates: { x: 127.0365, y: 37.5006 },
                demand: 280,
                rank: 2,
              },
            ],
          },
        ],
      },
      evening_peak: {
        time_period: "evening_peak",
        time_period_name: "퇴근시간 (17-19시)",
        analysis_month: selectedMonth,
        total_origins: 12,
        total_demand: 7200,
        avg_destinations_per_origin: 10.8,
        origins: [],
      },
      daytime: {
        time_period: "daytime",
        time_period_name: "주간시간 (10-16시)",
        analysis_month: selectedMonth,
        total_origins: 8,
        total_demand: 4500,
        avg_destinations_per_origin: 8.5,
        origins: [],
      },
      night: {
        time_period: "night",
        time_period_name: "심야시간 (23-06시)",
        analysis_month: selectedMonth,
        total_origins: 5,
        total_demand: 1200,
        avg_destinations_per_origin: 4.2,
        origins: [],
      },
    };

    setTimeAnalysis(fallbackTimeAnalysis);

    // 정류장 데이터 업데이트
    const allStations = new Map<string, Station>();
    Object.values(fallbackTimeAnalysis).forEach((timeData) => {
      if (timeData?.origins) {
        timeData.origins.forEach((origin: TimeBasedOriginAnalysis) => {
          if (origin.from_station) {
            allStations.set(
              origin.from_station.station_id,
              origin.from_station
            );
          }
          origin.to_stations.forEach((dest: DestinationStation) => {
            allStations.set(dest.station_id, {
              station_id: dest.station_id,
              station_name: dest.station_name,
              station_num: dest.station_num,
              district_name: dest.district_name,
              coordinates: dest.coordinates,
            });
          });
        });
      }
    });
    const stationArray = Array.from(allStations.values());
    setStationData(stationArray);

    // 디버깅용 로그
    console.log(`✅ Fallback time-based data loaded:`);
    console.log(`   - Stations: ${stationArray.length}`);
    console.log(
      `   - Morning peak origins: ${
        fallbackTimeAnalysis.morning_peak?.origins.length || 0
      }`
    );
    console.log(`   - First station:`, stationArray[0]);
  };

  // Fallback 미스매치 데이터 로드
  const loadFallbackMismatchData = () => {
    const fallbackMismatchData: DemandSupplyMismatchData[] = [
      {
        od_pair: {
          from_station_id: "118000215",
          from_station_name: "대방역",
          from_station_num: "19306",
          to_station_id: "100000023",
          to_station_name: "광화문역2번출구.KT광화문지사",
          to_station_num: "1118",
          from_district: "영등포구",
          to_district: "종로구",
          distance_km: 8.5,
          from_coordinates: { x: 126.9267, y: 37.5136 },
          to_coordinates: { x: 126.9768, y: 37.5709 },
        },
        monthly_total_passengers: 4500,
        daily_avg_passengers: 150,
        distance_km: 8.5,
        service_quality_score: 35,
        avg_dispatch_interval_min: 25,
        route_diversity_index: 2.1,
        transfer_penalty: 1.5,
        demand_service_ratio: 3.2,
      },
      {
        od_pair: {
          from_station_id: "121000001",
          from_station_name: "강남역",
          from_station_num: "21001",
          to_station_id: "102000226",
          to_station_name: "남산서울타워",
          to_station_num: "3320",
          from_district: "강남구",
          to_district: "중구",
          distance_km: 12.3,
          from_coordinates: { x: 127.0276, y: 37.4979 },
          to_coordinates: { x: 126.9882, y: 37.5512 },
        },
        monthly_total_passengers: 3200,
        daily_avg_passengers: 107,
        distance_km: 12.3,
        service_quality_score: 42,
        avg_dispatch_interval_min: 18,
        route_diversity_index: 1.8,
        transfer_penalty: 1.2,
        demand_service_ratio: 2.8,
      },
      {
        od_pair: {
          from_station_id: "108000011",
          from_station_name: "미아사거리역",
          from_station_num: "9011",
          to_station_id: "107000032",
          to_station_name: "정릉길음시장.길음뉴타운9단지",
          to_station_num: "8122",
          from_district: "강북구",
          to_district: "성북구",
          distance_km: 1.55,
          from_coordinates: { x: 127.0257, y: 37.6129 },
          to_coordinates: { x: 127.0264, y: 37.6059 },
        },
        monthly_total_passengers: 2640,
        daily_avg_passengers: 88,
        distance_km: 1.55,
        service_quality_score: 65,
        avg_dispatch_interval_min: 12,
        route_diversity_index: 2.5,
        transfer_penalty: 1.3,
        demand_service_ratio: 1.8,
      },
    ];

    setMismatchAnalysis({
      data: fallbackMismatchData,
      loading: false,
      error: null,
    });

    // 정류장 데이터 업데이트 - fallback 데이터에서 직접 추출
    const stationMap = new Map<string, Station>();
    fallbackMismatchData.forEach((item) => {
      // 출발지 정류장
      if (!stationMap.has(item.od_pair.from_station_id)) {
        stationMap.set(item.od_pair.from_station_id, {
          station_id: item.od_pair.from_station_id,
          station_name: item.od_pair.from_station_name,
          station_num: item.od_pair.from_station_num,
          district_name: item.od_pair.from_district,
          coordinates: item.od_pair.from_coordinates,
        });
      }
      // 도착지 정류장
      if (!stationMap.has(item.od_pair.to_station_id)) {
        stationMap.set(item.od_pair.to_station_id, {
          station_id: item.od_pair.to_station_id,
          station_name: item.od_pair.to_station_name,
          station_num: item.od_pair.to_station_num,
          district_name: item.od_pair.to_district,
          coordinates: item.od_pair.to_coordinates,
        });
      }
    });
    setStationData(Array.from(stationMap.values()));
  };

  // 모드 변경시 데이터 로드
  useEffect(() => {
    if (!loading) {
      loadAnalysisData();
    }
  }, [currentMode, selectedMonth]);

  // 선택된 정류장의 관련 데이터 필터링
  const selectedStationData = useMemo(() => {
    if (!selectedStation) return [];

    if (currentMode === "time_based" && timeAnalysis[selectedTimePeriod]) {
      return (
        timeAnalysis[selectedTimePeriod]?.origins.find(
          (origin) => origin.from_station.station_id === selectedStation
        )?.to_stations || []
      );
    } else if (currentMode === "mismatch") {
      return mismatchAnalysis.data.filter(
        (item) =>
          item.od_pair.from_station_id === selectedStation ||
          item.od_pair.to_station_id === selectedStation
      );
    }
    return [];
  }, [
    selectedStation,
    currentMode,
    timeAnalysis,
    selectedTimePeriod,
    mismatchAnalysis.data,
  ]);

  // 정류장 레이어
  const stationLayer = new ScatterplotLayer({
    id: "stations",
    data: stationData,
    getPosition: (d: Station) => {
      const coords = ODAnalysisUtils.convertCoordinates(d.coordinates);
      // 디버깅용 로그
      if (stationData.length > 0 && stationData.indexOf(d) < 3) {
        console.log(
          `🗺️ Station ${d.station_name} position: [${coords.lng}, ${coords.lat}]`
        );
      }
      return [coords.lng, coords.lat];
    },
    getRadius: (d: Station) => {
      if (selectedStation === d.station_id) return 250;
      if (hoveredStation === d.station_id) return 200;
      // 적당한 크기로 정류장이 잘 보이도록 함
      return 100;
    },
    getFillColor: (d: Station) => {
      if (selectedStation === d.station_id) return [255, 50, 50, 255];
      if (hoveredStation === d.station_id) return [255, 165, 0, 220];
      // 더 진한 색상으로 정류장이 잘 보이도록 함
      return [59, 130, 246, 255];
    },
    getLineColor: [255, 255, 255, 255],
    lineWidthMinPixels: 3,
    pickable: true,
    onHover: ({ object }) => {
      setHoveredStation(object?.station_id || null);
      if (object) {
        console.log(`🖱️ Hovering station: ${object.station_name}`);
      }
    },
    onClick: ({ object }) => {
      setSelectedStation(object?.station_id || null);
      if (object) {
        console.log(`🖱️ Selected station: ${object.station_name}`);
      }
    },
    updateTriggers: {
      getRadius: [selectedStation, hoveredStation],
      getFillColor: [selectedStation, hoveredStation],
    },
  });

  // 플로우 레이어 데이터 생성
  const flowLayerData = useMemo(() => {
    let flows: any[] = [];

    if (currentMode === "time_based" && timeAnalysis[selectedTimePeriod]) {
      timeAnalysis[selectedTimePeriod]?.origins.forEach((origin) => {
        if (
          selectedStation &&
          origin.from_station.station_id !== selectedStation
        )
          return;

        origin.to_stations.forEach((destination) => {
          if (destination.demand >= filters.minDemand) {
            flows.push({
              analysis_type: "time_based",
              // ✅ ID를 함께 넣는다
              from_station_id: origin.from_station.station_id,
              to_station_id: destination.station_id,
              from_coordinates: origin.from_station.coordinates,
              to_coordinates: destination.coordinates,
              demand: destination.demand,
              distance_km: 0,
            });
          }
        });
      });
    } else if (currentMode === "mismatch") {
      flows = mismatchAnalysis.data
        .filter((item) => item.demand_service_ratio >= filters.minDemandRatio)
        .filter(
          (item) => !filters.showHighRiskOnly || item.demand_service_ratio > 10
        )
        .map((item) => ({
          analysis_type: "mismatch",
          // ✅ ID를 함께 넣는다
          from_station_id: item.od_pair.from_station_id,
          to_station_id: item.od_pair.to_station_id,
          from_coordinates: item.od_pair.from_coordinates,
          to_coordinates: item.od_pair.to_coordinates,
          demand: item.daily_avg_passengers,
          distance_km: item.distance_km,
          service_quality: item.service_quality_score,
          demand_service_ratio: item.demand_service_ratio,
        }));
    }

    // 디버깅용 로그
    console.log(
      `🔄 Flow layer data: ${flows.length} flows for mode ${currentMode}`
    );
    if (flows.length > 0) {
      console.log(`🔄 First flow sample:`, flows[0]);
    }

    return flows;
  }, [
    currentMode,
    timeAnalysis,
    selectedTimePeriod,
    mismatchAnalysis.data,
    selectedStation,
    filters,
  ]);

  const flowLayer = new ArcLayer({
    id: "od-flows",
    data: flowLayerData,
    getSourcePosition: (d: any) => {
      const coords = ODAnalysisUtils.convertCoordinates(d.from_coordinates);
      return [coords.lng, coords.lat];
    },
    getTargetPosition: (d: any) => {
      const coords = ODAnalysisUtils.convertCoordinates(d.to_coordinates);
      return [coords.lng, coords.lat];
    },
    getHeight: (d: any) => {
      const baseHeight = Math.log(d.demand + 1) * 0.3;
      return d.analysis_type === "mismatch" ? baseHeight * 2.0 : baseHeight;
    },
    getSourceColor: (d: any) => {
      if (d.analysis_type === "time_based") {
        return getDemandLevelColor(d.demand);
      } else {
        return getDemandRatioColor(d.demand_service_ratio || 1);
      }
    },
    getTargetColor: (d: any) => {
      if (d.analysis_type === "time_based") {
        return getDemandLevelColor(d.demand);
      } else {
        return getDemandRatioColor(d.demand_service_ratio || 1);
      }
    },
    getWidth: (d: any) => Math.max(4, Math.log(d.demand + 1) * 2.5),
    pickable: true,
    autoHighlight: true,
    visible: true,
    opacity: 0.8,
    onClick: ({ object }: any) => {
      // ✅ 방어코드: ID 없으면 중단
      const fromId = object?.from_station_id;
      const toId = object?.to_station_id;
      if (!fromId || !toId) {
        console.warn("🚨 Arc object has no station IDs:", object);
        return;
      }

      console.log("🔄 Arc clicked - loading 24h analysis:", {
        fromId,
        toId,
        selectedMonth,
      });

      // Promise를 무시하여 비동기 호출
      (async () => {
        try {
          setHourlyAnalysis({ data: null, loading: true, error: null });

          const result = await odAPI.getODPairHourlyAnalysis(
            fromId,
            toId,
            selectedMonth
          );

          setHourlyAnalysis({ data: result, loading: false, error: null });
          console.log("✅ 24h analysis loaded successfully");
        } catch (error) {
          console.error("❌ Failed to load hourly analysis:", error);
          setHourlyAnalysis({
            data: null,
            loading: false,
            error: "데이터를 불러올 수 없습니다",
          });
        }
      })();
    },
  });

  // 1단계: 시도 배경 레이어 (서울특별시 전체)
  const ctprvnLayer =
    seoulCtprvnGeoJson && filters.showMapBackground
      ? new GeoJsonLayer({
          id: "seoul-ctprvn",
          data: seoulCtprvnGeoJson,
          pickable: false,
          stroked: true,
          filled: true,
          getFillColor: [255, 255, 255, 30],
          getLineColor: [100, 100, 100, 150],
          getLineWidth: 100,
          lineWidthMinPixels: 2,
        })
      : null;

  // 2단계: 구 경계 레이어 (25개 구)
  const sigLayer =
    seoulSigGeoJson && filters.showDistrictBoundaries
      ? new GeoJsonLayer({
          id: "seoul-sig",
          data: seoulSigGeoJson,
          pickable: true,
          stroked: true,
          filled: true,
          getFillColor: (d: any) => {
            return hoveredStation === `district_${d.properties?.SIG_CD}`
              ? [100, 150, 255, 80]
              : [255, 255, 255, 20];
          },
          getLineColor: [80, 80, 80, 180],
          getLineWidth: 30,
          lineWidthMinPixels: 1.5,
          onHover: ({ object }) => {
            if (object) {
              setHoveredStation(`district_${object.properties?.SIG_CD}`);
            } else {
              setHoveredStation(null);
            }
          },
          updateTriggers: {
            getFillColor: [hoveredStation],
          },
        })
      : null;

  // 3단계: 동 경계 레이어 (467개 동)
  const emdLayer =
    seoulEmdGeoJson && filters.showDetailedBoundaries
      ? new GeoJsonLayer({
          id: "seoul-emd",
          data: seoulEmdGeoJson,
          pickable: true,
          stroked: true,
          filled: false,
          getFillColor: [0, 0, 0, 0],
          getLineColor: (d: any) => {
            return hoveredStation === `emd_${d.properties?.EMD_CD}`
              ? [255, 100, 100, 200]
              : [100, 100, 100, 100];
          },
          getLineWidth: (d: any) => {
            return hoveredStation === `emd_${d.properties?.EMD_CD}` ? 30 : 15;
          },
          lineWidthMinPixels: 0.3,
          onHover: ({ object }) => {
            if (object) {
              setHoveredStation(`emd_${object.properties?.EMD_CD}`);
            } else if (!hoveredStation?.startsWith("district_")) {
              setHoveredStation(null);
            }
          },
          updateTriggers: {
            getLineColor: [hoveredStation],
            getLineWidth: [hoveredStation],
          },
        })
      : null;

  // CartoDB 지도 타일 레이어
  const tileLayer = new TileLayer({
    id: "carto-tiles",
    data: [
      "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    ],
    minZoom: 0,
    maxZoom: 20,
    tileSize: 256,
    renderSubLayers: (props: any) => {
      const bbox = props.tile?.bbox;
      if (!bbox) return null;

      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [bbox.west, bbox.south, bbox.east, bbox.north],
      });
    },
  });

  // 레이어 순서: 타일 → 시도배경 → 구경계 → 동경계 → 스테이션 → 플로우
  const layers = [
    tileLayer,
    ...(ctprvnLayer ? [ctprvnLayer] : []),
    ...(sigLayer ? [sigLayer] : []),
    ...(emdLayer ? [emdLayer] : []),
    stationLayer,
    flowLayer,
  ].filter(Boolean);

  // 로딩 중일 때
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">OD 데이터를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="h-full flex">
        {/* 메인 지도 영역 */}
        <div
          className="flex-1 relative"
          onContextMenu={(e) => e.preventDefault()}
        >
          <DeckGL
            viewState={viewState}
            onViewStateChange={({ viewState }: any) => setViewState(viewState)}
            controller={true}
            layers={layers}
            getTooltip={({ object }: any) => {
              if (!object) return null;

              if (object.station_name) {
                // 정류장 툴팁
                return {
                  html: `
                  <div class="bg-white p-2 rounded shadow-lg">
                    <div class="font-bold">${object.station_name}</div>
                    <div class="text-sm">구역: ${
                      object.district_name || "N/A"
                    }</div>
                    <div class="text-sm">정류장 번호: ${
                      object.station_num || "N/A"
                    }</div>
                    <div class="text-xs text-gray-500 mt-1">클릭하여 연결 정보 보기</div>
                  </div>
                `,
                };
              } else if (object.analysis_type) {
                // 플로우 툴팁
                if (object.analysis_type === "time_based") {
                  return {
                    html: `
                    <div class="bg-white p-3 rounded shadow-lg border-l-4 border-blue-500">
                      <div class="font-bold text-sm">시간대별 이동 패턴</div>
                      <div class="mt-2 space-y-1">
                        <div class="text-sm">📊 수요: <span class="font-bold">${
                          object.demand?.toLocaleString() || 0
                        }명</span></div>
                        <div class="text-sm">⏰ 시간대: <span class="font-bold">${
                          TIME_PERIODS.find((p) => p.key === selectedTimePeriod)
                            ?.label || ""
                        }</span></div>
                        <div class="text-xs text-gray-500 mt-2">DRT 서비스 검토 대상</div>
                      </div>
                    </div>
                  `,
                  };
                } else {
                  return {
                    html: `
                    <div class="bg-white p-3 rounded shadow-lg border-l-4 border-orange-500">
                      <div class="font-bold text-sm">수요-공급 불균형</div>
                      <div class="mt-2 space-y-1">
                        <div class="text-sm">수요집중도: <span class="font-bold ${
                          (object.demand_service_ratio || 0) > 10
                            ? "text-red-600"
                            : ""
                        }">'${(object.demand_service_ratio || 0).toFixed(
                      1
                    )}배</span></div>
                        <div class="text-sm">일평균 승객: <span class="font-bold">${
                          object.demand?.toLocaleString() || 0
                        }명</span></div>
                        <div class="text-sm">서비스 품질: <span class="font-bold">${Math.round(
                          object.service_quality || 0
                        )}점</span></div>
                        <div class="text-sm">거리: <span class="font-bold">${
                          object.distance_km?.toFixed(1) || 0
                        }km</span></div>
                        <div class="text-xs text-gray-500 mt-2">DRT 도입 필요 구간</div>
                      </div>
                    </div>
                  `,
                  };
                }
              }
              return null;
            }}
          />

          {/* 현재 분석 정보 */}
          <div className="absolute top-4 left-4 z-10 text-xs text-gray-600 bg-white/95 p-3 rounded-lg shadow-lg">
            <div className="font-medium mb-1">
              {ANALYSIS_MODES.find((mode) => mode.type === currentMode)?.label}
              {mismatchAnalysis.error && currentMode === "mismatch" && (
                <span className="ml-2 text-orange-600 text-xs">
                  ⚠️ 샘플 데이터
                </span>
              )}
            </div>
            {currentMode === "time_based" && (
              <div className="text-gray-500">
                {selectedMonth} •{" "}
                {TIME_PERIODS.find((p) => p.key === selectedTimePeriod)?.label}
                <br />총 {timeAnalysis[selectedTimePeriod]?.total_origins || 0}
                개 출발지
                <br />총{" "}
                {(
                  timeAnalysis[selectedTimePeriod]?.total_demand || 0
                ).toLocaleString()}
                명 수요
              </div>
            )}
            {currentMode === "mismatch" && (
              <div className="text-gray-500">
                {selectedMonth} 분석 결과
                <br />
                {mismatchAnalysis.data.length}개 구간 분석
                <br />
                {
                  mismatchAnalysis.data.filter(
                    (item) => item.demand_service_ratio > 10
                  ).length
                }
                개 고위험 구간
              </div>
            )}
            <div className="text-gray-400 mt-2 border-t pt-1">
              3D 지도 표시 • 정류장 클릭으로 상세 정보
              {mismatchAnalysis.error && currentMode === "mismatch" && (
                <div className="text-orange-500 mt-1">
                  API 연결 실패 - 데모 데이터 사용 중
                </div>
              )}
            </div>
          </div>

          {/* 필터 컨트롤 */}
          <Card className="absolute top-4 right-4 z-10 p-3 w-64 bg-white/95 backdrop-blur-sm">
            <CardTitle className="text-xs mb-1 font-semibold flex items-center gap-1">
              필터
              <Tooltip>
                <TooltipTrigger>
                  <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">
                    분석 모드와 시간대를 선택하여 원하는 OD 패턴을 확인할 수
                    있습니다.
                  </p>
                </TooltipContent>
              </Tooltip>
            </CardTitle>
            <div className="space-y-0">
              {/* 분석 모드 선택 */}
              <div className="space-y-1 mb-3">
                <div className="flex items-center gap-1">
                  <Label className="text-xs font-medium">분석 모드</Label>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-2 w-2 text-gray-400 hover:text-gray-600" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">
                        시간대별: 특정 시간대의 승객 이동 패턴 분석
                        <br />
                        미스매치: 수요와 공급의 불균형 분석
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="grid grid-cols-1 gap-1">
                  <Button
                    variant={
                      currentMode === "time_based" ? "default" : "outline"
                    }
                    size="sm"
                    onClick={() => setCurrentMode("time_based")}
                    className="text-xs h-7 justify-start"
                  >
                    <Clock className="h-3 w-3 mr-1" />
                    수요패턴 분석
                  </Button>
                  <Button
                    variant={currentMode === "mismatch" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setCurrentMode("mismatch")}
                    className="text-xs h-7 justify-start"
                  >
                    <AlertTriangle className="h-3 w-3 mr-1" />
                    서비스부족구간 분석
                  </Button>
                </div>
              </div>

              {/* 시간대별 분석 필터 */}
              {currentMode === "time_based" && (
                <div className="space-y-2">
                  <Label className="text-xs font-medium">시간대 선택</Label>
                  <div className="grid grid-cols-2 gap-1">
                    {TIME_PERIODS.map((period) => (
                      <Button
                        key={period.key}
                        variant={
                          selectedTimePeriod === period.key
                            ? "default"
                            : "outline"
                        }
                        size="sm"
                        onClick={() => setSelectedTimePeriod(period.key)}
                        className="text-xs h-7"
                        style={{
                          backgroundColor:
                            selectedTimePeriod === period.key
                              ? period.color
                              : undefined,
                          borderColor: period.color,
                        }}
                      >
                        {period.label}
                      </Button>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <Label className="text-xs">
                      최소수요: {filters.minDemand}
                    </Label>
                    <input
                      type="range"
                      min="10"
                      max="500"
                      step="10"
                      value={filters.minDemand}
                      onChange={(e) =>
                        setFilters((prev) => ({
                          ...prev,
                          minDemand: parseInt(e.target.value),
                        }))
                      }
                      className="flex-1 h-1"
                    />
                  </div>
                </div>
              )}

              {/* 미스매치 분석 필터 */}
              {currentMode === "mismatch" && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={filters.showHighRiskOnly}
                      onCheckedChange={(checked) =>
                        setFilters((prev) => ({
                          ...prev,
                          showHighRiskOnly: checked,
                        }))
                      }
                      className="scale-75"
                    />
                    <Label className="text-xs">고위험 구간만</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs">
                      수요집중도: {filters.minDemandRatio}배
                    </Label>
                    <input
                      type="range"
                      min="1"
                      max="30"
                      step="1"
                      value={filters.minDemandRatio}
                      onChange={(e) =>
                        setFilters((prev) => ({
                          ...prev,
                          minDemandRatio: parseFloat(e.target.value),
                        }))
                      }
                      className="flex-1 h-1"
                    />
                  </div>
                </div>
              )}
            </div>

            <Separator className="my-3" />

            <div className="space-y-2">
              <div className="text-xs font-medium mb-2">지도 레이어</div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={filters.showMapBackground}
                  onCheckedChange={(checked) =>
                    setFilters((prev) => ({
                      ...prev,
                      showMapBackground: checked,
                    }))
                  }
                  disabled={!seoulCtprvnGeoJson}
                />
                <div className="w-3 h-3 bg-gray-300 rounded border" />
                <Label className="text-xs">서울특별시 배경</Label>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={filters.showDistrictBoundaries}
                  onCheckedChange={(checked) =>
                    setFilters((prev) => ({
                      ...prev,
                      showDistrictBoundaries: checked,
                    }))
                  }
                  disabled={!seoulSigGeoJson}
                />
                <div className="w-3 h-3 bg-gray-200 border border-gray-400" />
                <Label className="text-xs">구 경계선</Label>
                {seoulSigGeoJson && (
                  <span className="text-xs text-gray-500">(25개 구)</span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={filters.showDetailedBoundaries}
                  onCheckedChange={(checked) =>
                    setFilters((prev) => ({
                      ...prev,
                      showDetailedBoundaries: checked,
                    }))
                  }
                  disabled={!seoulEmdGeoJson}
                />
                <div className="w-3 h-3 border border-gray-400 bg-transparent" />
                <Label className="text-xs">동 경계선</Label>
                {seoulEmdGeoJson && (
                  <span className="text-xs text-gray-500">(467개 동)</span>
                )}
              </div>
            </div>
          </Card>

          {/* 범례 - 컴팩트 */}
          <Card className="absolute bottom-4 left-4 z-10 p-2 w-48 bg-white/95 backdrop-blur-sm">
            <div className="space-y-2">
              <div className="text-xs font-semibold">범례</div>

              {/* 정류장 */}
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 bg-blue-500 rounded-full border border-white" />
                <span className="text-xs">정류장</span>
              </div>

              {/* 분석별 범례 */}
              {currentMode === "time_based" && (
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-red-600 rounded-sm" />
                    <span className="text-xs">고수요 (1000+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-orange-500 rounded-sm" />
                    <span className="text-xs">중수요 (500+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-blue-500 rounded-sm" />
                    <span className="text-xs">일반 (100+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-green-500 rounded-sm" />
                    <span className="text-xs">저수요 (50+)</span>
                  </div>
                </div>
              )}

              {currentMode === "mismatch" && (
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-red-600 rounded-sm" />
                    <span className="text-xs">긴급검토 (25배+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-orange-500 rounded-sm" />
                    <span className="text-xs">검토필요 (20배+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-blue-500 rounded-sm" />
                    <span className="text-xs">관찰대상 (10배+)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-1.5 bg-green-500 rounded-sm" />
                    <span className="text-xs">양호 (5배미만)</span>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* 우측 상세 패널 */}
        <div className="w-96 border-l bg-white p-4 overflow-y-auto">
          {/* 24시간 상세분석 표시 */}
          {hourlyAnalysis.data && (
            <Card className="mb-4">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Clock className="h-4 w-4" />
                    24시간 상세분석
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setHourlyAnalysis({
                        data: null,
                        loading: false,
                        error: null,
                      })
                    }
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
                <CardDescription className="text-xs">
                  {hourlyAnalysis.data.od_pair.from_station_name} →{" "}
                  {hourlyAnalysis.data.od_pair.to_station_name}
                  <br />
                  {hourlyAnalysis.data.od_pair.distance_km.toFixed(1)}km •
                  일평균 {Math.round(hourlyAnalysis.data.daily_avg_passengers)}
                  명
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* 패턴 배지 */}
                <div className="mb-4">
                  <Badge
                    className={
                      getPatternTypeConfig(
                        hourlyAnalysis.data.time_summary.pattern_type
                      ).bgColor +
                      " " +
                      getPatternTypeConfig(
                        hourlyAnalysis.data.time_summary.pattern_type
                      ).textColor
                    }
                  >
                    {
                      getPatternTypeConfig(
                        hourlyAnalysis.data.time_summary.pattern_type
                      ).icon
                    }{" "}
                    {hourlyAnalysis.data.time_summary.pattern_type}
                  </Badge>
                </div>

                {/* 24시간 시계열 그래프 */}
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={formatHourlyChartData(
                      hourlyAnalysis.data.hourly_passengers,
                      hourlyAnalysis.data.daily_avg_passengers
                    )}
                    margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="hour"
                      tick={{ fontSize: 10 }}
                      interval={2}
                    />
                    <YAxis tick={{ fontSize: 10 }} width={40} />
                    <RechartsTooltip
                      formatter={(value: number, name: string) => [
                        `${Math.round(value)}명`,
                        name === "passengers" ? "승객 수" : "평균선",
                      ]}
                      labelFormatter={(label) => `시간: ${label}`}
                    />

                    {/* 주요 데이터 라인 */}
                    <Line
                      type="monotone"
                      dataKey="passengers"
                      stroke={
                        getPatternTypeConfig(
                          hourlyAnalysis.data.time_summary.pattern_type
                        ).color
                      }
                      strokeWidth={2}
                      name="승객 수"
                      dot={{ r: 2 }}
                      activeDot={{ r: 4 }}
                      isAnimationActive={false}
                    />

                    {/* 평균선 */}
                    <Line
                      type="monotone"
                      dataKey="평균선"
                      stroke="#94a3b8"
                      strokeDasharray="5 5"
                      strokeWidth={1}
                      name="평균선"
                      dot={false}
                      isAnimationActive={false}
                    />

                    {/* 피크 시간 표시 */}
                    <ReferenceLine
                      x={`${hourlyAnalysis.data.time_summary.peak_hour}시`}
                      stroke="#ef4444"
                      strokeWidth={1}
                      strokeDasharray="3 3"
                      label={{ value: "피크", position: "top", fontSize: 10 }}
                    />
                  </LineChart>
                </ResponsiveContainer>

                {/* 주요 지표 */}
                <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                  <div className="text-center p-2 bg-orange-50 rounded">
                    <div className="font-semibold">피크 시간</div>
                    <div className="text-orange-600 font-bold">
                      {hourlyAnalysis.data.time_summary.peak_hour}시
                    </div>
                    <div className="text-gray-500">
                      {Math.round(
                        hourlyAnalysis.data.time_summary.peak_passengers
                      )}
                      명
                    </div>
                  </div>
                  <div className="text-center p-2 bg-blue-50 rounded">
                    <div className="font-semibold">퇴근 집중도</div>
                    <div className="text-blue-600 font-bold">
                      {hourlyAnalysis.data.time_summary.evening_peak_pct.toFixed(
                        1
                      )}
                      %
                    </div>
                    <div className="text-gray-500">17-19시</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {selectedStation ? (
            <div className="space-y-4">
              {/* 선택된 정류장 정보 */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <MapPin className="h-5 w-5" />
                        {
                          stationData.find(
                            (s) => s.station_id === selectedStation
                          )?.station_name
                        }
                      </CardTitle>
                      <CardDescription>
                        {currentMode === "time_based"
                          ? `${selectedStationData.length}개 목적지`
                          : `${selectedStationData.length}개 연결 경로`}
                      </CardDescription>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedStation(null)}
                      className="text-xs"
                    >
                      전체 보기
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {currentMode === "time_based" && (
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-gray-700 mb-3">
                        {
                          TIME_PERIODS.find((p) => p.key === selectedTimePeriod)
                            ?.label
                        }{" "}
                        목적지 TOP 5
                      </div>
                      {(selectedStationData as DestinationStation[])
                        .sort((a, b) => b.demand - a.demand)
                        .slice(0, 5)
                        .map((dest, idx) => (
                          <div
                            key={idx}
                            className="p-2 bg-gray-50 rounded border-l-2 border-blue-500"
                          >
                            <div className="flex justify-between items-center">
                              <div>
                                <div className="font-medium text-sm">
                                  {dest.station_name}
                                </div>
                                <div className="text-xs text-gray-600 mt-1">
                                  순위: {dest.rank}위 • {dest.district_name}
                                </div>
                              </div>
                              <div className="text-right">
                                <div className="font-bold text-blue-600">
                                  {dest.demand}명
                                </div>
                                <div className="text-xs text-gray-500">
                                  시간대 수요
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}

                  {currentMode === "mismatch" && (
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-gray-700 mb-3">
                        미스매치 구간 정보
                      </div>
                      {(selectedStationData as DemandSupplyMismatchData[])
                        .sort(
                          (a, b) =>
                            b.demand_service_ratio - a.demand_service_ratio
                        )
                        .slice(0, 5)
                        .map((item, idx) => (
                          <div
                            key={idx}
                            className="p-2 bg-gray-50 rounded border-l-2 border-orange-500"
                          >
                            <div className="flex justify-between items-center">
                              <div className="flex-1">
                                <div className="font-medium text-sm">
                                  {item.od_pair.from_station_id ===
                                  selectedStation
                                    ? item.od_pair.to_station_name
                                    : item.od_pair.from_station_name}
                                </div>
                                <div className="text-xs text-gray-600 mt-1">
                                  거리: {item.distance_km.toFixed(1)}km
                                </div>
                              </div>
                              <div className="text-right">
                                <div className="font-bold text-orange-600">
                                  {item.daily_avg_passengers}명/일
                                </div>
                                <div className="text-xs text-gray-500">
                                  서비스점수:{" "}
                                  {Math.round(item.service_quality_score)}점
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={async () => {
                                    console.log(
                                      "🔘 Button clicked - loading 24h analysis:",
                                      {
                                        fromId: item.od_pair.from_station_id,
                                        toId: item.od_pair.to_station_id,
                                        selectedMonth,
                                      }
                                    );

                                    setHourlyAnalysis({
                                      data: null,
                                      loading: true,
                                      error: null,
                                    });
                                    try {
                                      // ✅ 올바른 인수 순서: fromId, toId, month
                                      const analysis =
                                        await odAPI.getODPairHourlyAnalysis(
                                          item.od_pair.from_station_id,
                                          item.od_pair.to_station_id,
                                          selectedMonth
                                        );
                                      setHourlyAnalysis({
                                        data: analysis,
                                        loading: false,
                                        error: null,
                                      });
                                      setCurrentMode("mismatch"); // 보여주기 위해
                                    } catch (error) {
                                      console.error(
                                        "Failed to load hourly analysis:",
                                        error
                                      );
                                      setHourlyAnalysis({
                                        data: null,
                                        loading: false,
                                        error: "데이터를 불러올 수 없습니다",
                                      });
                                    }
                                  }}
                                  className="text-xs mt-1"
                                  disabled={hourlyAnalysis.loading}
                                >
                                  {hourlyAnalysis.loading
                                    ? "로딩..."
                                    : "24시간 분석"}
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 분석 결과 요약 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    {currentMode === "time_based" && "시간대별 분석 결과"}
                    {currentMode === "mismatch" && "DRT 도입 필요성 분석"}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {currentMode === "time_based" &&
                    timeAnalysis[selectedTimePeriod] && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <div className="flex items-center gap-1">
                            <span>전체 출발지 수</span>
                            <Tooltip>
                              <TooltipTrigger>
                                <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-xs">
                                  해당 시간대에 승객이 출발하는 버스정류장의 총
                                  개수입니다.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <span className="font-bold">
                            {timeAnalysis[selectedTimePeriod]?.total_origins}
                            개소
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <div className="flex items-center gap-1">
                            <span>총 수요량</span>
                            <Tooltip>
                              <TooltipTrigger>
                                <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-xs">
                                  해당 시간대에 이동한 승객의 총 인원수입니다.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <span className="font-bold text-blue-600">
                            {timeAnalysis[
                              selectedTimePeriod
                            ]?.total_demand.toLocaleString()}
                            명
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <div className="flex items-center gap-1">
                            <span>평균 목적지 수</span>
                            <Tooltip>
                              <TooltipTrigger>
                                <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-xs">
                                  각 출발지에서 연결되는 목적지의 평균
                                  개수입니다. 높을수록 다양한 목적지로
                                  분산됩니다.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <span className="font-bold">
                            {timeAnalysis[
                              selectedTimePeriod
                            ]?.avg_destinations_per_origin.toFixed(1)}
                            개
                          </span>
                        </div>
                        <div className="border-t pt-2 mt-3">
                          <div className="text-xs text-gray-600">
                            💡{" "}
                            {
                              TIME_PERIODS.find(
                                (p) => p.key === selectedTimePeriod
                              )?.label
                            }{" "}
                            특성에 맞는 DRT 운영 전략이 필요합니다.
                          </div>
                        </div>
                      </div>
                    )}

                  {currentMode === "mismatch" && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <div className="flex items-center gap-1">
                          <span>총 분석 구간</span>
                          <Tooltip>
                            <TooltipTrigger>
                              <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-xs">
                                수요와 공급을 비교 분석한 OD 구간의 총
                                개수입니다.
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <span className="font-bold">
                          {mismatchAnalysis.data.length}개
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <div className="flex items-center gap-1">
                          <span>고위험 구간</span>
                          <Tooltip>
                            <TooltipTrigger>
                              <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-xs">
                                교통 서비스가 부족해 불편을 겪는 구간입니다.
                                DRT로 개선이 가능합니다.
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <span className="font-bold text-red-600">
                          {
                            mismatchAnalysis.data.filter(
                              (item) => item.demand_service_ratio > 10
                            ).length
                          }
                          개
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <div className="flex items-center gap-1">
                          <span>평균 서비스 점수</span>
                          <Tooltip>
                            <TooltipTrigger>
                              <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-xs">
                                전체 구간의 서비스 품질을 평가한 평균
                                점수입니다. 낮을수록 개선이 필요합니다.
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <span className="font-bold">
                          {Math.round(
                            mismatchAnalysis.data.reduce(
                              (sum, item) => sum + item.service_quality_score,
                              0
                            ) / mismatchAnalysis.data.length || 0
                          )}
                          점
                        </span>
                      </div>
                      <div className="border-t pt-2 mt-3">
                        <div className="text-xs text-gray-600">
                          🚨 서비스 품질 개선이 시급한 구간들이 식별되었습니다.
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    {currentMode === "time_based" && (
                      <Clock className="h-4 w-4" />
                    )}
                    {currentMode === "mismatch" && (
                      <AlertTriangle className="h-4 w-4" />
                    )}

                    {
                      ANALYSIS_MODES.find((mode) => mode.type === currentMode)
                        ?.label
                    }
                  </CardTitle>
                  <CardDescription>
                    {
                      ANALYSIS_MODES.find((mode) => mode.type === currentMode)
                        ?.description
                    }
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center text-sm text-gray-500">
                      데이터 로드 중...
                    </div>
                  ) : currentMode === "time_based" &&
                    timeAnalysis[selectedTimePeriod]?.origins ? (
                    <div className="text-center text-sm text-gray-500">
                      출발 정류장을 선택하여 연결 정보를 확인하세요
                    </div>
                  ) : (
                    <div className="text-center text-sm text-gray-500">
                      정류장을 클릭하여 상세 정보를 확인하세요
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 시간대별 분석 - From Station 랭킹 리스트 */}
              {currentMode === "time_based" &&
                timeAnalysis[selectedTimePeriod]?.origins && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <MapPin className="h-4 w-4" />
                        출발 정류장 랭킹
                        <Tooltip>
                          <TooltipTrigger>
                            <HelpCircle className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-xs">
                              해당 시간대에 승객 수요가 많은 출발 정류장을
                              순위별로 보여줍니다. 정류장을 클릭하면 해당
                              출발지의 목적지 분포를 확인할 수 있습니다.
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </CardTitle>
                      <CardDescription>
                        {
                          TIME_PERIODS.find((p) => p.key === selectedTimePeriod)
                            ?.label
                        }{" "}
                        기준 • 클릭하여 필터링
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2 max-h-80 overflow-y-auto">
                        {timeAnalysis[selectedTimePeriod]?.origins
                          .sort(
                            (a, b) =>
                              b.time_period_demand - a.time_period_demand
                          )
                          .map((origin, idx) => (
                            <div
                              key={origin.from_station.station_id}
                              className="p-3 bg-gray-50 hover:bg-blue-50 rounded-lg border cursor-pointer transition-colors"
                              onClick={() =>
                                setSelectedStation(
                                  origin.from_station.station_id
                                )
                              }
                            >
                              <div className="flex justify-between items-center">
                                <div className="flex-1">
                                  <div className="font-medium text-sm flex items-center gap-2">
                                    <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-bold">
                                      #{idx + 1}
                                    </span>
                                    {origin.from_station.station_name}
                                  </div>
                                  <div className="text-xs text-gray-600 mt-1">
                                    {origin.from_station.district_name} •{" "}
                                    {origin.destination_count}개 목적지
                                  </div>
                                  {origin.drt_potential && (
                                    <div className="text-xs mt-1">
                                      <span
                                        className={`px-1.5 py-0.5 rounded text-xs ${
                                          origin.drt_potential === "높음"
                                            ? "bg-red-100 text-red-700"
                                            : origin.drt_potential === "보통"
                                            ? "bg-yellow-100 text-yellow-700"
                                            : "bg-green-100 text-green-700"
                                        }`}
                                      >
                                        DRT {origin.drt_potential}
                                      </span>
                                    </div>
                                  )}
                                </div>
                                <div className="text-right ml-3">
                                  <div className="font-bold text-blue-600">
                                    {origin.time_period_demand.toLocaleString()}
                                    명
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    시간대 총 수요
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                      </div>
                      <div className="mt-3 pt-2 border-t text-xs text-gray-500">
                        💡 정류장을 클릭하면 해당 출발지에서 퍼져나가는 연결만
                        지도에 표시됩니다
                      </div>
                    </CardContent>
                  </Card>
                )}

              {mismatchAnalysis.error && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-red-600">
                      ⚠️ {mismatchAnalysis.error}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};
