'use client';

import { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { RefreshCw, TrendingUp, Clock, Users } from 'lucide-react';
import { apiService, TrafficResponse, utils } from '@/lib/api';

interface TrafficChartProps {
  className?: string;
}

export function TrafficChart({ className }: TrafficChartProps) {
  const [data, setData] = useState<TrafficResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regionType, setRegionType] = useState<'seoul' | 'district'>('seoul');
  const [selectedDistrict, setSelectedDistrict] = useState<string>('');
  const [analysisMonth] = useState('2025-08-01'); // 현재 사용 가능한 데이터

  // 차트 데이터 변환
  const chartData = useMemo(() => {
    if (!data) return [];

    const result = [];
    for (let hour = 0; hour < 24; hour++) {
      const weekdayPattern = data.weekday_patterns.find(p => p.hour === hour);
      const weekendPattern = data.weekend_patterns.find(p => p.hour === hour);
      
      result.push({
        hour,
        hourFormatted: utils.formatHour(hour),
        weekday: weekdayPattern?.avg_total_passengers || 0,
        weekend: weekendPattern?.avg_total_passengers || 0,
        weekdayRide: weekdayPattern?.avg_ride_passengers || 0,
        weekdayAlight: weekdayPattern?.avg_alight_passengers || 0,
        weekendRide: weekendPattern?.avg_ride_passengers || 0,
        weekendAlight: weekendPattern?.avg_alight_passengers || 0,
      });
    }
    return result;
  }, [data]);

  // 통계 정보
  const statistics = useMemo(() => {
    if (!data) return null;

    const maxWeekday = Math.max(...chartData.map(d => d.weekday));
    const maxWeekend = Math.max(...chartData.map(d => d.weekend));
    
    return {
      maxWeekday,
      maxWeekend,
      totalWeekday: data.total_weekday_passengers,
      totalWeekend: data.total_weekend_passengers,
      ratio: data.weekday_weekend_ratio,
      peakHours: data.peak_hours
    };
  }, [data, chartData]);

  // 데이터 로드
  const loadData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.getHourlyTraffic(
        analysisMonth,
        regionType,
        regionType === 'district' ? selectedDistrict : undefined
      );
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러오는데 실패했습니다.');
      console.error('Traffic data loading error:', err);
    } finally {
      setLoading(false);
    }
  };

  // 초기 로드 및 옵션 변경시 재로드
  useEffect(() => {
    loadData();
  }, [regionType, selectedDistrict]);

  // 커스텀 툴팁
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const hour = parseInt(label);
      return (
        <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-4">
          <p className="font-semibold text-gray-800 mb-2">
            {utils.formatHour(hour)} ({hour}시)
          </p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: entry.color }}
              />
              <span className="capitalize">{entry.dataKey === 'weekday' ? '평일' : '주말'}:</span>
              <span className="font-medium">{utils.formatNumber(entry.value)}명</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            시간대별 교통 패턴
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-96">
          <div className="flex items-center gap-2 text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin" />
            데이터를 불러오는 중...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            시간대별 교통 패턴
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center h-96 gap-4">
          <div className="text-red-500 text-center">
            <p className="font-medium">데이터 로드 실패</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
          <Button onClick={loadData} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            다시 시도
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              시간대별 교통 패턴
            </CardTitle>
            <CardDescription>
              {data?.region_name} - {data?.analysis_month} 평일/주말 승하차 패턴 비교
            </CardDescription>
          </div>
          <Button onClick={loadData} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        {/* 컨트롤 섹션 */}
        <div className="flex gap-4 mt-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium">지역 구분:</label>
            <Select value={regionType} onValueChange={(value: 'seoul' | 'district') => setRegionType(value)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="seoul">서울시 전체</SelectItem>
                <SelectItem value="district">특정 구</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {regionType === 'district' && (
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">구 선택:</label>
              <Select value={selectedDistrict} onValueChange={setSelectedDistrict}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="구 선택" />
                </SelectTrigger>
                <SelectContent>
                  {utils.seoulDistricts.map(district => (
                    <SelectItem key={district} value={district}>
                      {district}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {/* 통계 카드 */}
        {statistics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {utils.formatNumber(statistics.totalWeekday)}
              </div>
              <div className="text-sm text-muted-foreground">평일 총 승객</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {utils.formatNumber(statistics.totalWeekend)}
              </div>
              <div className="text-sm text-muted-foreground">주말 총 승객</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {(statistics.ratio * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">평일/주말 비율</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {utils.formatHour(statistics.peakHours.weekday_morning_peak.hour)}
              </div>
              <div className="text-sm text-muted-foreground">평일 피크</div>
            </div>
          </div>
        )}

        <Separator className="mb-6" />

        {/* 피크 시간 정보 */}
        {statistics && (
          <div className="flex flex-wrap gap-2 mb-6">
            <Badge variant="outline" className="flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              평일 아침 피크: {utils.formatHour(statistics.peakHours.weekday_morning_peak.hour)}
            </Badge>
            <Badge variant="outline" className="flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              평일 저녁 피크: {utils.formatHour(statistics.peakHours.weekday_evening_peak.hour)}
            </Badge>
            <Badge variant="outline" className="flex items-center gap-1">
              <Users className="h-3 w-3" />
              주말 피크: {utils.formatHour(statistics.peakHours.weekend_peak.hour)}
            </Badge>
          </div>
        )}

        {/* 차트 */}
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis 
                dataKey="hour" 
                tickFormatter={utils.formatHour}
                interval="preserveStartEnd"
              />
              <YAxis 
                tickFormatter={utils.formatNumber}
                label={{ value: '승객 수 (명)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="weekday" 
                stroke="#2563eb" 
                strokeWidth={3}
                name="평일"
                dot={{ fill: '#2563eb', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line 
                type="monotone" 
                dataKey="weekend" 
                stroke="#ea580c" 
                strokeWidth={3}
                name="주말"
                dot={{ fill: '#ea580c', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 범례 */}
        <div className="flex justify-center mt-4 gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-1 bg-blue-600 rounded"></div>
            <span>평일 ({utils.formatNumber(statistics?.totalWeekday || 0)}명)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-1 bg-orange-600 rounded"></div>
            <span>주말 ({utils.formatNumber(statistics?.totalWeekend || 0)}명)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}