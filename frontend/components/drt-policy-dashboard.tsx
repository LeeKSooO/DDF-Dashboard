"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  MapPin,
  TrendingUp,
  Users,
  Bus,
  Clock,
  AlertTriangle,
  Activity,
  BarChart3,
  RefreshCw,
  Download,
  Maximize2,
  Minimize2,
  Target,
  Zap,
  Navigation,
} from "lucide-react"
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

// Types
interface DistrictData {
  district_code: string
  district_name: string
  total_traffic: number
  total_ride: number
  total_alight: number
  daily_average: number
  station_count: number
  traffic_rank: number
  traffic_density: number
  coordinates: [number, number]
  color: string
}

interface HourlyPattern {
  hour: string
  weekday: number
  weekend: number
  peak_type: "rush" | "normal" | "low"
}

interface AnomalyPattern {
  type: string
  severity: "high" | "medium" | "low"
  description: string
  affected_areas: string[]
  recommendation: string
}

// Mock data based on the specification
const seoulDistricts: DistrictData[] = [
  {
    district_code: "11680",
    district_name: "강남구",
    total_traffic: 8228452,
    total_ride: 4114226,
    total_alight: 4114226,
    daily_average: 529900,
    station_count: 503,
    traffic_rank: 1,
    traffic_density: 95.2,
    coordinates: [37.5172, 127.0473],
    color: "#dc2626",
  },
  {
    district_code: "11740",
    district_name: "강동구",
    total_traffic: 4567890,
    total_ride: 2283945,
    total_alight: 2283945,
    daily_average: 294025,
    station_count: 287,
    traffic_rank: 8,
    traffic_density: 67.8,
    coordinates: [37.5301, 127.1238],
    color: "#ea580c",
  },
  {
    district_code: "11305",
    district_name: "강북구",
    total_traffic: 3456789,
    total_ride: 1728394,
    total_alight: 1728395,
    daily_average: 222499,
    station_count: 198,
    traffic_rank: 12,
    traffic_density: 52.1,
    coordinates: [37.6396, 127.0257],
    color: "#d97706",
  },
  {
    district_code: "11500",
    district_name: "강서구",
    total_traffic: 5234567,
    total_ride: 2617283,
    total_alight: 2617284,
    daily_average: 337069,
    station_count: 342,
    traffic_rank: 6,
    traffic_density: 71.4,
    coordinates: [37.5509, 126.8495],
    color: "#f59e0b",
  },
  {
    district_code: "11620",
    district_name: "관악구",
    total_traffic: 4123456,
    total_ride: 2061728,
    total_alight: 2061728,
    daily_average: 265545,
    station_count: 245,
    traffic_rank: 10,
    traffic_density: 58.9,
    coordinates: [37.4781, 126.9515],
    color: "#65a30d",
  },
  {
    district_code: "11215",
    district_name: "광진구",
    total_traffic: 4789012,
    total_ride: 2394506,
    total_alight: 2394506,
    daily_average: 308323,
    station_count: 298,
    traffic_rank: 7,
    traffic_density: 69.2,
    coordinates: [37.5384, 127.0822],
    color: "#ea580c",
  },
  {
    district_code: "11530",
    district_name: "구로구",
    total_traffic: 5678901,
    total_ride: 2839450,
    total_alight: 2839451,
    daily_average: 365832,
    station_count: 378,
    traffic_rank: 5,
    traffic_density: 75.6,
    coordinates: [37.4954, 126.8874],
    color: "#f59e0b",
  },
  {
    district_code: "11545",
    district_name: "금천구",
    total_traffic: 2681659,
    total_ride: 1340829,
    total_alight: 1340830,
    daily_average: 172747,
    station_count: 156,
    traffic_rank: 25,
    traffic_density: 38.4,
    coordinates: [37.4569, 126.8955],
    color: "#2563eb",
  },
  {
    district_code: "11350",
    district_name: "노원구",
    total_traffic: 4567123,
    total_ride: 2283561,
    total_alight: 2283562,
    daily_average: 294008,
    station_count: 287,
    traffic_rank: 9,
    traffic_density: 65.3,
    coordinates: [37.6541, 127.0568],
    color: "#d97706",
  },
  {
    district_code: "11320",
    district_name: "도봉구",
    total_traffic: 3234567,
    total_traffic: 3234567,
    total_ride: 1617283,
    total_alight: 1617284,
    daily_average: 208394,
    station_count: 189,
    traffic_rank: 15,
    traffic_density: 46.7,
    coordinates: [37.6688, 127.0471],
    color: "#65a30d",
  },
]

