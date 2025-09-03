"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, Users, Repeat, Star } from "lucide-react"
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

// 노선별 km당 승하차수 데이터
const routePassengerPerKm = [
  { route: "노선 A", passengersPerKm: 145, totalKm: 12.5, totalPassengers: 1813, efficiency: 92 },
  { route: "노선 B", passengersPerKm: 132, totalKm: 15.2, totalPassengers: 2006, efficiency: 88 },
  { route: "노선 C", passengersPerKm: 128, totalKm: 18.7, totalPassengers: 2394, efficiency: 85 },
  { route: "노선 D", passengersPerKm: 118, totalKm: 22.1, totalPassengers: 2608, efficiency: 82 },
  { route: "노선 E", passengersPerKm: 115, totalKm: 16.8, totalPassengers: 1932, efficiency: 79 },
  { route: "노선 F", passengersPerKm: 108, totalKm: 14.3, totalPassengers: 1544, efficiency: 76 },
  { route: "노선 G", passengersPerKm: 102, totalKm: 19.6, totalPassengers: 1999, efficiency: 73 },
  { route: "노선 H", passengersPerKm: 98, totalKm: 21.4, totalPassengers: 2097, efficiency: 71 },
]

// 노선별 이용 집중도 데이터
const routeConcentration = [
  {
    route: "노선 A",
    concentration: 95,
    peakHours: "07-09시, 18-20시",
    peakRatio: 68,
    avgWaitTime: 4.2,
    satisfaction: 4.6,
  },
  {
    route: "노선 C",
    concentration: 89,
    peakHours: "08-10시, 17-19시",
    peakRatio: 62,
    avgWaitTime: 5.1,
    satisfaction: 4.3,
  },
  {
    route: "노선 B",
    concentration: 85,
    peakHours: "07-09시, 18-20시",
    peakRatio: 59,
    avgWaitTime: 5.8,
    satisfaction: 4.1,
  },
  {
    route: "노선 D",
    concentration: 82,
    peakHours: "08-10시, 17-19시",
    peakRatio: 55,
    avgWaitTime: 6.2,
    satisfaction: 3.9,
  },
  {
    route: "노선 E",
    concentration: 78,
    peakHours: "09-11시, 16-18시",
    peakRatio: 52,
    avgWaitTime: 6.8,
    satisfaction: 3.7,
  },
]

// 재이용도 지표 데이터
const reuseRateData = [
  {
    route: "노선 A",
    reuseRate: 87,
    weeklyUsers: 2450,
    monthlyUsers: 8920,
    loyaltyScore: 92,
    avgTripsPerUser: 12.3,
  },
  {
    route: "노선 B",
    reuseRate: 82,
    weeklyUsers: 2180,
    monthlyUsers: 7850,
    loyaltyScore: 88,
    avgTripsPerUser: 11.1,
  },
  {
    route: "노선 C",
    reuseRate: 79,
    weeklyUsers: 2650,
    monthlyUsers: 9120,
    loyaltyScore: 85,
    avgTripsPerUser: 10.8,
  },
  {
    route: "노선 E",
    reuseRate: 76,
    weeklyUsers: 1890,
    monthlyUsers: 6740,
    loyaltyScore: 82,
    avgTripsPerUser: 9.9,
  },
  {
    route: "노선 D",
    reuseRate: 73,
    weeklyUsers: 2320,
    monthlyUsers: 8100,
    loyaltyScore: 79,
    avgTripsPerUser: 9.2,
  },
]

// 지역별 노선 성과 데이터
const regionalRouteData = {
  강남구: {
    topRoute: "노선 A",
    passengersPerKm: 145,
    concentration: 95,
    reuseRate: 87,
  },
  마포구: {
    topRoute: "노선 C",
    passengersPerKm: 128,
    concentration: 89,
    reuseRate: 79,
  },
  default: {
    topRoute: "노선 A",
    passengersPerKm: 145,
    concentration: 95,
    reuseRate: 87,
  },
}

