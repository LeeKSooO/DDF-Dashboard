"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle, TrendingUp, TrendingDown, Activity, Zap } from "lucide-react"
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

// 이상 패턴 감지 데이터 (API 명세서 기반)
const anomalyData = {
  analysisPeriod: "2025-07 vs 2025-06",
  anomalyThreshold: 20.0,
  summary: {
    totalRegionsAnalyzed: 25,
    significantIncreases: 3,
    significantDecreases: 2,
    stableRegions: 20,
  },
}

// 교통량 급증 지역
const trafficIncreases = [
  {
    regionName: "송파구",
    regionType: "district",
    currentTraffic: 1150,
    previousTraffic: 890,
    changePercentage: 29.2,
    severity: "HIGH",
    possibleCauses: ["신규 상업지구 개발", "지하철 연장 개통", "대형 쇼핑몰 오픈"],
  },
  {
    regionName: "강서구",
    regionType: "district",
    currentTraffic: 689,
    previousTraffic: 556,
    changePercentage: 23.9,
    severity: "HIGH",
    possibleCauses: ["김포공항 노선 확장", "신규 아파트 단지 입주"],
  },
  {
    regionName: "성동구",
    regionType: "district",
    currentTraffic: 823,
    previousTraffic: 678,
    changePercentage: 21.4,
    severity: "MEDIUM",
    possibleCauses: ["성수동 IT 기업 증가", "카페거리 활성화"],
  },
]

// 교통량 급감 지역
const trafficDecreases = [
  {
    regionName: "중구",
    regionType: "district",
    currentTraffic: 520,
    previousTraffic: 780,
    changePercentage: -33.3,
    severity: "HIGH",
    possibleCauses: ["업무지구 재택근무 증가", "관광객 감소"],
  },
  {
    regionName: "종로구",
    regionType: "district",
    currentTraffic: 945,
    previousTraffic: 1156,
    changePercentage: -18.2,
    severity: "MEDIUM",
    possibleCauses: ["전통시장 방문객 감소", "온라인 쇼핑 증가"],
  },
]

// 월별 변화 추이 데이터
const monthlyTrends = [
  { month: "2025-03", 송파구: 820, 중구: 890, 강서구: 520, 성동구: 650, 종로구: 1200 },
  { month: "2025-04", 송파구: 845, 중구: 865, 강서구: 535, 성동구: 665, 종로구: 1180 },
  { month: "2025-05", 송파구: 870, 중구: 840, 강서구: 548, 성동구: 678, 종로구: 1165 },
  { month: "2025-06", 송파구: 885, 중구: 820, 강서구: 556, 성동구: 690, 종로구: 1156 },
  { month: "2025-07", 송파구: 890, 중구: 780, 강서구: 556, 성동구: 678, 종로구: 1156 },
  { month: "2025-08", 송파구: 1150, 중구: 520, 강서구: 689, 성동구: 823, 종로구: 945 },
]

// 시간대별 이상 패턴
const hourlyAnomalies = [
  { hour: "06", normal: 45, anomaly: 78, type: "증가" },
  { hour: "07", normal: 125, anomaly: 98, type: "감소" },
  { hour: "08", normal: 185, anomaly: 245, type: "증가" },
  { hour: "14", normal: 76, anomaly: 45, type: "감소" },
  { hour: "18", normal: 178, anomaly: 220, type: "증가" },
  { hour: "22", normal: 58, anomaly: 89, type: "증가" },
]

interface AnomalyContentProps {
  selectedMonth: string
  selectedRegion: string
}

