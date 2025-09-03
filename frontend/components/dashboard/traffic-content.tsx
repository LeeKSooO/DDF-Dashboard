"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Map, Clock, Users, TrendingUp, Calendar, MapPin, X } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts"
import { memo, useState, useEffect } from "react"
import { apiService, TrafficResponse, utils } from "@/lib/api"

interface TrafficContentProps {
  selectedMonth: string
  selectedRegion: string
}

type TabType = 'seoul' | 'districts';

export const TrafficContent = memo(function TrafficContent({ selectedMonth, selectedRegion }: TrafficContentProps) {
  console.log('🚀 TrafficContent initialized with:', { selectedMonth, selectedRegion });
  
  const [activeTab, setActiveTab] = useState<TabType>('seoul');
  const [seoulData, setSeoulData] = useState<TrafficResponse | null>(null);
  const [loadingSeoul, setLoadingSeoul] = useState(true);

  // 서울 전체 데이터 로드
  useEffect(() => {
    const loadSeoulData = async () => {
      try {
        setLoadingSeoul(true);
        const response = await apiService.getHourlyTraffic("2025-07-01", "seoul");
        setSeoulData(response);
      } catch (error) {
        console.error("서울 데이터 로드 실패:", error);
      } finally {
        setLoadingSeoul(false);
      }
    };

    loadSeoulData();
  }, []);

  return (
    <div className="space-y-6">
      {/* 탭 네비게이션 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">교통 패턴 분석</h1>
          <p className="text-gray-600 mt-1">서울시 교통 흐름을 다각도로 분석합니다</p>
        </div>
        <div className="flex items-center space-x-2">
          <Calendar className="h-4 w-4 text-gray-500" />
          <span className="text-base text-gray-600">{selectedMonth}</span>
        </div>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('seoul')}
            className={`py-2 px-1 border-b-2 font-medium text-base ${
              activeTab === 'seoul'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            서울 전체 교통 패턴
          </button>
          <button
            onClick={() => setActiveTab('districts')}
            className={`py-2 px-1 border-b-2 font-medium text-base ${
              activeTab === 'districts'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            구별 비교 교통 패턴
          </button>
        </nav>
      </div>

      {/* 탭 컨텐츠 */}
      {activeTab === 'seoul' ? <SeoulTrafficView /> : <DistrictsTrafficView />}
    </div>
  )

  // 서울 전체 교통 패턴 컴포넌트
  function SeoulTrafficView() {
    if (loadingSeoul) {
      return (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    // 24시간 승하차 차트 데이터 준비
    const chartData = seoulData?.weekday_patterns.map((weekday, index) => ({
      hour: `${index.toString().padStart(2, '0')}:00`,
      weekday_boarding: Math.round(weekday.avg_ride_passengers * 100) / 100,
      weekday_alighting: Math.round(weekday.avg_alight_passengers * 100) / 100,
      weekend_boarding: Math.round((seoulData.weekend_patterns[index]?.avg_ride_passengers || 0) * 100) / 100,
      weekend_alighting: Math.round((seoulData.weekend_patterns[index]?.avg_alight_passengers || 0) * 100) / 100
    })) || [];

    return (
      <div className="space-y-6">
        {/* KPI 카드들 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-blue-500" />
                <span className="text-base font-medium text-gray-600">주중 평균 승차</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekday_passengers ? Math.round(seoulData.total_weekday_passengers / 2).toLocaleString() : '129'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-red-500" />
                <span className="text-base font-medium text-gray-600">주중 평균 하차</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekday_passengers ? Math.round(seoulData.total_weekday_passengers / 2).toLocaleString() : '129'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-green-500" />
                <span className="text-base font-medium text-gray-600">주말 평균 승차</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekend_passengers ? Math.round(seoulData.total_weekend_passengers / 2).toLocaleString() : '89'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-yellow-500" />
                <span className="text-base font-medium text-gray-600">주말 평균 하차</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekend_passengers ? Math.round(seoulData.total_weekend_passengers / 2).toLocaleString() : '89'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 피크 시간 정보 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">주중 아침 피크</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-blue-600">
                  {seoulData ? `${seoulData.peak_hours.weekday_morning_peak.hour}:00` : '8:00'}
                </span>
                <Badge variant="secondary">
                  {seoulData ? 
                    Math.round(seoulData.peak_hours.weekday_morning_peak.avg_total_passengers) + '명' :
                    '24명'
                  }
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">주중 저녁 피크</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-red-600">
                  {seoulData ? `${seoulData.peak_hours.weekday_evening_peak.hour}:00` : '18:00'}
                </span>
                <Badge variant="secondary">
                  {seoulData ? 
                    Math.round(seoulData.peak_hours.weekday_evening_peak.avg_total_passengers) + '명' :
                    '23명'
                  }
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">주말 피크</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-green-600">
                  {seoulData ? `${seoulData.peak_hours.weekend_peak.hour}:00` : '17:00'}
                </span>
                <Badge variant="secondary">
                  {seoulData ? 
                    Math.round(seoulData.peak_hours.weekend_peak.avg_total_passengers) + '명' :
                    '13명'
                  }
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 주중/주말 분리 차트 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 주중 차트 */}
          <Card>
            <CardHeader>
              <CardTitle>주중 승하차 패턴 (월~금)</CardTitle>
              <CardDescription>주중 24시간 승차/하차 변화 추이</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="hour" 
                      tick={{ fontSize: 12 }}
                      interval={2}
                    />
                    <YAxis 
                      tick={{ fontSize: 12 }}
                      label={{ value: '인원 수', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip 
                      labelFormatter={(label) => `시간: ${label}`}
                      formatter={(value: number, name: string) => [
                        `${value.toFixed(1)}명`, 
                        name === 'weekday_boarding' ? '승차' : '하차'
                      ]}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="weekday_boarding" 
                      stroke="#3B82F6" 
                      strokeWidth={2}
                      name="weekday_boarding"
                      dot={{ r: 3 }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="weekday_alighting" 
                      stroke="#EF4444" 
                      strokeWidth={2}
                      name="weekday_alighting"
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center justify-center mt-4 space-x-6 text-base">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                  <span>승차</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                  <span>하차</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 주말 차트 */}
          <Card>
            <CardHeader>
              <CardTitle>주말 승하차 패턴 (토~일)</CardTitle>
              <CardDescription>주말 24시간 승차/하차 변화 추이</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="hour" 
                      tick={{ fontSize: 12 }}
                      interval={2}
                    />
                    <YAxis 
                      tick={{ fontSize: 12 }}
                      label={{ value: '인원 수', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip 
                      labelFormatter={(label) => `시간: ${label}`}
                      formatter={(value: number, name: string) => [
                        `${value.toFixed(1)}명`, 
                        name === 'weekend_boarding' ? '승차' : '하차'
                      ]}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="weekend_boarding" 
                      stroke="#10B981" 
                      strokeWidth={2}
                      name="weekend_boarding"
                      dot={{ r: 3 }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="weekend_alighting" 
                      stroke="#F59E0B" 
                      strokeWidth={2}
                      name="weekend_alighting"
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center justify-center mt-4 space-x-6 text-base">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span>승차</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <span>하차</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  // 구별 비교 교통 패턴 컴포넌트  
  function DistrictsTrafficView() {
    const [selectedDistricts, setSelectedDistricts] = useState<string[]>(['강남구', '서초구', '은평구', '광진구', '종로구']);
    const [districtData, setDistrictData] = useState<Record<string, TrafficResponse>>({});
    const [loading, setLoading] = useState(false);
    const [patternType, setPatternType] = useState<'weekday' | 'weekend'>('weekday');

    const loadDistrictData = async (districts: string[]) => {
      setLoading(true);
      const newData: Record<string, TrafficResponse> = {};
      
      try {
        await Promise.all(
          districts.map(async (district) => {
            const data = await apiService.getHourlyTraffic("2025-07-01", "district", district);
            newData[district] = data;
          })
        );
        setDistrictData(newData);
      } catch (error) {
        console.error('구별 데이터 로드 실패:', error);
      } finally {
        setLoading(false);
      }
    };

    useEffect(() => {
      if (selectedDistricts.length > 0) {
        loadDistrictData(selectedDistricts);
      }
    }, [selectedDistricts]);

    const addDistrict = (district: string) => {
      if (!selectedDistricts.includes(district) && selectedDistricts.length < 5) {
        setSelectedDistricts([...selectedDistricts, district]);
      }
    };

    const removeDistrict = (district: string) => {
      setSelectedDistricts(selectedDistricts.filter(d => d !== district));
    };

    // 차트 데이터 준비 (승차/하차 분리)
    const boardingChartData = Array.from({ length: 24 }, (_, hour) => {
      const data: any = { hour: `${hour.toString().padStart(2, '0')}:00` };
      selectedDistricts.forEach(district => {
        if (districtData[district]) {
          const patterns = patternType === 'weekday' 
            ? districtData[district].weekday_patterns 
            : districtData[district].weekend_patterns;
          data[district] = patterns[hour]?.avg_ride_passengers || 0;
        }
      });
      return data;
    });

    const alightingChartData = Array.from({ length: 24 }, (_, hour) => {
      const data: any = { hour: `${hour.toString().padStart(2, '0')}:00` };
      selectedDistricts.forEach(district => {
        if (districtData[district]) {
          const patterns = patternType === 'weekday' 
            ? districtData[district].weekday_patterns 
            : districtData[district].weekend_patterns;
          data[district] = patterns[hour]?.avg_alight_passengers || 0;
        }
      });
      return data;
    });

    const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

    // 구별 총합 데이터 (승차/하차 분리)
    const summaryData = selectedDistricts.map((district, index) => ({
      district,
      weekday_boarding: Math.round((districtData[district]?.total_weekday_passengers || 0) / 2),
      weekday_alighting: Math.round((districtData[district]?.total_weekday_passengers || 0) / 2),
      weekend_boarding: Math.round((districtData[district]?.total_weekend_passengers || 0) / 2),
      weekend_alighting: Math.round((districtData[district]?.total_weekend_passengers || 0) / 2),
      weekday_total: districtData[district]?.total_weekday_passengers || 0,
      weekend_total: districtData[district]?.total_weekend_passengers || 0,
      color: colors[index]
    })).sort((a, b) => {
      const aValue = patternType === 'weekday' ? a.weekday_total : a.weekend_total;
      const bValue = patternType === 'weekday' ? b.weekday_total : b.weekend_total;
      return bValue - aValue;
    });

    return (
      <div className="space-y-6">
        {/* 구 선택 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg">
              <MapPin className="h-6 w-6" />
              <span>비교할 구 선택</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 mb-4">
              {selectedDistricts.map((district, index) => (
                <Badge key={district} variant="secondary" className="px-3 py-1">
                  <div className={`w-3 h-3 rounded-full mr-2`} style={{ backgroundColor: colors[index] }}></div>
                  {district}
                  <button onClick={() => removeDistrict(district)} className="ml-2">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            
            {selectedDistricts.length < 5 && (
              <Select onValueChange={addDistrict}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="구 추가하기" />
                </SelectTrigger>
                <SelectContent>
                  {utils.seoulDistricts.filter(d => !selectedDistricts.includes(d)).map(district => (
                    <SelectItem key={district} value={district}>
                      {district}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </CardContent>
        </Card>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* 주중/주말 토글 버튼 */}
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold">구별 승하차 패턴 비교</h3>
              <div className="flex items-center gap-2">
                <Button
                  variant={patternType === 'weekday' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setPatternType('weekday')}
                >
                  주중
                </Button>
                <Button
                  variant={patternType === 'weekend' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setPatternType('weekend')}
                >
                  주말
                </Button>
              </div>
            </div>

            {/* 승차/하차 분리 차트 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 승차 차트 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{patternType === 'weekday' ? '주중' : '주말'} 구별 승차 패턴</CardTitle>
                  <CardDescription className="text-base">
                    {patternType === 'weekday' ? '주중 (월~금)' : '주말 (토~일)'} 24시간 승차 패턴 비교
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={boardingChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hour" tick={{ fontSize: 13 }} interval={2} />
                        <YAxis tick={{ fontSize: 13 }} label={{ value: '승차 수', angle: -90, position: 'insideLeft' }} />
                        <Tooltip 
                          labelFormatter={(label) => `시간: ${label}`}
                          formatter={(value: number, name: string) => [
                            `${value.toFixed(1)}명`, 
                            name
                          ]}
                        />
                        {selectedDistricts.map((district, index) => (
                          <Line
                            key={district}
                            type="monotone"
                            dataKey={district}
                            stroke={colors[index]}
                            strokeWidth={2}
                            dot={{ r: 2 }}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* 하차 차트 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{patternType === 'weekday' ? '주중' : '주말'} 구별 하차 패턴</CardTitle>
                  <CardDescription className="text-base">
                    {patternType === 'weekday' ? '주중 (월~금)' : '주말 (토~일)'} 24시간 하차 패턴 비교
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={alightingChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hour" tick={{ fontSize: 13 }} interval={2} />
                        <YAxis tick={{ fontSize: 13 }} label={{ value: '하차 수', angle: -90, position: 'insideLeft' }} />
                        <Tooltip 
                          labelFormatter={(label) => `시간: ${label}`}
                          formatter={(value: number, name: string) => [
                            `${value.toFixed(1)}명`, 
                            name
                          ]}
                        />
                        {selectedDistricts.map((district, index) => (
                          <Line
                            key={district}
                            type="monotone"
                            dataKey={district}
                            stroke={colors[index]}
                            strokeWidth={2}
                            dot={{ r: 2 }}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* 구별 총합 비교 및 바 차트 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 좌측: 구별 총합 비교 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">구별 일 평균 승하차 수 ({patternType === 'weekday' ? '주중' : '주말'})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {summaryData.map((item, index) => (
                      <div key={item.district} className="p-4 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <div className={`w-4 h-4 rounded-full`} style={{ backgroundColor: item.color }}></div>
                            <span className="font-semibold text-lg">{item.district}</span>
                            <Badge variant="outline" className="text-sm">#{index + 1}</Badge>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-base">
                          <div className={patternType === 'weekday' ? 'bg-blue-50 p-3 rounded' : 'p-2'}>
                            <div className={`text-gray-600 text-base font-medium ${patternType === 'weekday' ? 'text-blue-600 font-semibold' : ''}`}>주중</div>
                            <div className="text-base space-y-2 mt-2">
                              <div className="flex justify-between">
                                <span className="text-base">승차:</span>
                                <span className={`font-bold text-base ${patternType === 'weekday' ? 'text-blue-800' : ''}`}>{item.weekday_boarding.toLocaleString()}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-base">하차:</span>
                                <span className={`font-bold text-base ${patternType === 'weekday' ? 'text-blue-800' : ''}`}>{item.weekday_alighting.toLocaleString()}</span>
                              </div>
                            </div>
                          </div>
                          <div className={patternType === 'weekend' ? 'bg-green-50 p-3 rounded' : 'p-2'}>
                            <div className={`text-gray-600 text-base font-medium ${patternType === 'weekend' ? 'text-green-600 font-semibold' : ''}`}>주말</div>
                            <div className="text-base space-y-2 mt-2">
                              <div className="flex justify-between">
                                <span className="text-base">승차:</span>
                                <span className={`font-bold text-base ${patternType === 'weekend' ? 'text-green-800' : ''}`}>{item.weekend_boarding.toLocaleString()}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-base">하차:</span>
                                <span className={`font-bold text-base ${patternType === 'weekend' ? 'text-green-800' : ''}`}>{item.weekend_alighting.toLocaleString()}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* 우측: 바 차트 2개 */}
              <div className="lg:col-span-2 space-y-6">
                {/* 주중 승하차 바 차트 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">구별 주중 승하차 비교</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={summaryData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="district" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 13 }} />
                          <Tooltip 
                            formatter={(value: number, name: string) => [
                              `${value.toLocaleString()}명`, 
                              name === 'weekday_boarding' ? '승차' : '하차'
                            ]}
                          />
                          <Bar dataKey="weekday_boarding" fill="#3B82F6" name="weekday_boarding" />
                          <Bar dataKey="weekday_alighting" fill="#EF4444" name="weekday_alighting" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex items-center justify-center mt-3 space-x-8 text-base">
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 bg-blue-500 rounded-full"></div>
                        <span className="font-medium">승차</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 bg-red-500 rounded-full"></div>
                        <span className="font-medium">하차</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 주말 승하차 바 차트 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">구별 주말 승하차 비교</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={summaryData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="district" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 13 }} />
                          <Tooltip 
                            formatter={(value: number, name: string) => [
                              `${value.toLocaleString()}명`, 
                              name === 'weekend_boarding' ? '승차' : '하차'
                            ]}
                          />
                          <Bar dataKey="weekend_boarding" fill="#10B981" name="weekend_boarding" />
                          <Bar dataKey="weekend_alighting" fill="#F59E0B" name="weekend_alighting" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex items-center justify-center mt-3 space-x-8 text-base">
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 bg-green-500 rounded-full"></div>
                        <span className="font-medium">승차</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 bg-yellow-500 rounded-full"></div>
                        <span className="font-medium">하차</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        )}

      </div>
    )
  }
})