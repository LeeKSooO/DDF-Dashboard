"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { MapPin, TrendingUp, Users, Navigation, Activity, Clock, TrendingDown, Zap } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { useState, useEffect, useRef } from "react"
import { apiService, HeatmapResponse, DistrictData, StationData } from "@/lib/api"
import { HeatmapSeoulMap, HeatmapSeoulMapRef } from "@/components/map/heatmap-seoul-map"

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

interface HeatmapContentProps {
  selectedMonth: string
  selectedRegion: string
}

export function HeatmapContent({ selectedMonth, selectedRegion }: HeatmapContentProps) {
  const [viewMode, setViewMode] = useState<"district" | "station">("district")
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null)
  const [highlightTopStations, setHighlightTopStations] = useState(false)
  const [heatmapData, setHeatmapData] = useState<HeatmapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // 이상 패턴 분석 데이터 상태들
  const [selectedPattern, setSelectedPattern] = useState<string | null>(null)
  const [weekendData, setWeekendData] = useState<any>(null)
  const [nightData, setNightData] = useState<any>(null)
  const [rushHourData, setRushHourData] = useState<any>(null)
  const [lunchTimeData, setLunchTimeData] = useState<any>(null)
  const [areaTypeData, setAreaTypeData] = useState<any>(null)
  const [underutilizedData, setUnderutilizedData] = useState<any>(null)
  const mapRef = useRef<HeatmapSeoulMapRef>(null)

  // API 데이터 로드
  useEffect(() => {
    const loadHeatmapData = async () => {
      try {
        setLoading(true)
        setError(null)
        
        console.log('🗺️ Loading heatmap and pattern data for:', { selectedMonth, selectedRegion })
        
        // 지역이 변경되면 패턴 선택 초기화
        setSelectedPattern(null)
        console.log('🔄 패턴 선택 초기화 - 지역 변경:', selectedRegion)
        
        const analysisMonth = "2025-07-01"
        
        // 히트맵 데이터 로드
        const heatmapResponse = await apiService.getSeoulHeatmap(
          analysisMonth,
          true // 항상 정류장 상세 정보 포함
        )
        
        console.log('🗺️ Heatmap API response:', heatmapResponse)
        setHeatmapData(heatmapResponse)
        
        // 선택된 지역에 따른 이상 패턴 분석 데이터 로드
        if (selectedRegion !== "전체") {
          console.log('📊 Loading pattern analysis for district:', selectedRegion)
          
          // 모든 패턴 분석 API 병렬 호출
          const [
            weekendResult,
            nightResult, 
            rushHourResult,
            lunchTimeResult,
            areaTypeResult,
            underutilizedResult
          ] = await Promise.allSettled([
            apiService.getWeekendDominantStations(selectedRegion, analysisMonth, 5),
            apiService.getNightDemandStations(selectedRegion, analysisMonth, 5),
            apiService.getRushHourAnalysis(selectedRegion, analysisMonth),
            apiService.getLunchTimeStations(selectedRegion, analysisMonth, 5),
            apiService.getAreaTypeAnalysis(selectedRegion, analysisMonth),
            apiService.getUnderutilizedStations(selectedRegion, analysisMonth, 5)
          ])

          // 성공한 결과들 저장
          if (weekendResult.status === 'fulfilled') setWeekendData(weekendResult.value)
          if (nightResult.status === 'fulfilled') setNightData(nightResult.value)
          if (rushHourResult.status === 'fulfilled') setRushHourData(rushHourResult.value)
          if (lunchTimeResult.status === 'fulfilled') setLunchTimeData(lunchTimeResult.value)
          if (areaTypeResult.status === 'fulfilled') setAreaTypeData(areaTypeResult.value)
          if (underutilizedResult.status === 'fulfilled') setUnderutilizedData(underutilizedResult.value)
        } else {
          // 전체 선택시 패턴 데이터 초기화
          setWeekendData(null)
          setNightData(null) 
          setRushHourData(null)
          setLunchTimeData(null)
          setAreaTypeData(null)
          setUnderutilizedData(null)
        }
        
      } catch (err) {
        console.error('🚨 Heatmap API error:', err)
        setError(err instanceof Error ? err.message : 'Failed to load heatmap data')
      } finally {
        setLoading(false)
      }
    }

    loadHeatmapData()
  }, [selectedMonth, selectedRegion]) // selectedRegion 추가

  // 선택된 지역에 따른 데이터 필터링
  const filteredDistricts = heatmapData?.districts.filter(d => 
    selectedRegion === "전체" ? true : d.district_name === selectedRegion
  ) || []
  
  // 랭킹을 위한 정렬된 구 데이터
  const rankedDistricts = [...filteredDistricts]
    .sort((a, b) => b.total_traffic - a.total_traffic)
    .map((district, index) => ({ ...district, rank: index + 1 }))
  
  // 상위 정류장 데이터 (모든 구의 정류장 중 상위 5개)
  const topStations = heatmapData?.districts
    .flatMap(d => d.stations || [])
    .sort((a, b) => b.total_traffic - a.total_traffic)
    .slice(0, 5) || []
  
  // 선택된 패턴에 따른 정류장 데이터 추출
  const getPatternStations = () => {
    if (!selectedPattern || (selectedRegion === "전체" && !selectedDistrict)) return []
    
    switch (selectedPattern) {
      case 'weekend':
        return weekendData?.data?.map((item: any) => ({
          ...item.station,
          patternType: 'weekend',
          patternColor: '#3B82F6', // blue
          patternInfo: `주말 교통량: ${item.weekend_total_traffic?.toLocaleString()}명`
        })) || []
        
      case 'night':
        return nightData?.data?.map((item: any) => ({
          ...item.station,
          patternType: 'night', 
          patternColor: '#8B5CF6', // purple
          patternInfo: `심야 승차: ${item.total_night_ride?.toLocaleString()}명`
        })) || []
        
      case 'underutilized':
        return underutilizedData?.data?.map((item: any) => ({
          ...item.station,
          patternType: 'underutilized',
          patternColor: '#EF4444', // red
          patternInfo: `효율성: ${item.efficiency_score}% | 일평균: ${item.avg_daily_passengers?.toLocaleString()}명`
        })) || []
        
      case 'lunchtime':
        return lunchTimeData?.data?.map((item: any) => ({
          ...item.station,
          patternType: 'lunchtime',
          patternColor: '#10B981', // green
          patternInfo: `점심시간 하차: ${item.total_lunch_alight?.toLocaleString()}명`
        })) || []
        
      case 'rushhour':
        const morningStations = rushHourData?.data?.morning_rush?.map((item: any) => ({
          ...item.station,
          patternType: 'rushhour',
          patternColor: '#F97316', // orange
          patternInfo: `오전 승차: ${item.total_morning_rush?.toLocaleString()}명`,
          rushType: 'morning'
        })) || []
        
        const eveningStations = rushHourData?.data?.evening_rush?.map((item: any) => ({
          ...item.station,
          patternType: 'rushhour',
          patternColor: '#EA580C', // darker orange
          patternInfo: `오후 승차: ${item.total_evening_rush?.toLocaleString()}명`,
          rushType: 'evening'
        })) || []
        
        return [...morningStations, ...eveningStations]
        
      case 'areatype':
        const residentialStations = areaTypeData?.data?.residential_stations?.map((item: any) => ({
          ...item.station,
          patternType: 'areatype',
          patternColor: '#0EA5E9', // sky blue - 하늘색으로 변경
          patternInfo: `주거지역 | 오전승차: ${item.morning_ride?.toLocaleString()}명`,
          areaType: 'residential'
        })) || []
        
        const businessStations = areaTypeData?.data?.business_stations?.map((item: any) => ({
          ...item.station,
          patternType: 'areatype', 
          patternColor: '#8B5CF6', // purple
          patternInfo: `업무지역 | 오전하차: ${item.morning_alight?.toLocaleString()}명`,
          areaType: 'business'
        })) || []
        
        return [...residentialStations, ...businessStations]
        
      default:
        return []
    }
  }
  
  const patternStations = getPatternStations()
  
  // 지도에서 구 클릭 시 호출
  const handleDistrictClick = (districtName: string, districtCode: string) => {
    console.log(`District clicked: ${districtName} (${districtCode})`)
    
    // 새로운 구를 선택할 때 패턴 선택 초기화
    if (selectedDistrict !== districtName) {
      setSelectedPattern(null)
      console.log('🔄 패턴 선택 초기화 - 새로운 구 선택:', districtName)
    }
    
    setSelectedDistrict(districtName)
  }

  // 지도에서 구 클릭 시 해당 구의 패턴 데이터 로드
  useEffect(() => {
    if (!selectedDistrict) return

    const loadDistrictPatternData = async () => {
      try {
        console.log('📊 Loading pattern analysis for clicked district:', selectedDistrict)
        
        const analysisMonth = "2025-07-01"
        
        // 클릭된 구의 패턴 분석 데이터 로드 (기존 selectedRegion 패턴과 동일)
        const [
          weekendResult,
          nightResult, 
          rushHourResult,
          lunchTimeResult,
          areaTypeResult,
          underutilizedResult
        ] = await Promise.allSettled([
          apiService.getWeekendDominantStations(selectedDistrict, analysisMonth, 5),
          apiService.getNightDemandStations(selectedDistrict, analysisMonth, 5),
          apiService.getRushHourAnalysis(selectedDistrict, analysisMonth),
          apiService.getLunchTimeStations(selectedDistrict, analysisMonth, 5),
          apiService.getAreaTypeAnalysis(selectedDistrict, analysisMonth),
          apiService.getUnderutilizedStations(selectedDistrict, analysisMonth, 5)
        ])

        // 성공한 결과들 저장
        if (weekendResult.status === 'fulfilled') setWeekendData(weekendResult.value)
        if (nightResult.status === 'fulfilled') setNightData(nightResult.value)
        if (rushHourResult.status === 'fulfilled') setRushHourData(rushHourResult.value)
        if (lunchTimeResult.status === 'fulfilled') setLunchTimeData(lunchTimeResult.value)
        if (areaTypeResult.status === 'fulfilled') setAreaTypeData(areaTypeResult.value)
        if (underutilizedResult.status === 'fulfilled') setUnderutilizedData(underutilizedResult.value)

        console.log('✅ Pattern data loaded for district:', selectedDistrict)
      } catch (err) {
        console.error('🚨 Failed to load district pattern data:', err)
      }
    }

    loadDistrictPatternData()
  }, [selectedDistrict]) // selectedDistrict 변경 시 실행

  // 지도 중심 이동 함수
  const handleResetMapCenter = () => {
    if (mapRef.current) {
      mapRef.current.resetToSeoulCenter()
    }
  }

  // 로딩 상태 표시
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">히트맵 데이터 로딩 중...</p>
          </div>
        </div>
      </div>
    )
  }

  // 에러 상태 표시
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
    )
  }

  return (
    <div className="space-y-6">
      {/* 컨트롤 패널 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            서울시 교통량 히트맵 제어판
          </CardTitle>
          <CardDescription>지도 시각화 옵션 및 필터 설정</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-base font-medium">보기 모드:</label>
              <Select value={viewMode} onValueChange={(value: "district" | "station") => setViewMode(value)}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="district">구별 집계</SelectItem>
                  <SelectItem value="station">정류장별</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* TOP 5 정류장 강조 옵션 */}
            {viewMode === "station" && (
              <div className="flex items-center gap-2">
                <input 
                  type="checkbox" 
                  id="highlight-top-stations" 
                  checked={highlightTopStations}
                  onChange={(e) => setHighlightTopStations(e.target.checked)}
                  className="w-4 h-4 text-orange-600 bg-gray-100 border-gray-300 rounded focus:ring-orange-500"
                />
                <label htmlFor="highlight-top-stations" className="text-base font-medium text-orange-700">
                  ⭐ TOP 5 정류장 강조
                </label>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleResetMapCenter}>
              <Navigation className="h-4 w-4 mr-2" />
              지도 중심 이동
            </Button>
            {viewMode === "station" && selectedDistrict && (
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => {
                  setSelectedDistrict(null)
                  setSelectedPattern(null) // 패턴도 함께 초기화
                  console.log('🔄 패턴 선택 초기화 - 전체 정류장 보기')
                }}
                className="ml-2"
              >
                전체 정류장 보기
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 메인 히트맵 */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>서울시 교통량 히트맵</CardTitle>
              <CardDescription>{viewMode === "district" ? "25개 자치구별" : "정류장별"} 교통량 시각화</CardDescription>
            </CardHeader>
            <CardContent>
              <HeatmapSeoulMap
                ref={mapRef}
                onDistrictClick={handleDistrictClick}
                selectedDistrict={selectedDistrict || undefined}
                districts={filteredDistricts}
                viewMode={viewMode}
                loading={loading}
                highlightTopStations={highlightTopStations}
                selectedPattern={selectedPattern}
                patternStations={patternStations}
              />
              <CardDescription className="mt-2">
                {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
                {viewMode === "station" && selectedDistrict && (
                  <span className="ml-4 text-blue-600 font-medium">
                    | {selectedDistrict} 정류장만 표시 중
                  </span>
                )}
                {viewMode === "station" && !selectedDistrict && (
                  <span className="ml-4 text-gray-500">
                    | 구를 클릭하여 해당 구의 정류장만 확인
                  </span>
                )}
              </CardDescription>
              
              {/* 지도 하단에 추가 정보 표시 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                {/* 주요 정류장 - 지도 하단 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    주요 정류장
                  </h4>
                  <div className="space-y-2">
                    {topStations.length > 0 ? (
                      topStations.slice(0, 3).map((station, index) => (
                        <div key={station.station_id} className="flex items-center justify-between p-2 bg-white rounded text-base">
                          <div className="flex items-center gap-2">
                            <div className="text-base font-bold text-blue-600">#{index + 1}</div>
                            <div>
                              <div className="font-medium">{station.station_name}</div>
                              <div className="text-base text-gray-500">
                                {heatmapData?.districts.find(d => 
                                  d.stations?.some(s => s.station_id === station.station_id)
                                )?.district_name}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-medium text-green-600">{station.total_traffic.toLocaleString()}</div>
                            <div className="text-base text-gray-500">명/월</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-2 text-gray-500 text-base">
                        {viewMode === 'station' ? '정류장 데이터를 로딩 중입니다...' : '정류장별 모드를 선택하세요'}
                      </div>
                    )}
                  </div>
                </div>

                {/* 통계 요약 - 지도 하단 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-medium text-gray-800 mb-3">📊 핵심 통계</h4>
                  <div className="space-y-2 text-base">
                    <div className="flex justify-between p-2 bg-white rounded">
                      <span>총 교통량:</span>
                      <span className="font-medium">
                        {heatmapData?.statistics.total_seoul_traffic.toLocaleString()}명
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-white rounded">
                      <span>평균 승하차비율:</span>
                      <span className="font-medium text-blue-600">
                        {(() => {
                          const totalRide = filteredDistricts.reduce((sum, d) => sum + (d.total_ride || 0), 0)
                          const totalAlight = filteredDistricts.reduce((sum, d) => sum + (d.total_alight || 0), 0)
                          return totalAlight > 0 ? (totalRide / totalAlight).toFixed(2) : 'N/A'
                        })()}
                      </span>
                    </div>
                    <div className="flex justify-between p-2 bg-white rounded">
                      <span>최대 구 교통량:</span>
                      <span className="font-medium">
                        {heatmapData?.statistics.max_district_traffic.toLocaleString()}명
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 사이드 패널 - 이상 패턴 분석 */}
        <div>
          {/* 이상 패턴 탐지 버튼들 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                이상 패턴 탐지
              </CardTitle>
              <CardDescription>
                {selectedRegion === "전체" && !selectedDistrict
                  ? "구를 선택하면 해당 지역의 패턴을 분석합니다" 
                  : `${selectedDistrict || selectedRegion} 지역의 교통 패턴 분석`
                }
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedRegion === "전체" && !selectedDistrict ? (
                <div className="text-center text-gray-500 py-8">
                  <Activity className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p className="text-base font-medium">구를 선택해주세요</p>
                  <p className="text-base">해당 지역의 이상 패턴을 분석하여 지도에 표시합니다</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {/* 주말 우세 정류장 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'weekend' ? null : 'weekend')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'weekend'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🏖️</span>
                      <span>주말 우세</span>
                      <span className="text-base opacity-75">
                        {weekendData?.data?.length || 0}개 정류장
                      </span>
                    </div>
                  </button>

                  {/* 심야 고수요 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'night' ? null : 'night')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'night'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🌙</span>
                      <span>심야 고수요</span>
                      <span className="text-base opacity-75">
                        {nightData?.data?.length || 0}개 정류장
                      </span>
                    </div>
                  </button>

                  {/* 저활용 정류장 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'underutilized' ? null : 'underutilized')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'underutilized'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">⚡</span>
                      <span>저활용 정류장</span>
                      <span className="text-base opacity-75">
                        {underutilizedData?.data?.length || 0}개 정류장
                      </span>
                    </div>
                  </button>

                  {/* 점심시간 특화 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'lunchtime' ? null : 'lunchtime')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'lunchtime'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🍽️</span>
                      <span>점심시간 특화</span>
                      <span className="text-base opacity-75">
                        {lunchTimeData?.data?.length || 0}개 정류장
                      </span>
                    </div>
                  </button>

                  {/* 러시아워 핫스팟 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'rushhour' ? null : 'rushhour')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'rushhour'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🚗</span>
                      <span>러시아워 핫스팟</span>
                      <span className="text-base opacity-75">
                        {((rushHourData?.data?.morning_rush?.length || 0) + (rushHourData?.data?.evening_rush?.length || 0))}개 정류장
                      </span>
                    </div>
                  </button>

                  {/* 지역 특성 분석 */}
                  <button
                    onClick={() => {
                      setSelectedPattern(selectedPattern === 'areatype' ? null : 'areatype')
                      setViewMode('station')
                    }}
                    className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                      selectedPattern === 'areatype'
                        ? "bg-blue-600 text-white shadow-md"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-lg">🏢</span>
                      <span>지역 특성</span>
                      <span className="text-base opacity-75">
                        {((areaTypeData?.data?.residential_stations?.length || 0) + (areaTypeData?.data?.business_stations?.length || 0))}개 정류장
                      </span>
                    </div>
                  </button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 교통 패턴 인사이트 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            교통 패턴 인사이트
          </CardTitle>
          <CardDescription>서울시 교통 데이터 기반 핵심 지표 분석</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* 교통 불균형 지수 */}
            <div className="p-4 bg-orange-50 rounded-lg">
              <h4 className="font-medium text-orange-800 mb-3 flex items-center gap-2">
                ⚖️ 교통 불균형 지수
              </h4>
              <div className="space-y-3">
                <div className="text-3xl font-bold text-orange-600">
                  {(() => {
                    const maxTraffic = Math.max(...filteredDistricts.map(d => d.total_traffic));
                    const minTraffic = Math.min(...filteredDistricts.map(d => d.total_traffic));
                    const avgTraffic = filteredDistricts.reduce((sum, d) => sum + d.total_traffic, 0) / filteredDistricts.length;
                    const imbalanceIndex = ((maxTraffic - minTraffic) / avgTraffic * 100).toFixed(1);
                    return `${imbalanceIndex}%`;
                  })()}
                </div>
                <div className="text-base text-gray-600">
                  <div>최대-최소 격차 대비 평균</div>
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between">
                      <span>최고 이용구:</span>
                      <span className="font-medium">{Math.max(...filteredDistricts.map(d => d.total_traffic)).toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>최저 이용구:</span>
                      <span className="font-medium">{Math.min(...filteredDistricts.map(d => d.total_traffic)).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 교통 집중도 */}
            <div className="p-4 bg-purple-50 rounded-lg">
              <h4 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                🎯 교통 집중도
              </h4>
              <div className="space-y-3">
                <div className="text-3xl font-bold text-purple-600">
                  {(() => {
                    const sortedDistricts = [...filteredDistricts].sort((a, b) => b.total_traffic - a.total_traffic);
                    const top5Traffic = sortedDistricts.slice(0, 5).reduce((sum, d) => sum + d.total_traffic, 0);
                    const totalTraffic = filteredDistricts.reduce((sum, d) => sum + d.total_traffic, 0);
                    return `${(top5Traffic / totalTraffic * 100).toFixed(1)}%`;
                  })()}
                </div>
                <div className="text-base text-gray-600">
                  <div>상위 5개구 교통량 비중</div>
                  <div className="mt-2">
                    <div className="text-base">집중 구역:</div>
                    {[...filteredDistricts]
                      .sort((a, b) => b.total_traffic - a.total_traffic)
                      .slice(0, 3)
                      .map((d, i) => (
                        <div key={d.district_name} className="text-base">
                          {i + 1}. {d.district_name}
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 정류장 효율성 */}
            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                🚏 정류장 효율성
              </h4>
              <div className="space-y-3">
                <div className="text-3xl font-bold text-blue-600">
                  {(() => {
                    const totalTraffic = filteredDistricts.reduce((sum, d) => sum + d.total_traffic, 0);
                    const totalStations = filteredDistricts.reduce((sum, d) => sum + (d.stations?.length || 0), 0);
                    return Math.round(totalTraffic / totalStations).toLocaleString();
                  })()}
                </div>
                <div className="text-base text-gray-600">
                  <div>정류장당 평균 이용객</div>
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between text-base">
                      <span>총 정류장:</span>
                      <span className="font-medium">
                        {filteredDistricts.reduce((sum, d) => sum + (d.stations?.length || 0), 0).toLocaleString()}개
                      </span>
                    </div>
                    <div className="flex justify-between text-base">
                      <span>최고 효율구:</span>
                      <span className="font-medium">
                        {(() => {
                          const efficiencies = filteredDistricts.map(d => ({
                            name: d.district_name,
                            efficiency: d.total_traffic / (d.stations?.length || 1)
                          }));
                          const best = efficiencies.sort((a, b) => b.efficiency - a.efficiency)[0];
                          return best?.name || 'N/A';
                        })()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </CardContent>
      </Card>

      {/* 구별 상세 차트 */}
      <Card>
        <CardHeader>
          <CardTitle>구별 교통량 상세 분석</CardTitle>
          <CardDescription>25개 자치구 교통량, 승하차 비율 및 정류장 효율성 비교</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={rankedDistricts.map(d => ({
              district: d.district_name,
              totalTraffic: Math.round(d.total_traffic / 1000), // 천 단위로 변환 
              rideAlightRatio: d.total_ride && d.total_alight ? (d.total_ride / d.total_alight).toFixed(2) : 0,
              avgDaily: Math.round(d.avg_daily_traffic / 1000), // 천 단위로 변환
              stationEfficiency: d.total_traffic > 0 ? Math.round((d.stations?.length || 0) / (d.total_traffic / 1000000) * 10) / 10 : 0 // 백만명당 정류장 수
            }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="district" angle={-45} textAnchor="end" height={100} />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip 
                formatter={(value: any, name: string) => [
                  name === "totalTraffic" || name === "avgDaily" ? `${value}천명` : 
                  name === "rideAlightRatio" ? `${value}` : 
                  name === "stationEfficiency" ? `${value}개/백만명` : value,
                  name === "totalTraffic" ? "총 교통량" : 
                  name === "avgDaily" ? "일평균 교통량" : 
                  name === "rideAlightRatio" ? "승하차 비율" : "정류장 효율성"
                ]}
                labelFormatter={(label) => `${label}`}
              />
              <Legend />
              <Bar yAxisId="left" dataKey="totalTraffic" fill="#3b82f6" name="총 교통량 (천명)" />
              <Bar yAxisId="right" dataKey="rideAlightRatio" fill="#10b981" name="승하차 비율" />
              <Bar yAxisId="right" dataKey="stationEfficiency" fill="#f59e0b" name="정류장 효율성 (개/백만명)" />
            </BarChart>
          </ResponsiveContainer>
          <CardDescription>
            {monthNames[Number.parseInt(selectedMonth) - 1]} 데이터 (최종 업데이트: 2024-01-30 14:30)
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  )
}