// 시간대별 노선 이용 패턴
const hourlyRouteUsage = [
  { hour: "06", routeA: 45, routeB: 32, routeC: 38 },
  { hour: "07", routeA: 125, routeB: 98, routeC: 112 },
  { hour: "08", routeA: 185, routeB: 156, routeC: 168 },
  { hour: "09", routeA: 142, routeB: 128, routeC: 135 },
  { hour: "10", routeA: 89, routeB: 76, routeC: 82 },
  { hour: "11", routeA: 78, routeB: 68, routeC: 73 },
  { hour: "12", routeA: 95, routeB: 85, routeC: 89 },
  { hour: "13", routeA: 82, routeB: 74, routeC: 78 },
  { hour: "14", routeA: 76, routeB: 69, routeC: 72 },
  { hour: "15", routeA: 98, routeB: 88, routeC: 92 },
  { hour: "16", routeA: 128, routeB: 115, routeC: 121 },
  { hour: "17", routeA: 165, routeB: 148, routeC: 156 },
  { hour: "18", routeA: 178, routeB: 162, routeC: 169 },
  { hour: "19", routeA: 135, routeB: 122, routeC: 128 },
  { hour: "20", routeA: 92, routeB: 84, routeC: 87 },
  { hour: "21", routeA: 58, routeB: 52, routeC: 55 },
]

interface RouteAnalysisContentProps {
  selectedMonth: string
  selectedRegion: string
}

