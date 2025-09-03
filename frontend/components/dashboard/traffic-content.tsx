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

    // 24시간 차트 데이터 준비
    const chartData = seoulData?.weekday_patterns.map((weekday, index) => ({
      hour: `${index.toString().padStart(2, '0')}:00`,
      weekday: Math.round(weekday.avg_total_passengers * 100) / 100,
      weekend: Math.round((seoulData.weekend_patterns[index]?.avg_total_passengers || 0) * 100) / 100
    })) || [];

    return (
      <div className="space-y-6">
        {/* KPI 카드들 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-blue-500" />
                <span className="text-base font-medium text-gray-600">평일 총 승객</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekday_passengers ? seoulData.total_weekday_passengers.toLocaleString() : '259'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-green-500" />
                <span className="text-base font-medium text-gray-600">주말 총 승객</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.total_weekend_passengers ? seoulData.total_weekend_passengers.toLocaleString() : '178'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <TrendingUp className="h-5 w-5 text-purple-500" />
                <span className="text-base font-medium text-gray-600">평일/주말 비율</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData?.weekday_weekend_ratio ? seoulData.weekday_weekend_ratio.toFixed(2) : '1.45'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Clock className="h-5 w-5 text-orange-500" />
                <span className="text-base font-medium text-gray-600">평일 피크시간</span>
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {seoulData ? 
                  `${seoulData.peak_hours.weekday_morning_peak.hour}시, ${seoulData.peak_hours.weekday_evening_peak.hour}시` :
                  '8시, 18시'
                }
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 피크 시간 정보 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">평일 아침 피크</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-blue-600">
                  {seoulData ? `${seoulData.peak_hours.weekday_morning_peak.hour}:00` : '8:00'}
                </span>
                <Badge variant="secondary">
                  {seoulData ? 
                    Math.round(seoulData.peak_hours.weekday_morning_peak.avg_total_passengers) + '명' :
                    '42명'
                  }
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">평일 저녁 피크</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-red-600">
                  {seoulData ? `${seoulData.peak_hours.weekday_evening_peak.hour}:00` : '18:00'}
                </span>
                <Badge variant="secondary">
                  {seoulData ? 
                    Math.round(seoulData.peak_hours.weekday_evening_peak.avg_total_passengers) + '명' :
                    '21명'
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
                    '12명'
                  }
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 24시간 라인차트 */}
        <Card>
          <CardHeader>
            <CardTitle>24시간 승객 패턴</CardTitle>
            <CardDescription>평일/주말 시간대별 승객 변화 추이</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-96">
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
                    label={{ value: '승객 수', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip 
                    labelFormatter={(label) => `시간: ${label}`}
                    formatter={(value: number, name: string) => [
                      `${value.toFixed(1)}명`, 
                      name === 'weekday' ? '평일' : '주말'
                    ]}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="weekday" 
                    stroke="#3B82F6" 
                    strokeWidth={2}
                    name="weekday"
                    dot={{ r: 3 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="weekend" 
                    stroke="#10B981" 
                    strokeWidth={2}
                    name="weekend"
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center mt-4 space-x-6 text-base">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span>평일</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span>주말</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // 구별 비교 교통 패턴 컴포넌트  
  function DistrictsTrafficView() {
    const [selectedDistricts, setSelectedDistricts] = useState<string[]>(['강남구', '서초구']);
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

    // 차트 데이터 준비 (평일/주말에 따라 다른 데이터 사용)
    const chartData = Array.from({ length: 24 }, (_, hour) => {
      const data: any = { hour: `${hour.toString().padStart(2, '0')}:00` };
      selectedDistricts.forEach(district => {
        if (districtData[district]) {
          const patterns = patternType === 'weekday' 
            ? districtData[district].weekday_patterns 
            : districtData[district].weekend_patterns;
          data[district] = patterns[hour]?.avg_total_passengers || 0;
        }
      });
      return data;
    });

    const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

    // 구별 총합 데이터 (선택된 패턴 타입에 따라 정렬)
    const summaryData = selectedDistricts.map((district, index) => ({
      district,
      weekday: districtData[district]?.total_weekday_passengers || 0,
      weekend: districtData[district]?.total_weekend_passengers || 0,
      color: colors[index]
    })).sort((a, b) => {
      const aValue = patternType === 'weekday' ? a.weekday : a.weekend;
      const bValue = patternType === 'weekday' ? b.weekday : b.weekend;
      return bValue - aValue;
    });

    return (
      <div className="space-y-6">
        {/* 구 선택 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <MapPin className="h-5 w-5" />
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
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 24시간 비교 차트 */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>24시간 구별 승객 패턴 비교</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant={patternType === 'weekday' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setPatternType('weekday')}
                    >
                      평일
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
                <CardDescription>
                  {patternType === 'weekday' ? '평일 (월~금)' : '주말 (토~일)'} 시간대별 승객 패턴을 구별로 비교합니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="hour" tick={{ fontSize: 12 }} interval={2} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
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

            {/* 구별 총합 비교 */}
            <Card>
              <CardHeader>
                <CardTitle>구별 일 평균 총 승객 수 ({patternType === 'weekday' ? '평일' : '주말'})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {summaryData.map((item, index) => (
                    <div key={item.district} className="p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full`} style={{ backgroundColor: item.color }}></div>
                          <span className="font-medium">{item.district}</span>
                          <Badge variant="outline">#{index + 1}</Badge>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-base">
                        <div className={patternType === 'weekday' ? 'bg-blue-50 p-2 rounded' : ''}>
                          <div className={`text-gray-600 ${patternType === 'weekday' ? 'text-blue-600 font-semibold' : ''}`}>평일</div>
                          <div className={`font-bold ${patternType === 'weekday' ? 'text-blue-800 text-lg' : ''}`}>{item.weekday.toLocaleString()}</div>
                        </div>
                        <div className={patternType === 'weekend' ? 'bg-green-50 p-2 rounded' : ''}>
                          <div className={`text-gray-600 ${patternType === 'weekend' ? 'text-green-600 font-semibold' : ''}`}>주말</div>
                          <div className={`font-bold ${patternType === 'weekend' ? 'text-green-800 text-lg' : ''}`}>{item.weekend.toLocaleString()}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 평일/주말 비교 바 차트 */}
        {!loading && Object.keys(districtData).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>구별 평일/주말 승객 비교</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summaryData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="weekday" fill="#3B82F6" name="평일" />
                    <Bar dataKey="weekend" fill="#10B981" name="주말" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    )
  }
})