const hourlyPatterns: HourlyPattern[] = [
  { hour: "00", weekday: 1250, weekend: 2100, peak_type: "low" },
  { hour: "01", weekday: 890, weekend: 1650, peak_type: "low" },
  { hour: "02", weekday: 650, weekend: 1200, peak_type: "low" },
  { hour: "03", weekday: 480, weekend: 890, peak_type: "low" },
  { hour: "04", weekday: 720, weekend: 650, peak_type: "low" },
  { hour: "05", weekday: 1850, weekend: 780, peak_type: "normal" },
  { hour: "06", weekday: 4200, weekend: 1200, peak_type: "normal" },
  { hour: "07", weekday: 8900, weekend: 2100, peak_type: "rush" },
  { hour: "08", weekday: 12500, weekend: 3200, peak_type: "rush" },
  { hour: "09", weekday: 9800, weekend: 4500, peak_type: "rush" },
  { hour: "10", weekday: 6700, weekend: 5800, peak_type: "normal" },
  { hour: "11", weekday: 7200, weekend: 6200, peak_type: "normal" },
  { hour: "12", weekday: 8500, weekend: 7100, peak_type: "normal" },
  { hour: "13", weekday: 7800, weekend: 6800, peak_type: "normal" },
  { hour: "14", weekday: 7100, weekend: 6500, peak_type: "normal" },
  { hour: "15", weekday: 7900, weekend: 6900, peak_type: "normal" },
  { hour: "16", weekday: 9200, weekend: 7200, peak_type: "normal" },
  { hour: "17", weekday: 11800, weekend: 7800, peak_type: "rush" },
  { hour: "18", weekday: 13200, weekend: 8500, peak_type: "rush" },
  { hour: "19", weekday: 10500, weekend: 8900, peak_type: "rush" },
  { hour: "20", weekday: 8200, weekend: 8200, peak_type: "normal" },
  { hour: "21", weekday: 6500, weekend: 7500, peak_type: "normal" },
  { hour: "22", weekday: 4800, weekend: 6800, peak_type: "normal" },
  { hour: "23", weekday: 2900, weekend: 4200, peak_type: "low" },
]

const anomalyPatterns: AnomalyPattern[] = [
  {
    type: "weekend-dominant",
    severity: "high",
    description: "주말 교통량이 평일보다 높은 이상 패턴",
    affected_areas: ["홍대입구", "강남역", "명동"],
    recommendation: "관광특화형 DRT 모델 적용 검토",
  },
  {
    type: "night-demand",
    severity: "medium",
    description: "심야시간 예상보다 높은 수요",
    affected_areas: ["강남구", "마포구"],
    recommendation: "심야 DRT 서비스 확대 검토",
  },
  {
    type: "high-volatility",
    severity: "medium",
    description: "교통량 변동성이 높은 지역",
    affected_areas: ["금천구", "구로구"],
    recommendation: "교통취약지형 DRT 모델 우선 적용",
  },
]

const drtModels = [
  {
    type: "출퇴근형",
    description: "출퇴근 시간대 집중 서비스",
    suitable_areas: ["강남구", "서초구", "영등포구"],
    efficiency: 89,
    cost_effectiveness: 76,
    color: "#3b82f6",
  },
  {
    type: "관광특화형",
    description: "관광지 연결 중심 서비스",
    suitable_areas: ["중구", "종로구", "마포구"],
    efficiency: 72,
    cost_effectiveness: 68,
    color: "#10b981",
  },
  {
    type: "교통취약지형",
    description: "교통 소외지역 접근성 개선",
    suitable_areas: ["금천구", "도봉구", "강북구"],
    efficiency: 65,
    cost_effectiveness: 85,
    color: "#f59e0b",
  },
]

