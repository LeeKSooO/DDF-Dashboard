"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Bus,
  Users,
  Clock,
  MapPin,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  CalendarIcon,
  Download,
  RefreshCw,
} from "lucide-react"
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

// Mock data
const dailyRides = [
  { time: "06:00", rides: 45, passengers: 67 },
  { time: "07:00", rides: 89, passengers: 134 },
  { time: "08:00", rides: 156, passengers: 234 },
  { time: "09:00", rides: 134, passengers: 201 },
  { time: "10:00", rides: 98, passengers: 147 },
  { time: "11:00", rides: 87, passengers: 131 },
  { time: "12:00", rides: 112, passengers: 168 },
  { time: "13:00", rides: 98, passengers: 147 },
  { time: "14:00", rides: 89, passengers: 134 },
  { time: "15:00", rides: 123, passengers: 185 },
  { time: "16:00", rides: 167, passengers: 251 },
  { time: "17:00", rides: 189, passengers: 284 },
  { time: "18:00", rides: 145, passengers: 218 },
  { time: "19:00", rides: 98, passengers: 147 },
  { time: "20:00", rides: 67, passengers: 101 },
  { time: "21:00", rides: 45, passengers: 68 },
]

const weeklyPerformance = [
  { day: "Mon", rides: 1234, efficiency: 87, avgWaitTime: 8.5 },
  { day: "Tue", rides: 1456, efficiency: 92, avgWaitTime: 7.2 },
  { day: "Wed", rides: 1389, efficiency: 89, avgWaitTime: 8.1 },
  { day: "Thu", rides: 1567, efficiency: 94, avgWaitTime: 6.8 },
  { day: "Fri", rides: 1678, efficiency: 91, avgWaitTime: 7.5 },
  { day: "Sat", rides: 1234, efficiency: 85, avgWaitTime: 9.2 },
  { day: "Sun", rides: 987, efficiency: 83, avgWaitTime: 9.8 },
]

const vehicleStatus = [
  { name: "운행 중", value: 45, color: "#22c55e" },
  { name: "정비 중", value: 8, color: "#f59e0b" },
  { name: "오프라인", value: 3, color: "#ef4444" },
]

const routePerformance = [
  { route: "노선 A", rides: 234, efficiency: 94, revenue: 1456 },
  { route: "노선 B", rides: 189, efficiency: 87, revenue: 1234 },
  { route: "노선 C", rides: 156, efficiency: 91, revenue: 1089 },
  { route: "노선 D", rides: 145, efficiency: 89, revenue: 987 },
  { route: "노선 E", rides: 134, efficiency: 85, revenue: 876 },
]