export function RouteAnalysisContent({ selectedMonth, selectedRegion }: RouteAnalysisContentProps) {
  // 선택된 지역의 데이터 가져오기
  const getRegionalData = (region: string) => {
    if (region === "전체") return regionalRouteData.default
    return regionalRouteData[region as keyof typeof regionalRouteData] || regionalRouteData.default
  }

  const regionalData = getRegionalData(selectedRegion)

  return (
    <div className="space-y-6">
      {/* 주요 지표 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base font-medium">최고 효율 노선</CardTitle>
            <Star className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{regionalData.topRoute}</div>
            <div className="flex items-center text-base text-muted-foreground">
              <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
              km당 {regionalData.passengersPerKm}명
            </div>
            <CardDescription>
              {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
            </CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base font-medium">이용 집중도</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{regionalData.concentration}%</div>
            <div className="flex items-center text-base text-muted-foreground">
              <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
              피크시간 집중도
            </div>
            <CardDescription>
              {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
            </CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base font-medium">재이용률</CardTitle>
            <Repeat className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{regionalData.reuseRate}%</div>
            <div className="flex items-center text-base text-muted-foreground">
              <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
              월간 재이용률
            </div>
            <CardDescription>
              {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
            </CardDescription>
          </CardContent>
        </Card>
      </div>

      {/* 노선별 km당 승하차수 */}
      <Card>
        <CardHeader>
          <CardTitle>노선별 km당 승하차수</CardTitle>
          <CardDescription>노선 효율성 비교 분석</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={routePassengerPerKm}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="route" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="passengersPerKm" fill="#3b82f6" name="km당 승하차수" />
              <Bar dataKey="efficiency" fill="#10b981" name="효율성 (%)" />
            </BarChart>
          </ResponsiveContainer>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
          </CardDescription>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 노선별 이용 집중도 순위 */}
        <Card>
          <CardHeader>
            <CardTitle>노선별 이용 집중도 순위</CardTitle>
            <CardDescription>피크시간 이용 집중도 기준</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {routeConcentration.map((route, index) => (
                <div key={route.route} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold">#{index + 1}</div>
                    </div>
                    <div>
                      <h4 className="font-medium">{route.route}</h4>
                      <p className="text-base text-muted-foreground">피크시간: {route.peakHours}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-base">대기시간: {route.avgWaitTime}분</span>
                        <span className="text-base">만족도: {route.satisfaction}/5.0</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-blue-600">{route.concentration}%</div>
                    <Badge variant={index < 2 ? "default" : index < 4 ? "secondary" : "outline"}>
                      {index < 2 ? "최우수" : index < 4 ? "우수" : "양호"}
                    </Badge>
                    <div className="mt-2">
                      <Progress value={route.peakRatio} className="w-20" />
                      <span className="text-base text-muted-foreground">피크비율 {route.peakRatio}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <CardDescription>
              {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
            </CardDescription>
          </CardContent>
        </Card>

        {/* 재이용도 지표 순위 */}
        <Card>
          <CardHeader>
            <CardTitle>재이용도 지표 순위</CardTitle>
            <CardDescription>고객 충성도 및 재이용률 기준</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {reuseRateData.map((route, index) => (
                <div key={route.route} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold">#{index + 1}</div>
                    </div>
                    <div>
                      <h4 className="font-medium">{route.route}</h4>
                      <p className="text-base text-muted-foreground">
                        주간 이용자: {route.weeklyUsers.toLocaleString()}명
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-base">월간: {route.monthlyUsers.toLocaleString()}명</span>
                        <span className="text-base">평균 {route.avgTripsPerUser}회/인</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-green-600">{route.reuseRate}%</div>
                    <Badge variant={index < 2 ? "default" : index < 4 ? "secondary" : "outline"}>
                      충성도 {route.loyaltyScore}점
                    </Badge>
                    <div className="mt-2">
                      <Progress value={route.reuseRate} className="w-20" />
                      <span className="text-base text-muted-foreground">재이용률</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <CardDescription>
              {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
            </CardDescription>
          </CardContent>
        </Card>
      </div>

      {/* 시간대별 노선 이용 패턴 */}
      <Card>
        <CardHeader>
          <CardTitle>시간대별 노선 이용 패턴</CardTitle>
          <CardDescription>주요 노선별 24시간 이용 현황</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={hourlyRouteUsage}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="routeA" stroke="#3b82f6" strokeWidth={2} name="노선 A" />
              <Line type="monotone" dataKey="routeB" stroke="#10b981" strokeWidth={2} name="노선 B" />
              <Line type="monotone" dataKey="routeC" stroke="#f59e0b" strokeWidth={2} name="노선 C" />
            </LineChart>
          </ResponsiveContainer>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
          </CardDescription>
        </CardContent>
      </Card>

      {/* 지역별 노선 성과 요약 */}
      <Card>
        <CardHeader>
          <CardTitle>{selectedRegion === "전체" ? "전체 지역" : selectedRegion} 노선 성과 요약</CardTitle>
          <CardDescription>선택된 지역의 주요 노선 성과 지표</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-blue-50 rounded-lg text-center">
              <h5 className="font-medium text-blue-800 mb-2">🚌 최고 성과 노선</h5>
              <div className="text-3xl font-bold text-blue-600">{regionalData.topRoute}</div>
              <div className="text-base text-blue-600 mt-1">종합 1위</div>
            </div>
            <div className="p-4 bg-green-50 rounded-lg text-center">
              <h5 className="font-medium text-green-800 mb-2">📊 km당 승하차수</h5>
              <div className="text-3xl font-bold text-green-600">{regionalData.passengersPerKm}명</div>
              <div className="text-base text-green-600 mt-1">최고 효율</div>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg text-center">
              <h5 className="font-medium text-purple-800 mb-2">🔄 재이용률</h5>
              <div className="text-3xl font-bold text-purple-600">{regionalData.reuseRate}%</div>
              <div className="text-base text-purple-600 mt-1">고객 충성도</div>
            </div>
          </div>
          <div className="mt-6 p-4 bg-yellow-50 rounded-lg">
            <h5 className="font-medium text-yellow-800 mb-3">📋 개선 제안</h5>
            <div className="text-base space-y-2">
              <div>• 최고 성과 노선의 운영 방식을 다른 노선에 적용</div>
              <div>• 이용 집중도가 낮은 시간대 서비스 최적화</div>
              <div>• 재이용률 향상을 위한 고객 만족도 개선</div>
              <div>• 노선별 특성에 맞는 맞춤형 서비스 제공</div>
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
