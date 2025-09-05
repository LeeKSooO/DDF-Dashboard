"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Users, Calendar, MapPin, X, HelpCircle } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from "recharts"
import { memo, useState, useEffect } from "react"
import { apiService, TrafficResponse, utils } from "@/lib/api"
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface TrafficContentProps {
  selectedMonth: string
  selectedRegion: string
}

type TabType = 'seoul' | 'districts';

// 교통 패턴 KPI 툴팁 정보
const trafficKpiTooltips = {
  weekdayRide: "주중(월~금) 평균 승차 인원입니다. 출근시간대 패턴을 파악할 수 있는 지표로, 주거지역은 아침에 높고 업무지역은 저녁에 높게 나타납니다.",
  weekdayAlight: "주중(월~금) 평균 하차 인원입니다. 퇴근시간대 패턴을 파악할 수 있는 지표로, 업무지역은 아침에 높고 주거지역은 저녁에 높게 나타납니다.",
  weekendRide: "주말(토~일) 평균 승차 인원입니다. 여가활동 패턴을 반영하며, 일반적으로 주중보다 낮고 오후 시간대에 집중되는 특징을 보입니다.",
  weekendAlight: "주말(토~일) 평균 하차 인원입니다. 쇼핑몰, 공원, 관광지 등 여가시설 접근성을 나타내며, 주중과 다른 시간대별 분포를 보입니다.",
  weekdayMorningPeak: "주중 아침 시간대의 최대 이용량입니다. 출근 러시아워를 나타내며, 주거지역에서는 승차가, 업무지역에서는 하차가 많이 발생합니다.",
  weekdayEveningPeak: "주중 저녁 시간대의 최대 이용량입니다. 퇴근 러시아워를 나타내며, 아침과 반대로 업무지역에서는 승차가, 주거지역에서는 하차가 많이 발생합니다.",
  weekendPeak: "주말 최대 이용량입니다. 주중과 달리 오후~저녁 시간대에 피크를 보이며, 여가활동과 쇼핑 패턴을 반영합니다."
};

