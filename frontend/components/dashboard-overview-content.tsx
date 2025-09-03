"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { MapPin, Users, Activity, Zap } from "lucide-react"
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts"
import { useState, useEffect } from "react"
import { apiService, HeatmapResponse } from "@/lib/api"

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

interface DashboardOverviewContentProps {
  selectedMonth: string
  selectedRegion: string
}

// 색상 팔레트 (참고 이미지와 유사하게)
const kpiColors = [
  "#60A5FA", // 파란색
  "#34D399", // 민트
  "#A78BFA", // 보라색
  "#F87171", // 빨간색
  "#FBBF24", // 노란색
  "#FB7185", // 핑크색
]

export function DashboardOverviewContent({ selectedMonth, selectedRegion }: DashboardOverviewContentProps) {
  const [heatmapData, setHeatmapData] = useState<HeatmapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // API 데이터 로드
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true)
        setError(null)
        
        console.log('📊 Loading dashboard overview data for month:', selectedMonth, 'region:', selectedRegion)
        
        const heatmapResponse = await apiService.getSeoulHeatmap(
          "2025-07-01", // 고정 날짜 사용
          true // 정류장 상세 정보 포함
        )
        
        console.log('📊 Heatmap API response:', heatmapResponse)
        setHeatmapData(heatmapResponse)
        
      } catch (err) {
        console.error('🚨 Dashboard API error:', err)
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
      } finally {
        setLoading(false)
      }
    }

    loadDashboardData()
  }, [selectedMonth, selectedRegion])

  // 선택된 지역에 따른 데이터 필터링
  const filteredDistricts = heatmapData?.districts.filter(d => 
    selectedRegion === "전체" ? true : d.district_name === selectedRegion
  ) || []

  // TOP 5 정류장 (전체 서울시에서)
  const topStations = heatmapData?.districts
    .flatMap(d => d.stations || [])
    .sort((a, b) => b.total_traffic - a.total_traffic)
    .slice(0, 5) || []

  // 구 평균 교통량 계산
  const districtAverageTraffic = heatmapData?.districts.length 
    ? heatmapData.districts.reduce((sum, d) => sum + d.total_traffic, 0) / heatmapData.districts.length
    : 0

  // 정류장 증강 배수 계산 (해당 구 평균 대비)
  const getStationAmplificationRatio = (stationTraffic: number, districtName: string) => {
    const district = heatmapData?.districts.find(d => d.district_name === districtName)
    if (!district || !district.stations?.length) return 0
    
    const districtStationAvg = district.stations.reduce((sum, s) => sum + s.total_traffic, 0) / district.stations.length
    return districtStationAvg > 0 ? stationTraffic / districtStationAvg : 0
  }

  // KPI 계산
  const kpiData = [
    {
      title: "총 교통량",
      value: Math.round((heatmapData?.statistics.total_seoul_traffic || 0) / 1000000).toFixed(1) + "M",
      subtitle: "서울시 전체",
      income: Math.round((heatmapData?.statistics.total_seoul_traffic || 0) / 1000).toLocaleString() + "K",
      color: kpiColors[0],
      icon: "🚌"
    },
    {
      title: "평균 구별 교통량",
      value: Math.round(districtAverageTraffic / 1000).toLocaleString() + "K",
      subtitle: "25개 구 평균",
      income: Math.round(districtAverageTraffic / 100) + "00명",
      color: kpiColors[1],
      icon: "📊"
    },
    {
      title: "최대 교통량 구",
      value: Math.round((heatmapData?.statistics.max_district_traffic || 0) / 1000).toLocaleString() + "K", 
      subtitle: "최고 수치",
      income: Math.round((heatmapData?.statistics.max_district_traffic || 0) / 100) + "00명",
      color: kpiColors[2],
      icon: "🔥"
    },
    {
      title: "총 정류장 수",
      value: Math.round((heatmapData?.statistics.total_stations || 0) / 1000).toFixed(1) + "K",
      subtitle: "버스정류장",
      income: (heatmapData?.statistics.total_stations || 0).toLocaleString() + "개",
      color: kpiColors[3],
      icon: "🚏"
    },
    {
      title: "승하차 비율",
      value: (() => {
        const totalRide = filteredDistricts.reduce((sum, d) => sum + (d.total_ride || 0), 0)
        const totalAlight = filteredDistricts.reduce((sum, d) => sum + (d.total_alight || 0), 0)
        return totalAlight > 0 ? (totalRide / totalAlight).toFixed(2) : '0.00'
      })(),
      subtitle: "승차/하차",
      income: (() => {
        const totalRide = filteredDistricts.reduce((sum, d) => sum + (d.total_ride || 0), 0)
        const totalAlight = filteredDistricts.reduce((sum, d) => sum + (d.total_alight || 0), 0)
        return `승차 ${Math.round(totalRide / 1000).toLocaleString()}K / 하차 ${Math.round(totalAlight / 1000).toLocaleString()}K`
      })(),
      color: kpiColors[4],
      icon: "⚖️"
    },
    {
      title: "최소 교통량 구",
      value: Math.round((heatmapData?.statistics.min_district_traffic || 0) / 1000).toLocaleString() + "K",
      subtitle: "최저 수치",
      income: Math.round((heatmapData?.statistics.min_district_traffic || 0) / 100) + "00명",
      color: kpiColors[5],
      icon: "📉"
    }
  ]

  // 구별 교통량 분포 데이터 (파이 차트용)
  const pieChartData = filteredDistricts
    .sort((a, b) => b.total_traffic - a.total_traffic)
    .slice(0, 5)
    .map((district, index) => ({
      name: district.district_name,
      value: Math.round(district.total_traffic / 1000),
      color: kpiColors[index % kpiColors.length]
    }))

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
      {/* KPI 카드 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {kpiData.map((kpi, index) => (
          <Card key={index} className="relative overflow-hidden" style={{ backgroundColor: kpi.color + '20' }}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{kpi.icon}</span>
                    <span className="text-sm font-medium text-gray-700">{kpi.title}</span>
                  </div>
                  <div className="text-2xl font-bold" style={{ color: kpi.color }}>
                    {kpi.value}
                  </div>
                  <div className="text-xs text-gray-600">{kpi.subtitle}</div>
                  
                  <div className="mt-3">
                    <div className="text-sm font-medium text-gray-800">{kpi.income}</div>
                  </div>
                </div>
                
                {/* 오른쪽 미니 차트 영역 (참고 이미지 스타일) */}
                <div className="w-16 h-12 opacity-60">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[{value: 10}, {value: 15}, {value: 12}, {value: 18}]}>
                      <Bar dataKey="value" fill={kpi.color} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 하단 분석 섹션 */}
      <Card>
        <CardHeader>
          <CardTitle>🚌 교통량 현황</CardTitle>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} {selectedRegion === "전체" ? "서울시 전체" : selectedRegion} 버스 이용량 분석
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-8">
            
            {/* 첫 번째 행: 구별 분포와 정류장 랭킹 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* 왼쪽: TOP 5 교통량 분포 */}
              <div>
                <h3 className="text-lg font-medium mb-4">📊 상위 5개 구 이용현황</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
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
                <h3 className="text-lg font-medium mb-4">🚏 인기 정류장 TOP 5</h3>
                <div className="space-y-3">
                  {topStations.map((station, index) => {
                    const stationDistrict = heatmapData?.districts.find(d => 
                      d.stations?.some(s => s.station_id === station.station_id)
                    )
                    const amplificationRatio = getStationAmplificationRatio(
                      station.total_traffic, 
                      stationDistrict?.district_name || ""
                    )

                    return (
                      <div key={station.station_id} 
                           className="flex items-center justify-between p-3 rounded-lg"
                           style={{ backgroundColor: kpiColors[index % kpiColors.length] + '20' }}>
                        <div className="flex items-center gap-3">
                          <div className="text-center">
                            <div className="text-sm font-bold" style={{ color: kpiColors[index % kpiColors.length] }}>
                              #{index + 1}
                            </div>
                          </div>
                          <div>
                            <div className="font-medium">{station.station_name}</div>
                            <div className="text-sm text-gray-600">{stationDistrict?.district_name}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold" style={{ color: kpiColors[index % kpiColors.length] }}>
                            {amplificationRatio.toFixed(1)}x
                          </div>
                          <div className="text-sm text-gray-600">해당구 평균 대비</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* 두 번째 행: 추가 분석 지표 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* 교통 집중도 분석 */}
              <Card className="p-4 bg-gradient-to-br from-blue-50 to-blue-100">
                <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                  🎯 교통 집중도
                </h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-blue-700">상위 5개구 점유율</span>
                    <span className="font-medium text-blue-800">
                      {(() => {
                        const top5Traffic = pieChartData.reduce((sum, item) => sum + item.value, 0) * 1000
                        const totalTraffic = heatmapData?.statistics.total_seoul_traffic || 1
                        return ((top5Traffic / totalTraffic) * 100).toFixed(1)
                      })()}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-blue-700">최대 정류장 교통량</span>
                    <span className="font-medium text-blue-800">
                      {Math.round((heatmapData?.statistics.max_station_traffic || 0) / 1000).toLocaleString()}K
                    </span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-sm font-medium text-blue-700">집중도 지수</span>
                    <span className="font-bold text-blue-800">
                      {(() => {
                        const maxStation = heatmapData?.statistics.max_station_traffic || 0
                        const avgStation = (heatmapData?.statistics.total_seoul_traffic || 0) / (heatmapData?.statistics.total_stations || 1)
                        const concentration = maxStation / avgStation
                        return concentration > 5 ? '매우 높음' : concentration > 3 ? '높음' : concentration > 2 ? '보통' : '낮음'
                      })()}
                    </span>
                  </div>
                </div>
              </Card>

              {/* 구별 격차 분석 */}
              <Card className="p-4 bg-gradient-to-br from-green-50 to-green-100">
                <h4 className="font-medium text-green-800 mb-3 flex items-center gap-2">
                  📊 구별 격차
                </h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-green-700">최고 이용구</span>
                    <span className="font-medium text-green-800">
                      {Math.round((heatmapData?.statistics.max_district_traffic || 0) / 1000).toLocaleString()}K
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-green-700">최저 이용구</span>
                    <span className="font-medium text-green-800">
                      {Math.round((heatmapData?.statistics.min_district_traffic || 0) / 1000).toLocaleString()}K
                    </span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-sm font-medium text-green-700">격차 비율</span>
                    <span className="font-bold text-green-800">
                      {((heatmapData?.statistics.max_district_traffic || 0) / (heatmapData?.statistics.min_district_traffic || 1)).toFixed(1)}:1
                    </span>
                  </div>
                </div>
              </Card>

              {/* 정류장 밀도 분석 */}
              <Card className="p-4 bg-gradient-to-br from-purple-50 to-purple-100">
                <h4 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                  🚏 정류장 현황
                </h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-purple-700">총 정류장</span>
                    <span className="font-medium text-purple-800">
                      {(heatmapData?.statistics.total_stations || 0).toLocaleString()}개
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-purple-700">구당 평균</span>
                    <span className="font-medium text-purple-800">
                      {Math.round((heatmapData?.statistics.total_stations || 0) / 25).toLocaleString()}개
                    </span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-sm font-medium text-purple-700">정류장당 이용량</span>
                    <span className="font-bold text-purple-800">
                      {Math.round((heatmapData?.statistics.total_seoul_traffic || 0) / (heatmapData?.statistics.total_stations || 1)).toLocaleString()}명
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>

    </div>
  )
}