export function DRTPolicyDashboard() {
  const [selectedMonth, setSelectedMonth] = useState("2025-07")
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null)
  const [isMapExpanded, setIsMapExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState("overview")

  // Calculate statistics
  const totalTraffic = useMemo(() => seoulDistricts.reduce((sum, district) => sum + district.total_traffic, 0), [])

  const maxTrafficDistrict = useMemo(
    () => seoulDistricts.reduce((max, district) => (district.total_traffic > max.total_traffic ? district : max)),
    [],
  )

  const totalStations = useMemo(() => seoulDistricts.reduce((sum, district) => sum + district.station_count, 0), [])

  const selectedDistrictData = selectedDistrict
    ? seoulDistricts.find((d) => d.district_name === selectedDistrict)
    : null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white">
                <BarChart3 className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">DRT 정책 의사결정 대시보드</h1>
                <p className="text-base text-gray-600">서울시 수요응답형 교통 분석 시스템</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Select value={selectedMonth} onValueChange={setSelectedMonth}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="2025-07">2025년 7월</SelectItem>
                <SelectItem value="2025-06">2025년 6월</SelectItem>
                <SelectItem value="2025-05">2025년 5월</SelectItem>
                <SelectItem value="2025-04">2025년 4월</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              새로고침
            </Button>

            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              내보내기
            </Button>
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Main Content */}
        <div className={`flex-1 transition-all duration-300 ${isMapExpanded ? "mr-0" : "mr-96"}`}>
          {/* Map Section */}
          <div className="relative h-[60vh] bg-white border-b">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
              <div className="text-center">
                <MapPin className="h-16 w-16 text-blue-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-700 mb-2">서울시 교통량 히트맵</h3>
                <p className="text-gray-500 mb-4">25개 자치구 실시간 교통 현황</p>
                <div className="flex items-center justify-center gap-4 text-base">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-blue-500 rounded"></div>
                    <span>낮음</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-yellow-500 rounded"></div>
                    <span>보통</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-red-500 rounded"></div>
                    <span>높음</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Map Controls */}
            <div className="absolute top-4 left-4 flex flex-col gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsMapExpanded(!isMapExpanded)}
                className="bg-white/90 backdrop-blur-sm"
              >
                {isMapExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
              <Button variant="outline" size="sm" className="bg-white/90 backdrop-blur-sm">
                <Navigation className="h-4 w-4" />
              </Button>
            </div>

            {/* District Selection Grid */}
            <div className="absolute bottom-4 left-4 right-4">
              <div className="bg-white/95 backdrop-blur-sm rounded-lg p-4 border">
                <h4 className="font-medium mb-3">자치구 선택</h4>
                <div className="grid grid-cols-5 gap-2">
                  {seoulDistricts.slice(0, 10).map((district) => (
                    <Button
                      key={district.district_code}
                      variant={selectedDistrict === district.district_name ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedDistrict(district.district_name)}
                      className="text-base"
                    >
                      {district.district_name}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Analytics Section */}
          <div className="p-6 space-y-6">
            {/* Key Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base font-medium">총 교통량</CardTitle>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{totalTraffic.toLocaleString()}명</div>
                  <div className="flex items-center text-base text-muted-foreground">
                    <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                    전월 대비 +8.2%
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base font-medium">최대 교통량 구</CardTitle>
                  <Target className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{maxTrafficDistrict.district_name}</div>
                  <div className="text-base text-muted-foreground">
                    {maxTrafficDistrict.total_traffic.toLocaleString()}명
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base font-medium">총 정류장 수</CardTitle>
                  <Bus className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{totalStations.toLocaleString()}개</div>
                  <div className="flex items-center text-base text-muted-foreground">
                    <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                    신규 정류장 +12개
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base font-medium">AI 예측 정확도</CardTitle>
                  <Zap className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">94.8%</div>
                  <div className="flex items-center text-base text-muted-foreground">
                    <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                    MSTGCN 모델
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Hourly Traffic Pattern */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5" />
                    시간대별 교통 패턴
                  </CardTitle>
                  <CardDescription>평일 vs 주말 교통량 비교</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={hourlyPatterns}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="hour" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="weekday"
                        stackId="1"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.6}
                        name="평일"
                      />
                      <Area
                        type="monotone"
                        dataKey="weekend"
                        stackId="2"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.6}
                        name="주말"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* District Ranking */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    구별 교통량 순위
                  </CardTitle>
                  <CardDescription>상위 10개 자치구</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={seoulDistricts.slice(0, 8)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="district_name" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="total_traffic" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            {/* DRT Model Recommendations */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  DRT 모델 추천
                </CardTitle>
                <CardDescription>지역 특성에 맞는 최적 DRT 모델</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {drtModels.map((model) => (
                    <div key={model.type} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="font-medium">{model.type}</h4>
                        <Badge style={{ backgroundColor: model.color, color: "white" }}>추천</Badge>
                      </div>
                      <p className="text-base text-gray-600 mb-3">{model.description}</p>
                      <div className="space-y-2">
                        <div className="flex justify-between text-base">
                          <span>효율성</span>
                          <span>{model.efficiency}%</span>
                        </div>
                        <Progress value={model.efficiency} className="h-2" />
                        <div className="flex justify-between text-base">
                          <span>비용 효과성</span>
                          <span>{model.cost_effectiveness}%</span>
                        </div>
                        <Progress value={model.cost_effectiveness} className="h-2" />
                      </div>
                      <div className="mt-3">
                        <p className="text-base text-gray-500">적합 지역:</p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {model.suitable_areas.map((area) => (
                            <Badge key={area} variant="outline" className="text-base">
                              {area}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Anomaly Detection */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" />
                  이상 패턴 감지
                </CardTitle>
                <CardDescription>AI 기반 교통 이상 상황 분석</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {anomalyPatterns.map((pattern, index) => (
                    <Alert
                      key={index}
                      className={`border-l-4 ${
                        pattern.severity === "high"
                          ? "border-l-red-500"
                          : pattern.severity === "medium"
                            ? "border-l-yellow-500"
                            : "border-l-blue-500"
                      }`}
                    >
                      <AlertTriangle className="h-4 w-4" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium">{pattern.description}</h4>
                          <Badge
                            variant={
                              pattern.severity === "high"
                                ? "destructive"
                                : pattern.severity === "medium"
                                  ? "secondary"
                                  : "outline"
                            }
                          >
                            {pattern.severity === "high" ? "높음" : pattern.severity === "medium" ? "보통" : "낮음"}
                          </Badge>
                        </div>
                        <AlertDescription className="mb-2">
                          영향 지역: {pattern.affected_areas.join(", ")}
                        </AlertDescription>
                        <AlertDescription className="text-blue-600">💡 {pattern.recommendation}</AlertDescription>
                      </div>
                    </Alert>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Side Panel */}
        {!isMapExpanded && (
          <div className="w-96 bg-white border-l border-gray-200 p-6 overflow-y-auto">
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold mb-4">
                  {selectedDistrictData ? `${selectedDistrictData.district_name} 상세 정보` : "지역을 선택하세요"}
                </h3>

                {selectedDistrictData ? (
                  <div className="space-y-4">
                    <Card>
                      <CardContent className="p-4">
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">총 교통량</span>
                            <span className="font-medium">{selectedDistrictData.total_traffic.toLocaleString()}명</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">일평균</span>
                            <span className="font-medium">{selectedDistrictData.daily_average.toLocaleString()}명</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">정류장 수</span>
                            <span className="font-medium">{selectedDistrictData.station_count}개</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">교통량 순위</span>
                            <Badge variant="outline">#{selectedDistrictData.traffic_rank}</Badge>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">교통 밀도</span>
                            <span className="font-medium">{selectedDistrictData.traffic_density}%</span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">승하차 분석</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">총 승차</span>
                            <span className="font-medium text-blue-600">
                              {selectedDistrictData.total_ride.toLocaleString()}명
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">총 하차</span>
                            <span className="font-medium text-green-600">
                              {selectedDistrictData.total_alight.toLocaleString()}명
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-base text-gray-600">순 유입</span>
                            <span
                              className={`font-medium ${
                                selectedDistrictData.total_ride - selectedDistrictData.total_alight > 0
                                  ? "text-green-600"
                                  : "text-red-600"
                              }`}
                            >
                              {selectedDistrictData.total_ride - selectedDistrictData.total_alight > 0 ? "+" : ""}
                              {(selectedDistrictData.total_ride - selectedDistrictData.total_alight).toLocaleString()}명
                            </span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">DRT 적합성</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {drtModels.map((model) => {
                            const isRecommended = model.suitable_areas.includes(selectedDistrictData.district_name)
                            return (
                              <div key={model.type} className="flex items-center justify-between">
                                <span className="text-base">{model.type}</span>
                                <Badge variant={isRecommended ? "default" : "outline"}>
                                  {isRecommended ? "추천" : "검토"}
                                </Badge>
                              </div>
                            )
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <MapPin className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">지도에서 자치구를 선택하면</p>
                    <p className="text-gray-500">상세 분석 정보를 확인할 수 있습니다</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