export function DRTDashboard() {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date())

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">DRT 분석 대시보드</h1>
            <p className="text-gray-600 mt-1">실시간 수요응답형 교통 인사이트</p>
          </div>
          <div className="flex items-center gap-3">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-[240px] justify-start text-left font-normal bg-transparent">
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {selectedDate ? selectedDate.toLocaleDateString("ko-KR") : "날짜 선택"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar mode="single" selected={selectedDate} onSelect={setSelectedDate} initialFocus />
              </PopoverContent>
            </Popover>
            <Select defaultValue="today">
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">오늘</SelectItem>
                <SelectItem value="week">이번 주</SelectItem>
                <SelectItem value="month">이번 달</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              내보내기
            </Button>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">오늘 총 운행 수</CardTitle>
              <Bus className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">1,847</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                어제 대비 +12.5%
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">활성 승객 수</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">2,764</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                어제 대비 +8.2%
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">평균 대기 시간</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">7.8 min</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <TrendingDown className="mr-1 h-3 w-3 text-green-500" />
                어제 대비 -2.1분
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">서비스 효율성</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">89.4%</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                어제 대비 +3.2%
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">개요</TabsTrigger>
            <TabsTrigger value="rides">운행 분석</TabsTrigger>
            <TabsTrigger value="vehicles">차량 현황</TabsTrigger>
            <TabsTrigger value="routes">노선 성과</TabsTrigger>
            <TabsTrigger value="alerts">알림</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Daily Ride Pattern */}
              <Card>
                <CardHeader>
                  <CardTitle>일일 운행 패턴</CardTitle>
                  <CardDescription>하루 종일 운행 및 승객 현황</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={dailyRides}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="rides"
                        stackId="1"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.6}
                      />
                      <Area
                        type="monotone"
                        dataKey="passengers"
                        stackId="2"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.6}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Vehicle Status */}
              <Card>
                <CardHeader>
                  <CardTitle>차량 현황</CardTitle>
                  <CardDescription>현재 차량 가용성</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={vehicleStatus}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {vehicleStatus.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex justify-center gap-4 mt-4">
                    {vehicleStatus.map((status) => (
                      <div key={status.name} className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: status.color }} />
                        <span className="text-sm">
                          {status.name}: {status.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Weekly Performance */}
            <Card>
              <CardHeader>
                <CardTitle>주간 성과 개요</CardTitle>
                <CardDescription>지난 주 운행, 효율성 및 대기 시간</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={weeklyPerformance}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="left" dataKey="rides" fill="#3b82f6" name="Total Rides" />
                    <Line yAxisId="right" type="monotone" dataKey="efficiency" stroke="#10b981" name="Efficiency %" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rides" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Ride Distribution</CardTitle>
                  <CardDescription>Peak and off-peak ride patterns</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={dailyRides}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="rides" stroke="#3b82f6" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Passenger Load Factor</CardTitle>
                  <CardDescription>Average passengers per ride</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={dailyRides}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Area type="monotone" dataKey="passengers" stroke="#10b981" fill="#10b981" fillOpacity={0.6} />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="vehicles" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>차량 활용도</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Vehicle #001</span>
                      <Badge variant="secondary">94% 활용</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Vehicle #002</span>
                      <Badge variant="secondary">87% 활용</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Vehicle #003</span>
                      <Badge variant="destructive">정비 중</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>연료 효율성</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">12.4 km/L</div>
                  <p className="text-sm text-muted-foreground">차량 평균</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>정비 일정</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">오늘 예정</span>
                      <Badge variant="destructive">3대 차량</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">이번 주 예정</span>
                      <Badge variant="secondary">7대 차량</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="routes" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>노선 성과 분석</CardTitle>
                <CardDescription>노선별 성과 지표</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {routePerformance.map((route) => (
                    <div key={route.route} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center gap-4">
                        <MapPin className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <h4 className="font-medium">{route.route}</h4>
                          <p className="text-sm text-muted-foreground">{route.rides}회 운행 오늘</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="text-sm font-medium">{route.efficiency}% 효율성</p>
                          <p className="text-sm text-muted-foreground">₩{route.revenue.toLocaleString()} 수익</p>
                        </div>
                        <Badge variant={route.efficiency > 90 ? "default" : "secondary"}>
                          {route.efficiency > 90 ? "우수" : "양호"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="alerts" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    중요 알림
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                      <div>
                        <p className="font-medium text-red-800">차량 #003 고장</p>
                        <p className="text-sm text-red-600">노선 A 영향 - 15분 전</p>
                      </div>
                      <Badge variant="destructive">중요</Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                      <div>
                        <p className="font-medium text-yellow-800">높은 대기 시간</p>
                        <p className="text-sm text-yellow-600">노선 B - 평균 12분</p>
                      </div>
                      <Badge variant="secondary">경고</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    시스템 상태
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span>GPS 추적</span>
                      <Badge variant="default">온라인</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>결제 시스템</span>
                      <Badge variant="default">온라인</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>모바일 앱</span>
                      <Badge variant="default">온라인</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>배차 시스템</span>
                      <Badge variant="default">온라인</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
