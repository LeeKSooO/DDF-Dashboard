"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  Target
} from "lucide-react"
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
import { apiService } from "@/lib/api"

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

interface TrafficAnalysisContentProps {
  selectedMonth: string
  selectedRegion: string
}

export function TrafficAnalysisContent({ selectedMonth, selectedRegion }: TrafficAnalysisContentProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // API 데이터 상태들
  const [weekendData, setWeekendData] = useState<any>(null)
  const [nightData, setNightData] = useState<any>(null)
  const [rushHourData, setRushHourData] = useState<any>(null)
  const [lunchTimeData, setLunchTimeData] = useState<any>(null)
  const [areaTypeData, setAreaTypeData] = useState<any>(null)
  const [underutilizedData, setUnderutilizedData] = useState<any>(null)
  const [integrationData, setIntegrationData] = useState<any>(null)

  // 데이터 로드
  useEffect(() => {
    const loadTrafficAnalysisData = async () => {
      try {
        setLoading(true)
        setError(null)
        
        console.log('🚌 Loading traffic analysis data for:', { selectedMonth, selectedRegion })
        
        // 분석할 구 목록 결정
        const districtsToAnalyze = selectedRegion === "전체" 
          ? ["강남구", "서초구", "송파구", "영등포구", "마포구"] // 샘플 구들
          : [selectedRegion]

        // 첫 번째 구로 데이터 로드 (데모용)
        const targetDistrict = districtsToAnalyze[0]
        const analysisMonth = "2025-07-01"

        // 모든 API 병렬 호출
        const [
          weekendResult,
          nightResult,
          rushHourResult,
          lunchTimeResult,
          areaTypeResult,
          underutilizedResult,
          integrationResult
        ] = await Promise.allSettled([
          apiService.getWeekendDominantStations(targetDistrict, analysisMonth, 5),
          apiService.getNightDemandStations(targetDistrict, analysisMonth, 5),
          apiService.getRushHourAnalysis(targetDistrict, analysisMonth),
          apiService.getLunchTimeStations(targetDistrict, analysisMonth, 5),
          apiService.getAreaTypeAnalysis(targetDistrict, analysisMonth),
          apiService.getUnderutilizedStations(targetDistrict, analysisMonth, 5),
          apiService.getIntegratedAnomalyAnalysis(targetDistrict, analysisMonth)
        ])

        // 성공한 결과들 저장
        if (weekendResult.status === 'fulfilled') setWeekendData(weekendResult.value)
        if (nightResult.status === 'fulfilled') setNightData(nightResult.value)
        if (rushHourResult.status === 'fulfilled') setRushHourData(rushHourResult.value)
        if (lunchTimeResult.status === 'fulfilled') setLunchTimeData(lunchTimeResult.value)
        if (areaTypeResult.status === 'fulfilled') setAreaTypeData(areaTypeResult.value)
        if (underutilizedResult.status === 'fulfilled') setUnderutilizedData(underutilizedResult.value)
        if (integrationResult.status === 'fulfilled') setIntegrationData(integrationResult.value)

        console.log('🚌 API Results:', {
          weekend: weekendResult,
          night: nightResult,
          rushHour: rushHourResult,
          lunchTime: lunchTimeResult,
          areaType: areaTypeResult,
          underutilized: underutilizedResult,
          integration: integrationResult
        })

      } catch (err) {
        console.error('🚨 Traffic Analysis API error:', err)
        setError(err instanceof Error ? err.message : 'Failed to load traffic analysis data')
      } finally {
        setLoading(false)
      }
    }

    loadTrafficAnalysisData()
  }, [selectedMonth, selectedRegion])

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
    )
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
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold">교통 패턴 분석 & 노선 최적화</h1>
          <p className="text-gray-600">
            {selectedRegion === "전체" ? "서울시 전체" : selectedRegion} · {monthNames[Number.parseInt(selectedMonth) - 1]}
          </p>
        </div>
      </div>

      {/* 탭 구조 */}
      <Tabs defaultValue="patterns" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="patterns">🔍 이상 패턴 감지</TabsTrigger>
          <TabsTrigger value="optimization">🚌 노선 최적화</TabsTrigger>
          <TabsTrigger value="integration">📊 통합 분석</TabsTrigger>
        </TabsList>

        {/* 이상 패턴 감지 탭 */}
        <TabsContent value="patterns" className="space-y-6">
          {/* 지역 특성별 정류장 분석 - 상단으로 이동 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-purple-500" />
                지역 특성별 정류장 분석
              </CardTitle>
              <CardDescription>출퇴근 승하차 패턴으로 주거지역과 업무지역 구분</CardDescription>
            </CardHeader>
            <CardContent>
              {/* 분석 기준 설명 */}
              <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                <h5 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                  📊 분석 기준 및 방법
                </h5>
                <div className="text-sm space-y-2 text-gray-700">
                  <div>• <strong>출퇴근 시간대:</strong> 06-09시(출근), 17-19시(퇴근) 평일 데이터</div>
                  <div>• <strong>신뢰성 확보:</strong> 1,000명 이상 교통량 정류장만 분석</div>
                  <div>• <strong>주거지역:</strong> 출근시간 승차↑, 퇴근시간 하차↑ (집→직장 패턴)</div>
                  <div>• <strong>업무지역:</strong> 출근시간 하차↑, 퇴근시간 승차↑ (직장 도착/출발 패턴)</div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 주거지역 특성 정류장 */}
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h5 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                    🏠 주거지역 특성
                  </h5>
                  <div className="space-y-3">
                    {areaTypeData?.data?.residential_stations?.map((item: any, index: number) => (
                      <div key={item.station.station_id} className="flex items-center justify-between p-2 bg-white rounded text-sm">
                        <div>
                          <div className="font-medium">{item.station.station_name}</div>
                          <div className="text-xs text-gray-500">
                            오전 승차: {item.morning_ride?.toLocaleString()}명 | 총 교통량: {item.total_traffic?.toLocaleString()}명
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-blue-600 font-medium text-xs">
                            주거지 특성도: {item.imbalance_ratio?.toFixed(1)}
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

                {/* 업무지역 특성 정류장 */}
                <div className="p-4 bg-green-50 rounded-lg">
                  <h5 className="font-medium text-green-800 mb-3 flex items-center gap-2">
                    🏢 업무지역 특성
                  </h5>
                  <div className="space-y-3">
                    {areaTypeData?.data?.business_stations?.map((item: any, index: number) => (
                      <div key={item.station.station_id} className="flex items-center justify-between p-2 bg-white rounded text-sm">
                        <div>
                          <div className="font-medium">{item.station.station_name}</div>
                          <div className="text-xs text-gray-500">
                            오전 하차: {item.morning_alight?.toLocaleString()}명 | 총 교통량: {item.total_traffic?.toLocaleString()}명
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-green-600 font-medium text-xs">
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

              {/* 활용 사례 */}
              <div className="mt-4 p-4 bg-purple-50 rounded-lg">
                <h5 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                  🎯 활용 사례
                </h5>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-purple-700">
                  <div>• 도시계획 및 토지이용 패턴 파악</div>
                  <div>• 주거지역 vs 업무지역 교통 수요 특성 분석</div>
                  <div>• 지역별 맞춤형 교통정책 수립</div>
                  <div>• 도시 기능 분석을 통한 인프라 개발 계획</div>
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
                  러시아워 고수요 정류장
                </CardTitle>
                <CardDescription>출퇴근 시간대(06-09시, 17-19시) 교통 집중 구간</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {/* 오전 러시아워 */}
                  <div>
                    <h5 className="font-medium text-orange-800 mb-3">🌅 오전 러시아워 (06-09시)</h5>
                    <div className="space-y-3">
                      {rushHourData?.data?.morning_rush?.map((item: any, index: number) => (
                        <div key={item.station.station_id} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                          <div className="flex items-center gap-3">
                            <div className="text-center">
                              <div className="text-lg font-bold text-orange-600">#{index + 1}</div>
                            </div>
                            <div>
                              <h4 className="font-medium">{item.station.station_name}</h4>
                              <p className="text-sm text-gray-600">
                                오전 승차: {item.total_morning_rush?.toLocaleString()}명
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge variant="outline">
                              {item.vs_district_avg?.toFixed(1)}x
                            </Badge>
                            <p className="text-xs text-gray-600 mt-1">구평균 대비</p>
                          </div>
                        </div>
                      )) || (
                        <div className="text-center text-gray-500 py-4">
                          데이터를 불러오는 중...
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 오후 러시아워 */}
                  <div>
                    <h5 className="font-medium text-orange-800 mb-3">🌆 오후 러시아워 (17-19시)</h5>
                    <div className="space-y-3">
                      {rushHourData?.data?.evening_rush?.map((item: any, index: number) => (
                        <div key={item.station.station_id} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                          <div className="flex items-center gap-3">
                            <div className="text-center">
                              <div className="text-lg font-bold text-orange-600">#{index + 1}</div>
                            </div>
                            <div>
                              <h4 className="font-medium">{item.station.station_name}</h4>
                              <p className="text-sm text-gray-600">
                                오후 승차: {item.total_evening_rush?.toLocaleString()}명
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge variant="outline">
                              {item.vs_district_avg?.toFixed(1)}x
                            </Badge>
                            <p className="text-xs text-gray-600 mt-1">구평균 대비</p>
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

            {/* 저활용 정류장 분석 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingDown className="h-5 w-5 text-red-500" />
                  저활용 정류장 분석
                </CardTitle>
                <CardDescription>운영 효율성 개선이 필요한 정류장들</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {underutilizedData?.data?.map((item: any) => (
                    <Alert key={item.station.station_id} className="border-l-4 border-l-red-500">
                      <AlertTriangle className="h-4 w-4" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium">{item.station.station_name}</h4>
                          <Badge variant="destructive">
                            효율성 {item.efficiency_score}%
                          </Badge>
                        </div>
                        <AlertDescription>
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>일평균 이용: {item.avg_daily_passengers?.toLocaleString()}명</div>
                            <div>활용도: {(item.utilization_rate * 100).toFixed(1)}%</div>
                          </div>
                          <div className="mt-2 text-sm">
                            <strong>노선 수:</strong> {item.connecting_routes}개 | <strong>최대 이용:</strong> {item.max_daily_passengers}명/일
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

          {/* 4개 카드들을 하단에 배치 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">주말 우세 정류장</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  TOP {weekendData?.data?.length || 0}
                </div>
                <p className="text-xs text-muted-foreground">관광/레저 지역</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">심야 고수요</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  TOP {nightData?.data?.length || 0}
                </div>
                <p className="text-xs text-muted-foreground">야간 활동 지역</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">점심시간 특화</CardTitle>
                <Users className="h-4 w-4 text-green-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">
                  TOP {lunchTimeData?.data?.length || 0}
                </div>
                <p className="text-xs text-muted-foreground">업무 중심 지역</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">지역 특성 분석</CardTitle>
                <MapPin className="h-4 w-4 text-purple-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-purple-600">
                  {((areaTypeData?.data?.residential_stations?.length || 0) + (areaTypeData?.data?.business_stations?.length || 0))}개
                </div>
                <p className="text-xs text-muted-foreground">주거/업무 분류</p>
              </CardContent>
            </Card>
          </div>

          {/* 나머지 카드들 (주말/심야) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 주말 우세 정류장 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-blue-500" />
                  주말 우세 정류장
                </CardTitle>
                <CardDescription>주말 수요가 높은 관광/레저 지역</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {weekendData?.data?.map((item: any, index: number) => (
                    <div key={item.station.station_id} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="text-center">
                          <div className="text-lg font-bold text-blue-600">#{item.rank}</div>
                        </div>
                        <div>
                          <h4 className="font-medium">{item.station.station_name}</h4>
                          <p className="text-sm text-gray-600">
                            주말 교통량: {item.weekend_total_traffic?.toLocaleString()}명
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="secondary">
                          {item.vs_district_avg?.toFixed(1)}x
                        </Badge>
                        <p className="text-xs text-gray-600 mt-1">구평균 대비</p>
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
                  심야 고수요 정류장
                </CardTitle>
                <CardDescription>23:00-03:00 시간대 높은 수요</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {nightData?.data?.map((item: any, index: number) => (
                    <div key={item.station.station_id} className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="text-center">
                          <div className="text-lg font-bold text-purple-600">#{index + 1}</div>
                        </div>
                        <div>
                          <h4 className="font-medium">{item.station.station_name}</h4>
                          <p className="text-sm text-gray-600">
                            심야 승차: {item.total_night_ride?.toLocaleString()}명
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {item.vs_district_avg?.toFixed(1)}x
                        </Badge>
                        <p className="text-xs text-gray-600 mt-1">구평균 대비</p>
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
                  점심시간 특화 정류장
                </CardTitle>
                <CardDescription>점심시간대(11:00-13:00) 하차 집중 구간</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {lunchTimeData?.data?.map((item: any, index: number) => (
                    <div key={item.station.station_id} className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="text-center">
                          <div className="text-lg font-bold text-green-600">#{index + 1}</div>
                        </div>
                        <div>
                          <h4 className="font-medium">{item.station.station_name}</h4>
                          <p className="text-sm text-gray-600">
                            점심시간 하차: {item.total_lunch_alight?.toLocaleString()}명
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">
                          {item.vs_district_avg?.toFixed(1)}x
                        </Badge>
                        <p className="text-xs text-gray-600 mt-1">구평균 대비</p>
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
        </TabsContent>

        {/* 노선 최적화 탭 */}
        <TabsContent value="optimization" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>🚌 패턴 기반 노선 최적화 제안</CardTitle>
              <CardDescription>발견된 이상 패턴을 바탕으로 한 노선 개선 방안</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* 주말 노선 최적화 */}
                {weekendData?.data && (
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <h5 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                      📅 주말 특화 노선 제안
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 주말 우세 정류장 {weekendData.data.length}곳을 연결하는 순환 노선 신설</div>
                      <div>• 토요일 09:00-18:00, 일요일 10:00-19:00 집중 운행</div>
                      <div>• 예상 이용객: 일 평균 {(weekendData.data.reduce((sum: number, s: any) => sum + (s.weekend_total_traffic || 0), 0) / 2).toLocaleString()}명</div>
                    </div>
                  </div>
                )}

                {/* 심야 노선 최적화 */}
                {nightData?.data && (
                  <div className="p-4 bg-purple-50 rounded-lg">
                    <h5 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                      🌙 심야 노선 최적화
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 심야 고수요 정류장 {nightData.data.length}곳 연계 강화</div>
                      <div>• 23:00-03:00 시간대 운행 빈도 20% 증가</div>
                      <div>• 안전 운행을 위한 CCTV 및 조명 설치 우선</div>
                    </div>
                  </div>
                )}

                {/* 저활용 정류장 최적화 */}
                {underutilizedData?.data && (
                  <div className="p-4 bg-red-50 rounded-lg">
                    <h5 className="font-medium text-red-800 mb-3 flex items-center gap-2">
                      🔧 저활용 정류장 최적화
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 저활용 정류장 {underutilizedData.data.length}곳 운영 방식 변경</div>
                      <div>• 수요응답형 운송(DRT) 서비스로 전환 검토</div>
                      <div>• 예상 비용 절감: 월 {(underutilizedData.data.length * 2.5).toFixed(1)}백만원</div>
                    </div>
                  </div>
                )}

                {/* 점심시간 최적화 */}
                {lunchTimeData?.data && (
                  <div className="p-4 bg-green-50 rounded-lg">
                    <h5 className="font-medium text-green-800 mb-3 flex items-center gap-2">
                      🍽️ 점심시간 특화 서비스
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 점심시간(11:00-13:00) 특화 정류장 {lunchTimeData.data.length}곳 집중 관리</div>
                      <div>• 업무 지구와 음식점 밀집 지역 연결 강화</div>
                      <div>• 배차 간격 단축: 5분 → 3분</div>
                    </div>
                  </div>
                )}

                {/* 러시아워 최적화 */}
                {rushHourData?.data?.morning_rush && (
                  <div className="p-4 bg-orange-50 rounded-lg">
                    <h5 className="font-medium text-orange-800 mb-3 flex items-center gap-2">
                      ⚡ 러시아워 교통 최적화
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 오전 러시아워(06-09시) 집중구간 {rushHourData.data.morning_rush.length}곳 증편</div>
                      <div>• 오후 러시아워(17-19시) 집중구간 {rushHourData.data.evening_rush?.length || 0}곳 증편</div>
                      <div>• 출퇴근 전용 급행 노선 신설 검토</div>
                      <div>• 러시아워 배차 간격: 10분 → 5분</div>
                    </div>
                  </div>
                )}

                {/* 지역 특성별 최적화 */}
                {areaTypeData?.data && (
                  <div className="p-4 bg-purple-50 rounded-lg">
                    <h5 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                      🏙️ 지역 특성별 맞춤 서비스
                    </h5>
                    <div className="text-sm space-y-2">
                      <div>• 주거지역 {areaTypeData.data.residential_stations?.length || 0}곳: 오전 출근 시간대 집중 운행</div>
                      <div>• 업무지역 {areaTypeData.data.business_stations?.length || 0}곳: 오후 퇴근 시간대 집중 운행</div>
                      <div>• 지역 특성에 맞는 차량 크기 및 노선 배치</div>
                      <div>• 주거-업무지역 간 직통 노선 강화</div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 통합 분석 탭 */}
        <TabsContent value="integration" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>📊 종합 분석 결과</CardTitle>
              <CardDescription>모든 패턴 분석을 종합한 최종 결과</CardDescription>
            </CardHeader>
            <CardContent>
              {integrationData ? (
                <div className="space-y-6">
                  {/* 통합 데이터가 있을 경우 */}
                  <div className="text-center text-gray-600">
                    통합 분석 데이터 표시 예정
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* 우선순위 높은 액션 아이템들 */}
                  <div className="p-4 bg-red-50 rounded-lg text-center">
                    <h5 className="font-medium text-red-800 mb-2">🚨 긴급 조치</h5>
                    <div className="text-3xl font-bold text-red-600">
                      {underutilizedData?.data?.length || 0}
                    </div>
                    <div className="text-sm text-red-600 mt-1">저활용 정류장</div>
                  </div>
                  
                  <div className="p-4 bg-blue-50 rounded-lg text-center">
                    <h5 className="font-medium text-blue-800 mb-2">📈 수요 증가</h5>
                    <div className="text-3xl font-bold text-blue-600">
                      {(weekendData?.data?.length || 0) + (nightData?.data?.length || 0)}
                    </div>
                    <div className="text-sm text-blue-600 mt-1">신규 수요 지역</div>
                  </div>
                  
                  <div className="p-4 bg-green-50 rounded-lg text-center">
                    <h5 className="font-medium text-green-800 mb-2">✅ 최적화 대상</h5>
                    <div className="text-3xl font-bold text-green-600">
                      {lunchTimeData?.data?.length || 0}
                    </div>
                    <div className="text-sm text-green-600 mt-1">효율 개선 가능</div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}