export function AnomalyContent({ selectedMonth, selectedRegion }: AnomalyContentProps) {
  return (
    <div className="space-y-6">
      {/* 이상 패턴 요약 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">분석 대상</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{anomalyData.summary.totalRegionsAnalyzed}개 구</div>
            <p className="text-xs text-muted-foreground">서울시 전체 자치구</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">급증 지역</CardTitle>
            <TrendingUp className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{anomalyData.summary.significantIncreases}개</div>
            <p className="text-xs text-muted-foreground">+20% 이상 증가</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">급감 지역</CardTitle>
            <TrendingDown className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{anomalyData.summary.significantDecreases}개</div>
            <p className="text-xs text-muted-foreground">-20% 이상 감소</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">안정 지역</CardTitle>
            <Zap className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{anomalyData.summary.stableRegions}개</div>
            <p className="text-xs text-muted-foreground">±20% 이내 변화</p>
          </CardContent>
        </Card>
      </div>

      {/* 이상 패턴 알림 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 교통량 급증 지역 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-red-500" />
              교통량 급증 지역
            </CardTitle>
            <CardDescription>전월 대비 20% 이상 증가한 지역</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {trafficIncreases.map((region, index) => (
                <Alert key={index} className="border-l-4 border-l-red-500">
                  <AlertTriangle className="h-4 w-4" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{region.regionName}</h4>
                      <Badge variant="destructive">+{region.changePercentage}%</Badge>
                    </div>
                    <AlertDescription className="mb-2">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>현재: {region.currentTraffic.toLocaleString()}명</div>
                        <div>이전: {region.previousTraffic.toLocaleString()}명</div>
                      </div>
                    </AlertDescription>
                    <AlertDescription>
                      <div className="text-sm">
                        <strong>가능한 원인:</strong>
                        <ul className="list-disc list-inside mt-1 space-y-1">
                          {region.possibleCauses.map((cause, i) => (
                            <li key={i}>{cause}</li>
                          ))}
                        </ul>
                      </div>
                    </AlertDescription>
                  </div>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* 교통량 급감 지역 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-blue-500" />
              교통량 급감 지역
            </CardTitle>
            <CardDescription>전월 대비 20% 이상 감소한 지역</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {trafficDecreases.map((region, index) => (
                <Alert key={index} className="border-l-4 border-l-blue-500">
                  <AlertTriangle className="h-4 w-4" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{region.regionName}</h4>
                      <Badge variant="secondary">{region.changePercentage}%</Badge>
                    </div>
                    <AlertDescription className="mb-2">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>현재: {region.currentTraffic.toLocaleString()}명</div>
                        <div>이전: {region.previousTraffic.toLocaleString()}명</div>
                      </div>
                    </AlertDescription>
                    <AlertDescription>
                      <div className="text-sm">
                        <strong>가능한 원인:</strong>
                        <ul className="list-disc list-inside mt-1 space-y-1">
                          {region.possibleCauses.map((cause, i) => (
                            <li key={i}>{cause}</li>
                          ))}
                        </ul>
                      </div>
                    </AlertDescription>
                  </div>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 월별 변화 추이 */}
      <Card>
        <CardHeader>
          <CardTitle>이상 지역 월별 변화 추이</CardTitle>
          <CardDescription>최근 6개월간 교통량 변화 패턴</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={monthlyTrends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="송파구" stroke="#ef4444" strokeWidth={3} name="송파구 (급증)" />
              <Line type="monotone" dataKey="중구" stroke="#3b82f6" strokeWidth={3} name="중구 (급감)" />
              <Line type="monotone" dataKey="강서구" stroke="#f59e0b" strokeWidth={2} name="강서구 (증가)" />
              <Line type="monotone" dataKey="성동구" stroke="#10b981" strokeWidth={2} name="성동구 (증가)" />
              <Line type="monotone" dataKey="종로구" stroke="#8b5cf6" strokeWidth={2} name="종로구 (감소)" />
            </LineChart>
          </ResponsiveContainer>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
          </CardDescription>
        </CardContent>
      </Card>

      {/* 시간대별 이상 패턴 */}
      <Card>
        <CardHeader>
          <CardTitle>시간대별 이상 패턴</CardTitle>
          <CardDescription>평소와 다른 시간대별 교통량 패턴</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={hourlyAnomalies}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="normal" fill="#94a3b8" name="평상시" />
              <Bar dataKey="anomaly" fill="#ef4444" name="이상 패턴" />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
            <h5 className="font-medium text-yellow-800 mb-2">🔍 패턴 분석 결과</h5>
            <div className="text-sm space-y-1">
              <div>• 오전 6시, 8시: 평소보다 높은 교통량 (재택근무 감소 영향)</div>
              <div>• 오전 7시: 평소보다 낮은 교통량 (출근 시간 분산)</div>
              <div>• 오후 2시: 평소보다 낮은 교통량 (점심시간 연장)</div>
              <div>• 오후 6시, 10시: 평소보다 높은 교통량 (야간 활동 증가)</div>
            </div>
          </div>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  )
}
