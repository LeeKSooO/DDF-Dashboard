"use client";

import { useEffect, lazy, Suspense } from "react";
import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useTrafficAnalysisData } from "@/hooks/use-traffic-analysis-data";
import { useAnimation } from "@/hooks/use-animation";
import "@/styles/traffic-analysis-animations.css";

// Lazy load components for code splitting
const AreaTypeAnalysisSection = lazy(() => 
  import("./traffic-analysis/area-type-analysis-section").then(module => ({
    default: module.AreaTypeAnalysisSection
  }))
);

const WeekendDominantSection = lazy(() => 
  import("./traffic-analysis/weekend-dominant-section").then(module => ({
    default: module.WeekendDominantSection
  }))
);

// Loading component
const SectionSkeleton = () => (
  <Card>
    <CardContent className="p-6">
      <div className="animate-pulse space-y-4">
        <div className="h-6 bg-gray-200 rounded w-1/2"></div>
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-full"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    </CardContent>
  </Card>
);

// Month names constant (moved outside component to prevent re-creation)
const MONTH_NAMES = [
  "1월", "2월", "3월", "4월", "5월", "6월",
  "7월", "8월", "9월", "10월", "11월", "12월",
];

interface TrafficAnalysisContentOptimizedProps {
  selectedMonth: string;
  selectedRegion: string;
}

export function TrafficAnalysisContentOptimized({
  selectedMonth,
  selectedRegion,
}: TrafficAnalysisContentOptimizedProps) {
  const { data, loading, error } = useTrafficAnalysisData(selectedMonth, selectedRegion);
  const { animatedNumbers, animateNumber, resetAnimations } = useAnimation();

  // 애니메이션 트리거
  useEffect(() => {
    if (!loading && !error) {
      // 데이터 로드 완료 후 애니메이션 시작
      const timer = setTimeout(() => {
        // Weekend data animation
        if (data.weekendData?.data) {
          data.weekendData.data.forEach((item: any, index: number) => {
            animateNumber(
              `weekend-${item.station.station_id}`,
              item.weekend_total_traffic || 0,
              1000 + index * 100
            );
          });
        }

        // Area type data animation
        if (data.areaTypeData?.data?.residential_stations) {
          data.areaTypeData.data.residential_stations.forEach((item: any, index: number) => {
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
          });
        }

        if (data.areaTypeData?.data?.business_stations) {
          data.areaTypeData.data.business_stations.forEach((item: any, index: number) => {
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
          });
        }
      }, 300);

      return () => clearTimeout(timer);
    }
  }, [loading, error, data, animateNumber]);

  // 데이터 변경 시 애니메이션 리셋
  useEffect(() => {
    resetAnimations();
  }, [selectedMonth, selectedRegion, resetAnimations]);

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

  const monthName = MONTH_NAMES[Number.parseInt(selectedMonth) - 1];
  const regionName = selectedRegion === "전체" ? "서울시 전체" : selectedRegion;

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold">이상 패턴 분석</h1>
          <p className="text-gray-600">{regionName} · {monthName}</p>
        </div>
      </div>

      {/* 이상 패턴 감지 콘텐츠 */}
      <div className="space-y-6">
        {/* 지역 특성별 정류장 분석 */}
        <Suspense fallback={<SectionSkeleton />}>
          <AreaTypeAnalysisSection
            areaTypeData={data.areaTypeData}
            animatedNumbers={animatedNumbers}
          />
        </Suspense>

        {/* 주말 우세 정류장 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Suspense fallback={<SectionSkeleton />}>
            <WeekendDominantSection
              weekendData={data.weekendData}
              animatedNumbers={animatedNumbers}
            />
          </Suspense>
          
          {/* 다른 섹션들도 필요에 따라 추가 */}
          <SectionSkeleton /> 
          <SectionSkeleton />
        </div>
      </div>
    </div>
  );
}