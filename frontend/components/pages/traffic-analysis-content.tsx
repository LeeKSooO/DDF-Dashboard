"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Users,
  Star,
  Repeat,
  Clock,
  MapPin,
  Target,
  HelpCircle,
} from "lucide-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { apiService } from "@/lib/api";

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
  const [integrationData, setIntegrationData] = useState<any>(null);

  // 데이터 로드
  useEffect(() => {
    const loadTrafficAnalysisData = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log("🚌 Loading traffic analysis data for:", {
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
        const analysisMonth = "2025-07-01";

        // 모든 API 병렬 호출
        const [
          weekendResult,
          nightResult,
          rushHourResult,
          lunchTimeResult,
          areaTypeResult,
          underutilizedResult,
          integrationResult,
        ] = await Promise.allSettled([
          apiService.getWeekendDominantStations(
            targetDistrict,
            analysisMonth,
            5
          ),
          apiService.getNightDemandStations(targetDistrict, analysisMonth, 5),
          apiService.getRushHourAnalysis(targetDistrict, analysisMonth),
          apiService.getLunchTimeStations(targetDistrict, analysisMonth, 5),
          apiService.getAreaTypeAnalysis(targetDistrict, analysisMonth),
          apiService.getUnderutilizedStations(targetDistrict, analysisMonth, 5),
          apiService.getIntegratedAnomalyAnalysis(
            targetDistrict,
            analysisMonth
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
        if (integrationResult.status === "fulfilled")
          setIntegrationData(integrationResult.value);

        console.log("🚌 API Results:", {
          weekend: weekendResult,
          night: nightResult,
          rushHour: rushHourResult,
          lunchTime: lunchTimeResult,
          areaType: areaTypeResult,
          underutilized: underutilizedResult,
          integration: integrationResult,
        });
      } catch (err) {
        console.error("🚨 Traffic Analysis API error:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load traffic analysis data"
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
                <div className="space-y-3">
                  {areaTypeData?.data?.residential_stations?.map(
                    (item: any) => (
                      <div
                        key={item.station.station_id}
                        className="flex items-center justify-between p-3 bg-white rounded"
                      >
                        <div>
                          <div className="font-semibold text-base">
                            {item.station.station_name}
                          </div>
                          <div className="text-sm text-gray-600 mt-1">
                            오전 승차:{" "}
                            <span className="font-medium">
                              {item.morning_ride?.toLocaleString()}명
                            </span>{" "}
                            | 오후 하차:{" "}
                            <span className="font-medium">
                              {item.evening_alight?.toLocaleString()}명
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-blue-600 font-semibold text-sm">
                            주거지 특성도: {item.imbalance_ratio?.toFixed(1)}
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
                <div className="space-y-3">
                  {areaTypeData?.data?.business_stations?.map((item: any) => (
                    <div
                      key={item.station.station_id}
                      className="flex items-center justify-between p-3 bg-white rounded"
                    >
                      <div>
                        <div className="font-semibold text-base">
                          {item.station.station_name}
                        </div>
                        <div className="text-sm text-gray-600 mt-1">
                          오전 하차:{" "}
                          <span className="font-medium">
                            {item.morning_alight?.toLocaleString()}명
                          </span>{" "}
                          | 오후 승차:{" "}
                          <span className="font-medium">
                            {item.evening_ride?.toLocaleString()}명
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-green-600 font-semibold text-sm">
                          업무지 특성도: {item.imbalance_ratio?.toFixed(1)}
                        </div>
                      </div>
                    </div>
                  )) || (
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
                러시아워 고수요 정류장 (TOP 5)
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
                  <div className="space-y-4">
                    {rushHourData?.data?.morning_rush?.map(
                      (item: any, index: number) => (
                        <div
                          key={item.station.station_id}
                          className="p-4 bg-orange-50 rounded-lg"
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
                                  {item.station.station_name}
                                </h4>
                                <p className="text-base text-gray-600 mt-1">
                                  오전 승차:{" "}
                                  <span className="font-medium">
                                    {item.total_morning_rush?.toLocaleString()}
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
                  <div className="space-y-4">
                    {rushHourData?.data?.evening_rush?.map(
                      (item: any, index: number) => (
                        <div
                          key={item.station.station_id}
                          className="p-4 bg-orange-50 rounded-lg"
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
                                  {item.station.station_name}
                                </h4>
                                <p className="text-base text-gray-600 mt-1">
                                  오후 승차:{" "}
                                  <span className="font-medium">
                                    {item.total_evening_rush?.toLocaleString()}
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
                저활용 정류장 분석 (TOP 5)
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
              <div className="space-y-4">
                {underutilizedData?.data?.map((item: any) => (
                  <Alert
                    key={item.station.station_id}
                    className="border-l-4 border-l-red-500"
                  >
                    <AlertTriangle className="h-5 w-5" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-base">
                          {item.station.station_name}
                        </h4>
                        <Badge
                          variant="destructive"
                          className="text-base px-3 py-1"
                        >
                          효율성 {item.efficiency_score}%
                        </Badge>
                      </div>
                      <AlertDescription>
                        <div className="grid grid-cols-2 gap-4 text-base">
                          <div>
                            일평균 이용:{" "}
                            <span className="font-medium">
                              {item.avg_daily_passengers?.toLocaleString()}명
                            </span>
                          </div>
                          <div>
                            활용도:{" "}
                            <span className="font-medium">
                              {(item.utilization_rate * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 text-base">
                          <strong>노선 수:</strong> {item.connecting_routes}개 |{" "}
                          <strong>최대 이용:</strong>{" "}
                          {item.max_daily_passengers}명/일
                        </div>
                      </AlertDescription>
                    </div>
                  </Alert>
                )) || (
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
                주말 우세 정류장 (TOP 5)
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
              <CardDescription>주말 수요가 높은 관광/레저 지역</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {weekendData?.data?.map((item: any) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-blue-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-blue-600">
                          #{item.rank}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {item.station.station_name}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          주말 교통량:{" "}
                          <span className="font-medium">
                            {item.weekend_total_traffic?.toLocaleString()}명
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
                심야 고수요 정류장 (TOP 5)
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
              <div className="space-y-4">
                {nightData?.data?.map((item: any, index: number) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-purple-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-purple-600">
                          #{index + 1}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {item.station.station_name}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          심야 승차:{" "}
                          <span className="font-medium">
                            {item.total_night_ride?.toLocaleString()}명
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
                점심시간 특화 정류장 (TOP 5)
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
              <div className="space-y-4">
                {lunchTimeData?.data?.map((item: any, index: number) => (
                  <div
                    key={item.station.station_id}
                    className="flex items-center justify-between p-4 bg-green-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="text-xl font-bold text-green-600">
                          #{index + 1}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-base">
                          {item.station.station_name}
                        </h4>
                        <p className="text-base text-gray-600 mt-1">
                          점심시간 하차:{" "}
                          <span className="font-medium">
                            {item.total_lunch_alight?.toLocaleString()}명
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
