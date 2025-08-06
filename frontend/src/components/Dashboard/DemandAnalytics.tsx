import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Select, DatePicker, Spin, message } from 'antd';
import { 
  LineChart, Line, AreaChart, Area, BarChart, Bar, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts';
import { ClockCircleOutlined, EnvironmentOutlined, CarOutlined, RiseOutlined } from '@ant-design/icons';
import moment from 'moment';
import { analyticsApi, SystemKPIs, HourlyDemandPattern, RegionalAnalysis, RouteEfficiencyData } from '../../services/analyticsApi';

interface DemandAnalyticsProps {
  selectedTime: any;
  predictions: any[];
  heatmapData: any[];
}

// 로컬 인터페이스는 API 타입을 재사용

export const DemandAnalytics: React.FC<DemandAnalyticsProps> = ({
  selectedTime,
  predictions,
  heatmapData
}) => {
  const [loading, setLoading] = useState(false);
  const [hourlyData, setHourlyData] = useState<HourlyDemandPattern[]>([]);
  const [regionalData, setRegionalData] = useState<RegionalAnalysis[]>([]);
  const [routeData, setRouteData] = useState<RouteEfficiencyData[]>([]);
  const [kpiData, setKpiData] = useState<SystemKPIs>({
    totalPredictedDemand: 0,
    avgProbability: 0,
    peakHour: '',
    highDemandStops: 0,
    systemUptime: 0,
    responseTime: 0,
    activeVehicles: 0,
    totalVehicles: 0
  });

  useEffect(() => {
    if (predictions.length > 0) {
      generateAnalytics();
    }
  }, [predictions, heatmapData]);

  const generateAnalytics = async () => {
    setLoading(true);
    try {
      // 선택된 시간을 기준으로 분석 수행
      const targetDate = selectedTime.date || moment().format('YYYY-MM-DD');
      const targetDateTime = `${targetDate} ${String(selectedTime.hour || 9).padStart(2, '0')}:00:00`;
      
      // 실제 API 호출 시도, 실패하면 시뮬레이션 데이터 사용
      try {
        // 병렬로 API 호출
        const [kpis, hourlyPattern, regionalAnalysis, routeEfficiency] = await Promise.allSettled([
          analyticsApi.getSystemKPIs(targetDateTime),
          analyticsApi.getHourlyDemandPattern(targetDate),
          analyticsApi.getRegionalAnalysis({
            start: moment(targetDate).subtract(7, 'days').format('YYYY-MM-DD'),
            end: targetDate
          }),
          analyticsApi.getRouteEfficiency({
            start: moment(targetDate).subtract(7, 'days').format('YYYY-MM-DD'),
            end: targetDate
          })
        ]);

        // KPI 데이터
        if (kpis.status === 'fulfilled') {
          setKpiData(kpis.value);
        } else {
          // 시뮬레이션 KPI 데이터
          const totalDemand = predictions.reduce((sum, p) => sum + p.predicted_boarding_count, 0);
          const avgProb = predictions.reduce((sum, p) => sum + p.drt_probability, 0) / predictions.length;
          const highDemandCount = predictions.filter(p => p.drt_probability > 0.7).length;
          
          setKpiData({
            totalPredictedDemand: Math.round(totalDemand),
            avgProbability: Math.round(avgProb * 100),
            peakHour: '09:00-10:00',
            highDemandStops: highDemandCount,
            systemUptime: 99.5,
            responseTime: 156,
            activeVehicles: 3,
            totalVehicles: 4
          });
        }

        // 시간대별 수요 패턴
        if (hourlyPattern.status === 'fulfilled') {
          setHourlyData(hourlyPattern.value);
        } else {
          // 시뮬레이션 시간대별 데이터
          const simulatedHourlyData = Array.from({ length: 24 }, (_, i) => ({
            hour: i,
            demand: Math.round(50 + 30 * Math.sin((i - 8) * Math.PI / 12) + Math.random() * 20),
            prediction: Math.round(45 + 25 * Math.sin((i - 8) * Math.PI / 12) + Math.random() * 15),
            confidence: Math.round(70 + Math.random() * 25)
          }));
          setHourlyData(simulatedHourlyData);
        }

        // 지역별 분석
        if (regionalAnalysis.status === 'fulfilled') {
          setRegionalData(regionalAnalysis.value);
        } else {
          // 시뮬레이션 지역별 데이터
          const regions = ['가평읍', '청평면', '상면', '북면', '조종면'];
          const simulatedRegionalData = regions.map(region => ({
            region,
            totalDemand: Math.round(100 + Math.random() * 200),
            avgProbability: Math.round(40 + Math.random() * 40),
            stopCount: Math.round(150 + Math.random() * 100),
            peakHours: [8, 9, 17, 18]
          }));
          setRegionalData(simulatedRegionalData);
        }

        // 노선별 효율성
        if (routeEfficiency.status === 'fulfilled') {
          setRouteData(routeEfficiency.value);
        } else {
          // 시뮬레이션 노선 데이터
          const simulatedRouteData = [
            { 
              routeId: 'GGB239000005', routeName: '40-5', demandDensity: 85, coverage: 92, 
              efficiency: 78, avgWaitTime: 8.5, onTimePerformance: 94 
            },
            { 
              routeId: 'GGB239000006', routeName: '43', demandDensity: 76, coverage: 88, 
              efficiency: 82, avgWaitTime: 12.3, onTimePerformance: 89 
            },
            { 
              routeId: 'GGB239000024', routeName: '1330-44', demandDensity: 94, coverage: 95, 
              efficiency: 89, avgWaitTime: 6.8, onTimePerformance: 96 
            },
            { 
              routeId: 'GGB239000139', routeName: '7000', demandDensity: 91, coverage: 87, 
              efficiency: 85, avgWaitTime: 7.2, onTimePerformance: 92 
            },
            { 
              routeId: 'GGB239000032', routeName: '10-4', demandDensity: 68, coverage: 75, 
              efficiency: 71, avgWaitTime: 15.1, onTimePerformance: 87 
            }
          ];
          setRouteData(simulatedRouteData);
        }

      } catch (apiError) {
        console.warn('Analytics API 호출 실패, 시뮬레이션 데이터 사용:', apiError);
        message.warning('분석 API에 연결할 수 없어 시뮬레이션 데이터를 표시합니다.');
        
        // 전체 시뮬레이션 데이터로 fallback
        generateSimulationData();
      }

    } catch (error) {
      console.error('Analytics 생성 중 오류:', error);
      message.error('분석 데이터 생성 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const generateSimulationData = () => {
    // 기존 시뮬레이션 로직을 별도 함수로 분리
    const totalDemand = predictions.reduce((sum, p) => sum + p.predicted_boarding_count, 0);
    const avgProb = predictions.reduce((sum, p) => sum + p.drt_probability, 0) / predictions.length;
    const highDemandCount = predictions.filter(p => p.drt_probability > 0.7).length;
    
    setKpiData({
      totalPredictedDemand: Math.round(totalDemand),
      avgProbability: Math.round(avgProb * 100),
      peakHour: '09:00-10:00',
      highDemandStops: highDemandCount,
      systemUptime: 99.5,
      responseTime: 156,
      activeVehicles: 3,
      totalVehicles: 4
    });

    const hourlyPattern = Array.from({ length: 24 }, (_, i) => ({
      hour: i,
      demand: Math.round(50 + 30 * Math.sin((i - 8) * Math.PI / 12) + Math.random() * 20),
      prediction: Math.round(45 + 25 * Math.sin((i - 8) * Math.PI / 12) + Math.random() * 15),
      confidence: Math.round(70 + Math.random() * 25)
    }));
    setHourlyData(hourlyPattern);

    const regions = ['가평읍', '청평면', '상면', '북면', '조종면'];
    const regionalAnalysis = regions.map(region => ({
      region,
      totalDemand: Math.round(100 + Math.random() * 200),
      avgProbability: Math.round(40 + Math.random() * 40),
      stopCount: Math.round(150 + Math.random() * 100),
      peakHours: [8, 9, 17, 18]
    }));
    setRegionalData(regionalAnalysis);

    const routeAnalysis = [
      { 
        routeId: 'GGB239000005', routeName: '40-5', demandDensity: 85, coverage: 92, 
        efficiency: 78, avgWaitTime: 8.5, onTimePerformance: 94 
      },
      { 
        routeId: 'GGB239000006', routeName: '43', demandDensity: 76, coverage: 88, 
        efficiency: 82, avgWaitTime: 12.3, onTimePerformance: 89 
      },
      { 
        routeId: 'GGB239000024', routeName: '1330-44', demandDensity: 94, coverage: 95, 
        efficiency: 89, avgWaitTime: 6.8, onTimePerformance: 96 
      },
      { 
        routeId: 'GGB239000139', routeName: '7000', demandDensity: 91, coverage: 87, 
        efficiency: 85, avgWaitTime: 7.2, onTimePerformance: 92 
      },
      { 
        routeId: 'GGB239000032', routeName: '10-4', demandDensity: 68, coverage: 75, 
        efficiency: 71, avgWaitTime: 15.1, onTimePerformance: 87 
      }
    ];
    setRouteData(routeAnalysis);
  };

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
        <div style={{ marginTop: '16px' }}>수요 분석 데이터를 생성하고 있습니다...</div>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px' }}>
      {/* KPI 카드 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="예상 총 수요"
              value={kpiData.totalPredictedDemand}
              suffix="명"
              prefix={<CarOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="평균 DRT 확률"
              value={kpiData.avgProbability}
              suffix="%"
              prefix={<RiseOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="예상 피크 시간"
              value={kpiData.peakHour}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="고수요 정류장"
              value={kpiData.highDemandStops}
              suffix="개"
              prefix={<EnvironmentOutlined />}
              valueStyle={{ color: '#eb2f96' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 시간대별 수요 패턴 */}
        <Col span={12}>
          <Card title="시간대별 수요 패턴" size="small">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="demand" 
                  stroke="#1890ff" 
                  strokeWidth={2}
                  name="실제 수요"
                />
                <Line 
                  type="monotone" 
                  dataKey="prediction" 
                  stroke="#52c41a" 
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  name="예측 수요"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* 지역별 수요 분포 */}
        <Col span={12}>
          <Card title="지역별 수요 분포" size="small">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={regionalData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="region" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="totalDemand" fill="#1890ff" name="총 수요" />
                <Bar dataKey="avgProbability" fill="#52c41a" name="평균 확률(%)" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 노선별 효율성 */}
        <Col span={12}>
          <Card title="주요 노선 효율성 분석" size="small">
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={routeData.slice(0, 5)}>
                <PolarGrid />
                <PolarAngleAxis dataKey="routeName" />
                <PolarRadiusAxis angle={30} domain={[0, 100]} />
                <Radar
                  name="수요 밀도"
                  dataKey="demandDensity"
                  stroke="#1890ff"
                  fill="#1890ff"
                  fillOpacity={0.6}
                />
                <Radar
                  name="커버리지"
                  dataKey="coverage"
                  stroke="#52c41a"
                  fill="#52c41a"
                  fillOpacity={0.6}
                />
                <Radar
                  name="효율성"
                  dataKey="efficiency"
                  stroke="#fa8c16"
                  fill="#fa8c16"
                  fillOpacity={0.6}
                />
                <Tooltip />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* 수요 분포 파이차트 */}
        <Col span={12}>
          <Card title="수요 확률 분포" size="small">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={[
                    { name: '매우 높음 (80%+)', value: 12, color: '#ff4d4f' },
                    { name: '높음 (60-80%)', value: 28, color: '#fa8c16' },
                    { name: '보통 (40-60%)', value: 35, color: '#fadb14' },
                    { name: '낮음 (20-40%)', value: 20, color: '#52c41a' },
                    { name: '매우 낮음 (0-20%)', value: 5, color: '#1890ff' }
                  ]}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {regionalData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* 추세 분석 */}
      <Row gutter={16}>
        <Col span={24}>
          <Card title="일주일 수요 추세" size="small">
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart
                data={[
                  { day: '월', demand: 450, prediction: 420 },
                  { day: '화', demand: 380, prediction: 390 },
                  { day: '수', demand: 420, prediction: 410 },
                  { day: '목', demand: 460, prediction: 445 },
                  { day: '금', demand: 520, prediction: 500 },
                  { day: '토', demand: 680, prediction: 650 },
                  { day: '일', demand: 720, prediction: 690 }
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="prediction"
                  stackId="1"
                  stroke="#52c41a"
                  fill="#52c41a"
                  fillOpacity={0.6}
                  name="예측 수요"
                />
                <Area
                  type="monotone"
                  dataKey="demand"
                  stackId="2"
                  stroke="#1890ff"
                  fill="#1890ff"
                  fillOpacity={0.8}
                  name="실제 수요"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>
    </div>
  );
};