export const TrafficContent = memo(function TrafficContent({ selectedMonth, selectedRegion }: TrafficContentProps) {
  console.log('🚀 TrafficContent initialized with:', { selectedMonth, selectedRegion });
  
  const [activeTab, setActiveTab] = useState<TabType>('seoul');
  const [currentData, setCurrentData] = useState<TrafficResponse | null>(null);
  const [loadingCurrent, setLoadingCurrent] = useState(true);

  // 서울 전체 승차/하차 통계 계산 (총량)
  const getTrafficStats = (data: TrafficResponse | null) => {
    if (!data) return null;
    
    // 24시간 총합 계산
    const totalWeekdayRide = data.weekday_patterns.reduce((sum, pattern) => sum + pattern.avg_ride_passengers, 0);
    const totalWeekdayAlight = data.weekday_patterns.reduce((sum, pattern) => sum + pattern.avg_alight_passengers, 0);
    const totalWeekendRide = data.weekend_patterns.reduce((sum, pattern) => sum + pattern.avg_ride_passengers, 0);
    const totalWeekendAlight = data.weekend_patterns.reduce((sum, pattern) => sum + pattern.avg_alight_passengers, 0);
    
    console.log('🚌 서울 전체 통계 계산:', {
      totalWeekdayRide: totalWeekdayRide.toFixed(0),
      totalWeekdayAlight: totalWeekdayAlight.toFixed(0),
      totalWeekendRide: totalWeekendRide.toFixed(0),
      totalWeekendAlight: totalWeekendAlight.toFixed(0)
    });
    
    return {
      totalWeekdayRide: totalWeekdayRide.toFixed(2),
      totalWeekdayAlight: totalWeekdayAlight.toFixed(2),
      totalWeekendRide: totalWeekendRide.toFixed(2),
      totalWeekendAlight: totalWeekendAlight.toFixed(2)
    };
  };

  // 현재 선택된 지역 데이터 로드
  useEffect(() => {
    const loadCurrentData = async () => {
      try {
        setLoadingCurrent(true);
        let response: TrafficResponse;
        
        const analysisMonth = utils.formatSelectedMonth(selectedMonth);
        if (selectedRegion === '전체') {
          response = await apiService.getHourlyTraffic(analysisMonth, "seoul");
        } else {
          response = await apiService.getHourlyTraffic(analysisMonth, "district", selectedRegion);
        }
        
        setCurrentData(response);
        console.log('📄 현재 데이터 로드 완료:', { selectedRegion, response });
      } catch (error) {
        console.error("데이터 로드 실패:", error);
      } finally {
        setLoadingCurrent(false);
      }
    };

    loadCurrentData();
  }, [selectedRegion, selectedMonth]);

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
            전체 교통 패턴
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
      {activeTab === 'seoul' ? <CurrentTrafficView /> : <DistrictsTrafficView />}
    </div>
  )


  // 현재 선택된 지역 교통 패턴 컴포넌트
  function CurrentTrafficView() {
    if (loadingCurrent) {
      return (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    // 지역명 표시
    const regionDisplayName = selectedRegion === '전체' ? '서울시 전체' : selectedRegion;

    // 24시간 승하차 차트 데이터 준비
    const chartData = currentData?.weekday_patterns.map((weekday, index) => ({
      hour: `${index.toString().padStart(2, '0')}:00`,
      weekday_boarding: Math.round(weekday.avg_ride_passengers * 100) / 100,
      weekday_alighting: Math.round(weekday.avg_alight_passengers * 100) / 100,
      weekend_boarding: Math.round((currentData.weekend_patterns[index]?.avg_ride_passengers || 0) * 100) / 100,
      weekend_alighting: Math.round((currentData.weekend_patterns[index]?.avg_alight_passengers || 0) * 100) / 100
    })) || [];

    return (
      <div className="space-y-6">
        {/* KPI 카드들 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-gray-50">
            <CardContent className="p-6">
              <div className="flex items-center space-x-3">
                <Users className="h-7 w-7 text-blue-500" />
                <div className="flex items-center gap-2">
                  <div>
                    <span className="text-lg font-semibold text-gray-600">{regionDisplayName} 주중 승차</span>
                    <span className="text-base text-gray-500 ml-2">(정류장 평균)</span>
                  </div>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button className="text-gray-400 hover:text-gray-600 transition-colors">
                        <HelpCircle size={14} />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent 
                      side="top" 
                      className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                    >
                      {trafficKpiTooltips.weekdayRide}
                    </TooltipContent>
                  </UITooltip>
                </div>
              </div>
              <div className="text-4xl font-bold text-gray-900 mt-4">
                {getTrafficStats(currentData)?.totalWeekdayRide || '-'}
                {getTrafficStats(currentData)?.totalWeekdayRide && <span className="text-lg text-gray-600 ml-1">명</span>}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-50">
            <CardContent className="p-6">
              <div className="flex items-center space-x-3">
                <Users className="h-7 w-7 text-red-500" />
                <div className="flex items-center gap-2">
                  <div>
                    <span className="text-lg font-semibold text-gray-600">{regionDisplayName} 주중 하차</span>
                    <span className="text-base text-gray-500 ml-2">(정류장 평균)</span>
                  </div>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button className="text-gray-400 hover:text-gray-600 transition-colors">
                        <HelpCircle size={14} />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent 
                      side="top" 
                      className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                    >
                      {trafficKpiTooltips.weekdayAlight}
                    </TooltipContent>
                  </UITooltip>
                </div>
              </div>
              <div className="text-4xl font-bold text-gray-900 mt-4">
                {getTrafficStats(currentData)?.totalWeekdayAlight || '-'}
                {getTrafficStats(currentData)?.totalWeekdayAlight && <span className="text-lg text-gray-600 ml-1">명</span>}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-50">
            <CardContent className="p-6">
              <div className="flex items-center space-x-3">
                <Users className="h-7 w-7 text-green-500" />
                <div className="flex items-center gap-2">
                  <div>
                    <span className="text-lg font-semibold text-gray-600">{regionDisplayName} 주말 승차</span>
                    <span className="text-base text-gray-500 ml-2">(정류장 평균)</span>
                  </div>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button className="text-gray-400 hover:text-gray-600 transition-colors">
                        <HelpCircle size={14} />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent 
                      side="top" 
                      className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                    >
                      {trafficKpiTooltips.weekendRide}
                    </TooltipContent>
                  </UITooltip>
                </div>
              </div>
              <div className="text-4xl font-bold text-gray-900 mt-4">
                {getTrafficStats(currentData)?.totalWeekendRide || '-'}
                {getTrafficStats(currentData)?.totalWeekendRide && <span className="text-lg text-gray-600 ml-1">명</span>}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-50">
            <CardContent className="p-6">
              <div className="flex items-center space-x-3">
                <Users className="h-7 w-7 text-yellow-500" />
                <div className="flex items-center gap-2">
                  <div>
                    <span className="text-lg font-semibold text-gray-600">{regionDisplayName} 주말 하차</span>
                    <span className="text-base text-gray-500 ml-2">(정류장 평균)</span>
                  </div>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button className="text-gray-400 hover:text-gray-600 transition-colors">
                        <HelpCircle size={14} />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent 
                      side="top" 
                      className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                    >
                      {trafficKpiTooltips.weekendAlight}
                    </TooltipContent>
                  </UITooltip>
                </div>
              </div>
              <div className="text-4xl font-bold text-gray-900 mt-4">
                {getTrafficStats(currentData)?.totalWeekendAlight || '-'}
                {getTrafficStats(currentData)?.totalWeekendAlight && <span className="text-lg text-gray-600 ml-1">명</span>}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 피크 시간 정보 - 승차/하차 비율 파이차트 포함 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-gray-100">
            <CardHeader className="pb-1">
              <CardTitle className="text-2xl font-bold flex items-center gap-2">
                주중 아침 피크
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button className="text-gray-400 hover:text-gray-600 transition-colors">
                      <HelpCircle size={16} />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent 
                    side="top" 
                    className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                  >
                    {trafficKpiTooltips.weekdayMorningPeak}
                  </TooltipContent>
                </UITooltip>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-2">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="text-6xl font-bold text-blue-600 mb-4">
                    {currentData ? 
                      `${currentData.peak_hours.weekday_morning_peak.avg_total_passengers.toFixed(2)}명` :
                      '24.00명'
                    }
                  </div>
                  <Badge variant="secondary" className="text-base px-3 py-1 bg-gray-300">
                    {currentData ? `${currentData.peak_hours.weekday_morning_peak.hour}:00` : '8:00'}
                  </Badge>
                </div>
                
                {/* 승차/하차 비율 파이차트 */}
                <div className="w-48 h-48">
                  {(() => {
                    const morningPeakHour = currentData?.peak_hours.weekday_morning_peak.hour || 8;
                    const morningData = currentData?.weekday_patterns[morningPeakHour];
                    const rideValue = morningData ? morningData.avg_ride_passengers : 12;
                    const alightValue = morningData ? morningData.avg_alight_passengers : 12;
                    
                    return (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: '승차', value: rideValue, color: '#3B82F6' },
                              { name: '하차', value: alightValue, color: '#93C5FD' }
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={25}
                            outerRadius={65}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            <Cell fill="#3B82F6" />
                            <Cell fill="#93C5FD" />
                          </Pie>
                          <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)}명`, name]} />
                        </PieChart>
                      </ResponsiveContainer>
                    );
                  })()}
                </div>
              </div>
              
              {/* 승차/하차 비율 표시 */}
              <div className="flex justify-between text-base text-gray-600 mt-4">
                {(() => {
                  const morningPeakHour = currentData?.peak_hours.weekday_morning_peak.hour || 8;
                  const morningData = currentData?.weekday_patterns[morningPeakHour];
                  if (morningData) {
                    const total = morningData.avg_ride_passengers + morningData.avg_alight_passengers;
                    const ridePercent = ((morningData.avg_ride_passengers / total) * 100).toFixed(1);
                    const alightPercent = ((morningData.avg_alight_passengers / total) * 100).toFixed(1);
                    return (
                      <>
                        <span>승차 {ridePercent}%</span>
                        <span>하차 {alightPercent}%</span>
                      </>
                    );
                  }
                  return (
                    <>
                      <span>승차 50%</span>
                      <span>하차 50%</span>
                    </>
                  );
                })()}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-100">
            <CardHeader className="pb-1">
              <CardTitle className="text-2xl font-bold flex items-center gap-2">
                주중 저녁 피크
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button className="text-gray-400 hover:text-gray-600 transition-colors">
                      <HelpCircle size={16} />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent 
                    side="top" 
                    className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                  >
                    {trafficKpiTooltips.weekdayEveningPeak}
                  </TooltipContent>
                </UITooltip>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-2">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="text-6xl font-bold text-red-600 mb-4">
                    {currentData ? 
                      `${currentData.peak_hours.weekday_evening_peak.avg_total_passengers.toFixed(2)}명` :
                      '23.00명'
                    }
                  </div>
                  <Badge variant="secondary" className="text-base px-3 py-1 bg-gray-300">
                    {currentData ? `${currentData.peak_hours.weekday_evening_peak.hour}:00` : '18:00'}
                  </Badge>
                </div>
                
                {/* 승차/하차 비율 파이차트 */}
                <div className="w-48 h-48">
                  {(() => {
                    const eveningPeakHour = currentData?.peak_hours.weekday_evening_peak.hour || 18;
                    const eveningData = currentData?.weekday_patterns[eveningPeakHour];
                    const rideValue = eveningData ? eveningData.avg_ride_passengers : 11;
                    const alightValue = eveningData ? eveningData.avg_alight_passengers : 12;
                    
                    return (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: '승차', value: rideValue, color: '#DC2626' },
                              { name: '하차', value: alightValue, color: '#FCA5A5' }
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={25}
                            outerRadius={65}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            <Cell fill="#DC2626" />
                            <Cell fill="#FCA5A5" />
                          </Pie>
                          <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)}명`, name]} />
                        </PieChart>
                      </ResponsiveContainer>
                    );
                  })()}
                </div>
              </div>
              
              {/* 승차/하차 비율 표시 */}
              <div className="flex justify-between text-base text-gray-600 mt-4">
                {(() => {
                  const eveningPeakHour = currentData?.peak_hours.weekday_evening_peak.hour || 18;
                  const eveningData = currentData?.weekday_patterns[eveningPeakHour];
                  if (eveningData) {
                    const total = eveningData.avg_ride_passengers + eveningData.avg_alight_passengers;
                    const ridePercent = ((eveningData.avg_ride_passengers / total) * 100).toFixed(1);
                    const alightPercent = ((eveningData.avg_alight_passengers / total) * 100).toFixed(1);
                    return (
                      <>
                        <span>승차 {ridePercent}%</span>
                        <span>하차 {alightPercent}%</span>
                      </>
                    );
                  }
                  return (
                    <>
                      <span>승차 48%</span>
                      <span>하차 52%</span>
                    </>
                  );
                })()}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-100">
            <CardHeader className="pb-1">
              <CardTitle className="text-2xl font-bold flex items-center gap-2">
                주말 피크
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button className="text-gray-400 hover:text-gray-600 transition-colors">
                      <HelpCircle size={16} />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent 
                    side="top" 
                    className="max-w-xs bg-gray-800 text-white text-sm p-3 rounded-lg shadow-lg"
                  >
                    {trafficKpiTooltips.weekendPeak}
                  </TooltipContent>
                </UITooltip>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-2">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="text-6xl font-bold text-green-600 mb-4">
                    {currentData ? 
                      `${currentData.peak_hours.weekend_peak.avg_total_passengers.toFixed(2)}명` :
                      '13.00명'
                    }
                  </div>
                  <Badge variant="secondary" className="text-base px-3 py-1 bg-gray-300">
                    {currentData ? `${currentData.peak_hours.weekend_peak.hour}:00` : '17:00'}
                  </Badge>
                </div>
                
                {/* 승차/하차 비율 파이차트 */}
                <div className="w-48 h-48">
                  {(() => {
                    const weekendPeakHour = currentData?.peak_hours.weekend_peak.hour || 17;
                    const weekendData = currentData?.weekend_patterns[weekendPeakHour];
                    const rideValue = weekendData ? weekendData.avg_ride_passengers : 7;
                    const alightValue = weekendData ? weekendData.avg_alight_passengers : 6;
                    
                    return (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: '승차', value: rideValue, color: '#059669' },
                              { name: '하차', value: alightValue, color: '#86EFAC' }
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={25}
                            outerRadius={65}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            <Cell fill="#059669" />
                            <Cell fill="#86EFAC" />
                          </Pie>
                          <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)}명`, name]} />
                        </PieChart>
                      </ResponsiveContainer>
                    );
                  })()}
                </div>
              </div>
              
              {/* 승차/하차 비율 표시 */}
              <div className="flex justify-between text-base text-gray-600 mt-4">
                {(() => {
                  const weekendPeakHour = currentData?.peak_hours.weekend_peak.hour || 17;
                  const weekendData = currentData?.weekend_patterns[weekendPeakHour];
                  if (weekendData) {
                    const total = weekendData.avg_ride_passengers + weekendData.avg_alight_passengers;
                    const ridePercent = ((weekendData.avg_ride_passengers / total) * 100).toFixed(1);
                    const alightPercent = ((weekendData.avg_alight_passengers / total) * 100).toFixed(1);
                    return (
                      <>
                        <span>승차 {ridePercent}%</span>
                        <span>하차 {alightPercent}%</span>
                      </>
                    );
                  }
                  return (
                    <>
                      <span>승차 54%</span>
                      <span>하차 46%</span>
                    </>
                  );
                })()}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 주중/주말 분리 차트 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 주중 차트 */}
          <Card className="bg-gray-50">
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
          <Card className="bg-gray-50">
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
    // 초기 선택 대상 구 결정 (헤더 선택 반영)
    const getInitialDistricts = () => {
      if (selectedRegion && selectedRegion !== "전체") {
        return [selectedRegion];
      }
      return ['강남구', '서초구', '은평구', '광진구', '종로구'];
    };

    const [selectedDistricts, setSelectedDistricts] = useState<string[]>(getInitialDistricts);
    const [districtData, setDistrictData] = useState<Record<string, TrafficResponse>>({});
    const [loading, setLoading] = useState(false);
    const [patternType, setPatternType] = useState<'weekday' | 'weekend'>('weekday');
    const [lastSelectedRegion, setLastSelectedRegion] = useState<string | undefined>(selectedRegion);

    // 헤더 구 선택이 실제로 변경되었을 때만 비교 목록 업데이트
    useEffect(() => {
      if (lastSelectedRegion !== selectedRegion) {
        if (selectedRegion && selectedRegion !== "전체") {
          // 헤더에서 선택한 구를 기본으로 설정
          setSelectedDistricts([selectedRegion]);
        } else if (selectedRegion === "전체") {
          // 전체 선택 시 기본 구 목록으로 복원
          setSelectedDistricts(['강남구', '서초구', '은평구', '광진구', '종로구']);
        }
        setLastSelectedRegion(selectedRegion);
      }
    }, [lastSelectedRegion]);

    const loadDistrictData = async (districts: string[]) => {
      console.log('🚀 데이터 로드 시작:', districts);
      setLoading(true);
      const newData: Record<string, TrafficResponse> = {};
      
      try {
        await Promise.all(
          districts.map(async (district) => {
            console.log('📊 API 호출:', district);
            const analysisMonth = utils.formatSelectedMonth(selectedMonth);
            const data = await apiService.getHourlyTraffic(analysisMonth, "district", district);
            newData[district] = data;
            console.log('✅ API 응답 받음:', district);
          })
        );
        console.log('🎉 모든 데이터 로드 완료:', Object.keys(newData));
        setDistrictData(newData);
      } catch (error) {
        console.error('❌ 구별 데이터 로드 실패:', error);
      } finally {
        setLoading(false);
      }
    };

    // selectedDistricts 변경 시 데이터 로드 (초기 마운트 포함)
    useEffect(() => {
      if (selectedDistricts.length > 0) {
        console.log('📊 구별 데이터 로드 시작:', selectedDistricts);
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
    interface ChartDataPoint {
      hour: string;
      [district: string]: string | number;
    }
    
    const boardingChartData: ChartDataPoint[] = Array.from({ length: 24 }, (_, hour) => {
      const data: ChartDataPoint = { hour: `${hour.toString().padStart(2, '0')}:00` };
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

    const alightingChartData: ChartDataPoint[] = Array.from({ length: 24 }, (_, hour) => {
      const data: ChartDataPoint = { hour: `${hour.toString().padStart(2, '0')}:00` };
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

    // 각 구에 일관된 색상을 할당하는 함수
    const getDistrictColor = (district: string) => {
      const districtIndex = selectedDistricts.findIndex(d => d === district);
      return colors[districtIndex] || colors[0];
    };

    // 헤더 선택 구인지 확인하는 함수
    const isHeaderSelectedDistrict = (district: string) => {
      return selectedRegion !== "전체" && district === selectedRegion;
    };

    // 구별 선 굵기 결정 함수
    const getStrokeWidth = (district: string) => {
      return isHeaderSelectedDistrict(district) ? 4 : 2;
    };

    // 구별 총합 데이터 (승차/하차 분리)
    const summaryData = selectedDistricts.map((district) => {
      const data = districtData[district];
      if (!data) return { district, weekday_boarding: 0, weekday_alighting: 0, weekend_boarding: 0, weekend_alighting: 0, color: getDistrictColor(district) };
      
      const weekdayRide = data.weekday_patterns.reduce((sum, pattern) => sum + pattern.avg_ride_passengers, 0);
      const weekdayAlight = data.weekday_patterns.reduce((sum, pattern) => sum + pattern.avg_alight_passengers, 0);
      const weekendRide = data.weekend_patterns.reduce((sum, pattern) => sum + pattern.avg_ride_passengers, 0);
      const weekendAlight = data.weekend_patterns.reduce((sum, pattern) => sum + pattern.avg_alight_passengers, 0);
      
      return {
        district,
        weekday_boarding: weekdayRide.toFixed(2),
        weekday_alighting: weekdayAlight.toFixed(2),
        weekend_boarding: weekendRide.toFixed(2),
        weekend_alighting: weekendAlight.toFixed(2),
        weekday_total: data.total_weekday_passengers || 0,
        weekend_total: data.total_weekend_passengers || 0,
        color: getDistrictColor(district)
      };
    }).sort((a, b) => {
      const aValue = patternType === 'weekday' ? (a.weekday_total || 0) : (a.weekend_total || 0);
      const bValue = patternType === 'weekday' ? (b.weekday_total || 0) : (b.weekend_total || 0);
      return bValue - aValue;
    });

    return (
      <div className="space-y-6">
        {/* 구 선택 */}
        <Card className="bg-gray-50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-2xl font-bold">
              <div className="flex items-center space-x-3">
                <MapPin className="h-8 w-8" />
                <span>비교할 구 선택</span>
              </div>
              {selectedRegion && selectedRegion !== "전체" && (
                <Badge variant="default" className="text-sm bg-blue-600">
                  기본 구: {selectedRegion}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* 기본 구 (헤더 선택) */}
              {selectedRegion && selectedRegion !== "전체" && (
                <div>
                  <p className="text-sm text-gray-600 mb-2">기본 구 (헤더에서 선택됨)</p>
                  <Badge variant="default" className="px-4 py-2 text-lg bg-blue-600">
                    <div className="w-4 h-4 rounded-full mr-3" style={{ backgroundColor: getDistrictColor(selectedRegion) }}></div>
                    {selectedRegion}
                    <span className="ml-2 text-xs">기본</span>
                  </Badge>
                </div>
              )}
              
              {/* 비교 구들 */}
              <div>
                {selectedRegion && selectedRegion !== "전체" ? (
                  <p className="text-sm text-gray-600 mb-2">비교할 추가 구들</p>
                ) : (
                  <p className="text-sm text-gray-600 mb-2">비교할 구들</p>
                )}
                <div className="flex flex-wrap gap-3">
                  {selectedDistricts.map((district) => {
                    // 헤더 선택 구는 이미 위에 보여주므로 여기에서 제외
                    if (selectedRegion !== "전체" && district === selectedRegion) return null;
                    
                    return (
                      <Badge key={district} variant="secondary" className="px-4 py-2 text-lg">
                        <div className="w-4 h-4 rounded-full mr-3" style={{ backgroundColor: getDistrictColor(district) }}></div>
                        {district}
                        <button onClick={() => removeDistrict(district)} className="ml-3">
                          <X className="h-4 w-4" />
                        </button>
                      </Badge>
                    );
                  })}
                </div>
              </div>
            </div>
            
            {(() => {
              const maxDistricts = selectedRegion !== "전체" ? 5 : 5; // 전체일 때도 5개 유지
              const availableDistricts = utils.seoulDistricts.filter(d => !selectedDistricts.includes(d));
              
              return selectedDistricts.length < maxDistricts && availableDistricts.length > 0 && (
                <Select value="" onValueChange={addDistrict}>
                  <SelectTrigger className="w-64 text-lg py-3">
                    <SelectValue placeholder="구 추가하기" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableDistricts.map(district => (
                      <SelectItem key={district} value={district}>
                        {district}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              );
            })()}
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
              <h3 className="text-3xl font-bold">구별 승하차 패턴 비교</h3>
              <div className="flex items-center gap-2">
                <Button
                  variant={patternType === 'weekday' ? 'default' : 'outline'}
                  size="lg"
                  className="text-lg px-6 py-3"
                  onClick={() => setPatternType('weekday')}
                >
                  주중
                </Button>
                <Button
                  variant={patternType === 'weekend' ? 'default' : 'outline'}
                  size="lg"
                  className="text-lg px-6 py-3"
                  onClick={() => setPatternType('weekend')}
                >
                  주말
                </Button>
              </div>
            </div>

            {/* 승차/하차 분리 차트 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 승차 차트 */}
              <Card className="bg-gray-50">
                <CardHeader>
                  <CardTitle className="text-2xl font-bold">{patternType === 'weekday' ? '주중' : '주말'} 구별 승차 패턴</CardTitle>
                  <CardDescription className="text-lg">
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
                        {selectedDistricts.map((district) => (
                          <Line
                            key={district}
                            type="monotone"
                            dataKey={district}
                            stroke={getDistrictColor(district)}
                            strokeWidth={getStrokeWidth(district)}
                            dot={{ r: isHeaderSelectedDistrict(district) ? 3 : 2 }}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* 하차 차트 */}
              <Card className="bg-gray-50">
                <CardHeader>
                  <CardTitle className="text-2xl font-bold">{patternType === 'weekday' ? '주중' : '주말'} 구별 하차 패턴</CardTitle>
                  <CardDescription className="text-lg">
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
                        {selectedDistricts.map((district) => (
                          <Line
                            key={district}
                            type="monotone"
                            dataKey={district}
                            stroke={getDistrictColor(district)}
                            strokeWidth={getStrokeWidth(district)}
                            dot={{ r: isHeaderSelectedDistrict(district) ? 3 : 2 }}
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
              <Card className="bg-gray-50">
                <CardHeader>
                  <CardTitle className="text-2xl font-bold">구별 일 평균 승하차 수 ({patternType === 'weekday' ? '주중' : '주말'})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {summaryData.map((item, index) => (
                      <div key={item.district} className="p-6 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <div className={`w-4 h-4 rounded-full`} style={{ backgroundColor: item.color }}></div>
                            <span className="font-bold text-2xl">{item.district}</span>
                            <Badge variant="outline" className="text-lg px-3 py-1">#{index + 1}</Badge>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-base">
                          <div className={patternType === 'weekday' ? 'bg-blue-50 p-3 rounded' : 'p-2'}>
                            <div className={`text-gray-600 text-lg font-semibold ${patternType === 'weekday' ? 'text-blue-600 font-bold' : ''}`}>주중</div>
                            <div className="text-lg space-y-3 mt-3">
                              <div className="flex justify-between">
                                <span className="text-lg">승차:</span>
                                <span className={`font-bold text-lg ${patternType === 'weekday' ? 'text-blue-800' : ''}`}>
                                  {item.weekday_boarding}
                                  <span className="text-sm text-gray-600 ml-1">명</span>
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-lg">하차:</span>
                                <span className={`font-bold text-lg ${patternType === 'weekday' ? 'text-blue-800' : ''}`}>
                                  {item.weekday_alighting}
                                  <span className="text-sm text-gray-600 ml-1">명</span>
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className={patternType === 'weekend' ? 'bg-green-50 p-3 rounded' : 'p-2'}>
                            <div className={`text-gray-600 text-lg font-semibold ${patternType === 'weekend' ? 'text-green-600 font-bold' : ''}`}>주말</div>
                            <div className="text-lg space-y-3 mt-3">
                              <div className="flex justify-between">
                                <span className="text-lg">승차:</span>
                                <span className={`font-bold text-lg ${patternType === 'weekend' ? 'text-green-800' : ''}`}>
                                  {item.weekend_boarding}
                                  <span className="text-sm text-gray-600 ml-1">명</span>
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-lg">하차:</span>
                                <span className={`font-bold text-lg ${patternType === 'weekend' ? 'text-green-800' : ''}`}>
                                  {item.weekend_alighting}
                                  <span className="text-sm text-gray-600 ml-1">명</span>
                                </span>
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
                <Card className="bg-gray-50">
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
                <Card className="bg-gray-50">
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