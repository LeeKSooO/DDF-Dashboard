"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Briefcase, Camera, Heart, Target } from "lucide-react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"
import { apiService, DRTScoreResponse, DRTStationData } from "@/lib/api"

// Extended interface for merged data
interface ExtendedDRTStationData extends DRTStationData {
  original_district?: string
}

// Month names in Korean
const monthNames = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

interface DRTScoreContentProps {
  selectedMonth: string
  selectedRegion: string
}

export function DRTScoreContent({ selectedMonth, selectedRegion }: DRTScoreContentProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // 각 모델별 실제 API 데이터
  const [vulnerableData, setVulnerableData] = useState<DRTScoreResponse | null>(null)
  const [commuterData, setCommuterData] = useState<DRTScoreResponse | null>(null)
  const [tourismData, setTourismData] = useState<DRTScoreResponse | null>(null)

  // 모든 구의 데이터를 병합하는 함수
  const mergeStationData = (results: any[], modelType: string) => {
    const allStations = results.flatMap(result => 
      result[modelType]?.stations?.map((station: any) => ({
        ...station,
        original_district: result[modelType].district_name
      })) || []
    )
    return {
      district_name: "서울시 전체 (5개구)",
      model_type: results[0]?.[modelType]?.model_type,
      analysis_month: "2025-07-01",
      stations: allStations,
      top_stations: allStations.sort((a: any, b: any) => (b.drt_score || 0) - (a.drt_score || 0)).slice(0, 10)
    }
  }

  // 전체 지역 데이터 로드
  const loadSeoulData = async () => {
    const majorDistricts = ["강남구", "서초구", "마포구", "종로구", "중구"]
    const analysisMonth = "2025-07-01"
    
    console.log('🎯 Loading data for multiple districts:', majorDistricts)
    
    const allResults = await Promise.all(
      majorDistricts.map(async (district) => {
        const [vulnerable, commuter, tourism] = await Promise.all([
          apiService.getDRTScores(district, "vulnerable", analysisMonth),
          apiService.getDRTScores(district, "commuter", analysisMonth),
          apiService.getDRTScores(district, "tourism", analysisMonth)
        ])
        return { district, vulnerable, commuter, tourism }
      })
    )

    const mergedVulnerable = mergeStationData(allResults, 'vulnerable')
    const mergedCommuter = mergeStationData(allResults, 'commuter')
    const mergedTourism = mergeStationData(allResults, 'tourism')

    console.log('🎯 Merged DRT Score Data:', {
      vulnerable: mergedVulnerable,
      commuter: mergedCommuter,
      tourism: mergedTourism
    })

    return { mergedVulnerable, mergedCommuter, mergedTourism }
  }

  // 단일 구 데이터 로드
  const loadSingleDistrictData = async (district: string) => {
    const analysisMonth = "2025-07-01"
    
    const [vulnerableResult, commuterResult, tourismResult] = await Promise.all([
      apiService.getDRTScores(district, "vulnerable", analysisMonth),
      apiService.getDRTScores(district, "commuter", analysisMonth),
      apiService.getDRTScores(district, "tourism", analysisMonth)
    ])

    console.log('🎯 Single District DRT Score API Results:', {
      vulnerable: vulnerableResult,
      commuter: commuterResult,
      tourism: tourismResult
    })

    return { vulnerableResult, commuterResult, tourismResult }
  }

  // API 데이터 로드
  useEffect(() => {
    const loadDRTScoreData = async () => {
      try {
        setLoading(true)
        setError(null)
        
        console.log('🎯 Loading DRT Score data for:', { selectedMonth, selectedRegion })

        if (selectedRegion === "전체") {
          const { mergedVulnerable, mergedCommuter, mergedTourism } = await loadSeoulData()
          setVulnerableData(mergedVulnerable)
          setCommuterData(mergedCommuter)
          setTourismData(mergedTourism)
        } else {
          const { vulnerableResult, commuterResult, tourismResult } = await loadSingleDistrictData(selectedRegion)
          setVulnerableData(vulnerableResult)
          setCommuterData(commuterResult)
          setTourismData(tourismResult)
        }

      } catch (err) {
        console.error('🚨 DRT Score API error:', err)
        setError(err instanceof Error ? err.message : 'Failed to load DRT score data')
      } finally {
        setLoading(false)
      }
    }

    loadDRTScoreData()
  }, [selectedMonth, selectedRegion])

  // 로딩 상태
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">DRT 스코어 데이터 로딩 중...</p>
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
              <p className="text-base mt-2">{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // 평균 스코어 계산
  const calculateAverageScore = (data: DRTScoreResponse | null) => {
    if (!data?.stations?.length) return 0
    const sum = data.stations.reduce((acc, station) => acc + (station.drt_score || 0), 0)
    return sum / data.stations.length
  }

  const avgVulnerableScore = calculateAverageScore(vulnerableData)
  const avgCommuterScore = calculateAverageScore(commuterData)
  const avgTourismScore = calculateAverageScore(tourismData)

  // 실제 데이터 기반 구별 순위
  const generateDistrictData = (modelData: any) => {
    if (selectedRegion === "전체") {
      // 전체 선택시 5개 구별로 데이터 생성
      const districts = ["강남구", "서초구", "마포구", "종로구", "중구"]
      return districts.map((district, index) => {
        const districtStations = modelData?.stations?.filter(
          (station: any) => station.original_district === district
        ) || []
        const avgScore = districtStations.length > 0 
          ? districtStations.reduce((sum: number, station: any) => sum + (station.drt_score || 0), 0) / districtStations.length
          : 0
        
        return {
          district,
          avgScore: parseFloat(avgScore.toFixed(1)),
          stationCount: districtStations.length,
          rank: index + 1
        }
      }).sort((a, b) => b.avgScore - a.avgScore).map((item, index) => ({ ...item, rank: index + 1 }))
    } else {
      // 단일 구 선택시
      return [{
        district: modelData?.district_name || '데이터 없음',
        avgScore: modelData?.stations?.length > 0 
          ? parseFloat((modelData.stations.reduce((sum: number, station: any) => sum + (station.drt_score || 0), 0) / modelData.stations.length).toFixed(1))
          : 0,
        stationCount: modelData?.stations?.length || 0,
        rank: 1
      }]
    }
  }

  const currentDistrictData = {
    commuter: generateDistrictData(commuterData),
    tourism: generateDistrictData(tourismData),
    vulnerable: generateDistrictData(vulnerableData)
  }

  return (
    <div className="space-y-6">
      {/* DRT 스코어 개요 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            DRT 스코어 분석 개요
          </CardTitle>
          <CardDescription>수요응답형 교통 최적화를 위한 3가지 유형별 분석</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-blue-50 rounded-lg text-center">
              <Briefcase className="h-8 w-8 text-blue-600 mx-auto mb-2" />
              <h3 className="font-medium text-blue-800">출퇴근족 DRT</h3>
              <div className="text-2xl font-bold text-blue-600 mt-2">{avgCommuterScore.toFixed(1)}점</div>
              <p className="text-base text-blue-600 mt-1">평균 스코어 ({commuterData?.stations?.length || 0}개 정류장)</p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg text-center">
              <Camera className="h-8 w-8 text-green-600 mx-auto mb-2" />
              <h3 className="font-medium text-green-800">관광객 DRT</h3>
              <div className="text-2xl font-bold text-green-600 mt-2">{avgTourismScore.toFixed(1)}점</div>
              <p className="text-base text-green-600 mt-1">평균 스코어 ({tourismData?.stations?.length || 0}개 정류장)</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg text-center">
              <Heart className="h-8 w-8 text-purple-600 mx-auto mb-2" />
              <h3 className="font-medium text-purple-800">교통약자 DRT</h3>
              <div className="text-2xl font-bold text-purple-600 mt-2">{avgVulnerableScore.toFixed(1)}점</div>
              <p className="text-base text-purple-600 mt-1">평균 스코어 ({vulnerableData?.stations?.length || 0}개 정류장)</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 탭별 상세 분석 */}
      <Tabs defaultValue="commuter" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="commuter" className="flex items-center gap-2">
            <Briefcase className="h-4 w-4" />
            출퇴근족
          </TabsTrigger>
          <TabsTrigger value="tourism" className="flex items-center gap-2">
            <Camera className="h-4 w-4" />
            관광객
          </TabsTrigger>
          <TabsTrigger value="vulnerable" className="flex items-center gap-2">
            <Heart className="h-4 w-4" />
            교통약자
          </TabsTrigger>
        </TabsList>

        {/* 출퇴근족 DRT 탭 */}
        <TabsContent value="commuter" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 상위 정류장 */}
            <Card>
              <CardHeader>
                <CardTitle>출퇴근족 DRT TOP 5 정류장</CardTitle>
                <CardDescription>출퇴근 수요가 높은 상위 5개 정류장</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {commuterData?.top_stations?.slice(0, 5).map((station, index) => (
                    <div key={station.station_id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className="font-medium">{station.station_name}</h4>
                          <p className="text-base text-muted-foreground">{(station as ExtendedDRTStationData).original_district || commuterData?.district_name}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-blue-600">{station.drt_score?.toFixed(1)}점</div>
                          <Badge variant={index === 0 ? "default" : index < 3 ? "secondary" : "outline"}>
                            {index === 0 ? "최우수" : index === 1 ? "우수" : index === 2 ? "양호" : index === 3 ? "보통" : "기타"}
                          </Badge>
                        </div>
                      </div>

                      {/* 좌표 및 피크시간 정보 */}
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>위도</span>
                            <span>{station.coordinate?.lat.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>경도</span>
                            <span>{station.coordinate?.lng.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>피크 시간</span>
                            <span>{station.peak_hour}시</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>DRT 스코어</span>
                            <span className="font-medium">{station.drt_score?.toFixed(2)}</span>
                          </div>
                          <Progress value={station.drt_score || 0} max={100} className="h-2" />
                        </div>
                      </div>

                      {/* 추천사항 (실제 데이터 기반) */}
                      <div className="p-3 bg-blue-50 rounded-lg">
                        <h5 className="font-medium text-blue-800 mb-2">💡 분석 결과</h5>
                        <ul className="text-base space-y-1">
                          <li className="flex items-start gap-2">
                            <span className="text-blue-600">•</span>
                            <span>피크 시간({station.peak_hour}시)에 높은 출퇴근 수요 예상</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-blue-600">•</span>
                            <span>DRT 스코어 {station.drt_score?.toFixed(1)}점으로 {station.drt_score && station.drt_score > 70 ? '높은' : station.drt_score > 40 ? '보통' : '낮은'} 적합도</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  )) || (
                    <div className="text-center text-gray-500 py-8">
                      <div className="text-4xl mb-3">🏢</div>
                      <div>출퇴근족 DRT 데이터를 불러오는 중...</div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 구별 순위 */}
            <Card>
              <CardHeader>
                <CardTitle>구별 출퇴근 DRT 순위</CardTitle>
                <CardDescription>자치구별 출퇴근 DRT 적합성 순위</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={selectedRegion === "전체" ? 400 : 300}>
                  <BarChart data={currentDistrictData.commuter}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="avgScore" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 space-y-2">
                  {currentDistrictData.commuter.map((district) => (
                    <div key={district.district} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center gap-3">
                        <span className="font-bold">#{district.rank}</span>
                        <span>{district.district}</span>
                        <span className="text-base text-muted-foreground">({district.stationCount}개 정류장)</span>
                      </div>
                      <span className="font-medium">{district.avgScore}점</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 관광객 DRT 탭 */}
        <TabsContent value="tourism" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 상위 정류장 */}
            <Card>
              <CardHeader>
                <CardTitle>관광객 DRT TOP 5 정류장</CardTitle>
                <CardDescription>관광 수요가 높은 상위 5개 정류장</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {tourismData?.top_stations?.slice(0, 5).map((station, index) => (
                    <div key={station.station_id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className="font-medium">{station.station_name}</h4>
                          <p className="text-base text-muted-foreground">{(station as ExtendedDRTStationData).original_district || tourismData?.district_name}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-green-600">{station.drt_score?.toFixed(1)}점</div>
                          <Badge variant={index === 0 ? "default" : index < 3 ? "secondary" : "outline"}>
                            {index === 0 ? "최우수" : index === 1 ? "우수" : index === 2 ? "양호" : index === 3 ? "보통" : "기타"}
                          </Badge>
                        </div>
                      </div>

                      {/* 좌표 및 피크시간 정보 */}
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>위도</span>
                            <span>{station.coordinate?.lat.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>경도</span>
                            <span>{station.coordinate?.lng.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>피크 시간</span>
                            <span>{station.peak_hour}시</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>DRT 스코어</span>
                            <span className="font-medium">{station.drt_score?.toFixed(2)}</span>
                          </div>
                          <Progress value={station.drt_score || 0} max={100} className="h-2" />
                        </div>
                      </div>

                      {/* 추천사항 (실제 데이터 기반) */}
                      <div className="p-3 bg-green-50 rounded-lg">
                        <h5 className="font-medium text-green-800 mb-2">💡 분석 결과</h5>
                        <ul className="text-base space-y-1">
                          <li className="flex items-start gap-2">
                            <span className="text-green-600">•</span>
                            <span>피크 시간({station.peak_hour}시)에 높은 관광 수요 예상</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-green-600">•</span>
                            <span>DRT 스코어 {station.drt_score?.toFixed(1)}점으로 {station.drt_score && station.drt_score > 70 ? '높은' : station.drt_score > 40 ? '보통' : '낮은'} 관광 적합도</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  )) || (
                    <div className="text-center text-gray-500 py-8">
                      <div className="text-4xl mb-3">📸</div>
                      <div>관광객 DRT 데이터를 불러오는 중...</div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 구별 순위 */}
            <Card>
              <CardHeader>
                <CardTitle>구별 관광 DRT 순위</CardTitle>
                <CardDescription>자치구별 관광 DRT 적합성 순위</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={selectedRegion === "전체" ? 400 : 300}>
                  <BarChart data={currentDistrictData.tourism}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="avgScore" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 space-y-2">
                  {currentDistrictData.tourism.map((district) => (
                    <div key={district.district} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center gap-3">
                        <span className="font-bold">#{district.rank}</span>
                        <span>{district.district}</span>
                        <span className="text-base text-muted-foreground">({district.stationCount}개 정류장)</span>
                      </div>
                      <span className="font-medium">{district.avgScore}점</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 교통약자 DRT 탭 */}
        <TabsContent value="vulnerable" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 상위 정류장 */}
            <Card>
              <CardHeader>
                <CardTitle>교통약자 DRT TOP 5 정류장</CardTitle>
                <CardDescription>교통약자 접근성이 높은 상위 5개 정류장</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {vulnerableData?.top_stations?.slice(0, 5).map((station, index) => (
                    <div key={station.station_id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className="font-medium">{station.station_name}</h4>
                          <p className="text-base text-muted-foreground">{(station as ExtendedDRTStationData).original_district || vulnerableData?.district_name}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-purple-600">{station.drt_score?.toFixed(1)}점</div>
                          <Badge variant={index === 0 ? "default" : index < 3 ? "secondary" : "outline"}>
                            {index === 0 ? "최우수" : index === 1 ? "우수" : index === 2 ? "양호" : index === 3 ? "보통" : "기타"}
                          </Badge>
                        </div>
                      </div>

                      {/* 좌표 및 피크시간 정보 */}
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>위도</span>
                            <span>{station.coordinate?.lat.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>경도</span>
                            <span>{station.coordinate?.lng.toFixed(4)}</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>피크 시간</span>
                            <span>{station.peak_hour}시</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-base">
                            <span>DRT 스코어</span>
                            <span className="font-medium">{station.drt_score?.toFixed(2)}</span>
                          </div>
                          <Progress value={station.drt_score || 0} max={100} className="h-2" />
                        </div>
                      </div>

                      {/* 추천사항 (실제 데이터 기반) */}
                      <div className="p-3 bg-purple-50 rounded-lg">
                        <h5 className="font-medium text-purple-800 mb-2">💡 분석 결과</h5>
                        <ul className="text-base space-y-1">
                          <li className="flex items-start gap-2">
                            <span className="text-purple-600">•</span>
                            <span>피크 시간({station.peak_hour}시)에 높은 교통약자 수요 예상</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-purple-600">•</span>
                            <span>DRT 스코어 {station.drt_score?.toFixed(1)}점으로 {station.drt_score && station.drt_score > 70 ? '높은' : station.drt_score > 40 ? '보통' : '낮은'} 접근성</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  )) || (
                    <div className="text-center text-gray-500 py-8">
                      <div className="text-4xl mb-3">💜</div>
                      <div>교통약자 DRT 데이터를 불러오는 중...</div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 구별 순위 */}
            <Card>
              <CardHeader>
                <CardTitle>구별 교통약자 DRT 순위</CardTitle>
                <CardDescription>자치구별 교통약자 DRT 적합성 순위</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={selectedRegion === "전체" ? 400 : 300}>
                  <BarChart data={currentDistrictData.vulnerable}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="avgScore" fill="#8b5cf6" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 space-y-2">
                  {currentDistrictData.vulnerable.map((district) => (
                    <div key={district.district} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center gap-3">
                        <span className="font-bold">#{district.rank}</span>
                        <span>{district.district}</span>
                        <span className="text-base text-muted-foreground">({district.stationCount}개 정류장)</span>
                      </div>
                      <span className="font-medium">{district.avgScore}점</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* 종합 분석 */}
      <Card>
        <CardHeader>
          <CardTitle>DRT 스코어 종합 분석</CardTitle>
          <CardDescription>3가지 유형별 DRT 적합성 종합 평가</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg">
              <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                <Briefcase className="h-5 w-5" />
                출퇴근족 DRT 결론
              </h4>
              <div className="text-base space-y-2">
                <div>
                  • <strong>분석 지역:</strong> {commuterData?.district_name || '데이터 로딩 중'}
                </div>
                <div>
                  • <strong>평균 스코어:</strong> {avgCommuterScore.toFixed(1)}점 ({commuterData?.stations?.length || 0}개 정류장)
                </div>
                <div>
                  • <strong>최고 점수:</strong> {commuterData?.stations?.sort((a, b) => (b.drt_score || 0) - (a.drt_score || 0))[0]?.drt_score?.toFixed(1) || '0'}점
                </div>
                <div>
                  • <strong>개선점:</strong> 실시간 수요 기반 배차 최적화
                </div>
              </div>
            </div>

            <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-lg">
              <h4 className="font-medium text-green-800 mb-3 flex items-center gap-2">
                <Camera className="h-5 w-5" />
                관광객 DRT 결론
              </h4>
              <div className="text-base space-y-2">
                <div>
                  • <strong>분석 지역:</strong> {tourismData?.district_name || '데이터 로딩 중'}
                </div>
                <div>
                  • <strong>평균 스코어:</strong> {avgTourismScore.toFixed(1)}점 ({tourismData?.stations?.length || 0}개 정류장)
                </div>
                <div>
                  • <strong>최고 점수:</strong> {tourismData?.stations?.sort((a, b) => (b.drt_score || 0) - (a.drt_score || 0))[0]?.drt_score?.toFixed(1) || '0'}점
                </div>
                <div>
                  • <strong>개선점:</strong> 관광지 연계 노선 강화 필요
                </div>
              </div>
            </div>

            <div className="p-4 bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg">
              <h4 className="font-medium text-purple-800 mb-3 flex items-center gap-2">
                <Heart className="h-5 w-5" />
                교통약자 DRT 결론
              </h4>
              <div className="text-base space-y-2">
                <div>
                  • <strong>분석 지역:</strong> {vulnerableData?.district_name || '데이터 로딩 중'}
                </div>
                <div>
                  • <strong>평균 스코어:</strong> {avgVulnerableScore.toFixed(1)}점 ({vulnerableData?.stations?.length || 0}개 정류장)
                </div>
                <div>
                  • <strong>최고 점수:</strong> {vulnerableData?.stations?.sort((a, b) => (b.drt_score || 0) - (a.drt_score || 0))[0]?.drt_score?.toFixed(1) || '0'}점
                </div>
                <div>
                  • <strong>개선점:</strong> 접근성 및 안전성 강화 필요
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 bg-yellow-50 rounded-lg">
            <h5 className="font-medium text-yellow-800 mb-3">📋 통합 정책 제언</h5>
            <div className="text-base space-y-2">
              <div>
                • <strong>지역별 특화:</strong> 각 구의 특성에 맞는 DRT 모델 적용
              </div>
              <div>
                • <strong>시간대별 운영:</strong> 수요 패턴에 따른 탄력적 운영
              </div>
              <div>
                • <strong>연계 교통:</strong> 지하철, 버스와의 환승 할인 확대
              </div>
              <div>
                • <strong>기술 도입:</strong> AI 기반 실시간 배차 시스템 구축
              </div>
              <div>
                • <strong>사회적 가치:</strong> 교통약자 우선 정책 강화
              </div>
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
