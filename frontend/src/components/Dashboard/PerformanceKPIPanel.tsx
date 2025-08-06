import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Progress, Statistic, Spin } from 'antd';
import { 
  DashboardOutlined, 
  DollarOutlined, 
  UserOutlined, 
  CarOutlined,
  EnvironmentOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { drtAnalyticsApi } from '../../services/api';
import { DRTPerformanceKPIs } from '../../types/drtMetrics';

export const PerformanceKPIPanel: React.FC = () => {
  const [kpiData, setKpiData] = useState<DRTPerformanceKPIs | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadPerformanceKPIs();
  }, []);

  const loadPerformanceKPIs = async () => {
    setLoading(true);
    
    try {
      const data = await drtAnalyticsApi.getPerformanceKPIs();
      setKpiData(data);
    } catch (error) {
      console.error('성과 지표 데이터 로딩 실패:', error);
      setKpiData(null);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
        <div style={{ marginTop: '12px' }}>성과 지표 로딩 중...</div>
      </div>
    );
  }

  if (!kpiData) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <div>성과 지표 데이터를 불러올 수 없습니다.</div>
      </div>
    );
  }

  const pieData = [
    { name: '수익', value: kpiData.financial_performance.cost_recovery_ratio, color: '#52c41a' },
    { name: '보조금', value: 100 - kpiData.financial_performance.cost_recovery_ratio, color: '#fa8c16' }
  ];

  const trendData = [
    { month: '1월', efficiency: 65, satisfaction: 70, cost_recovery: 68 },
    { month: '2월', efficiency: 72, satisfaction: 75, cost_recovery: 71 },
    { month: '3월', efficiency: 76, satisfaction: 78, cost_recovery: 78 },
    { month: '4월', efficiency: 78, satisfaction: 82, cost_recovery: 78 },
  ];

  return (
    <div>
      {/* 서비스 커버리지 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={24}>
          <Card title="서비스 접근성" size="small">
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="서비스 면적"
                  value={kpiData.service_coverage.total_service_area}
                  suffix="km²"
                  prefix={<EnvironmentOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="커버 인구"
                  value={kpiData.service_coverage.population_covered}
                  suffix="명"
                  prefix={<UserOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="서비스 정류장"
                  value={kpiData.service_coverage.stops_served}
                  suffix="개"
                  prefix={<EnvironmentOutlined />}
                />
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>커버리지 개선</div>
                  <Progress
                    type="circle"
                    percent={kpiData.service_coverage.coverage_improvement}
                    size={80}
                    strokeColor="#52c41a"
                  />
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 운영 효율성 */}
        <Col span={12}>
          <Card title="운영 효율성" size="small">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="차량 가동률"
                  value={kpiData.operational_efficiency.vehicle_utilization}
                  suffix="%"
                  prefix={<CarOutlined />}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="평균 탑승률"
                  value={kpiData.operational_efficiency.average_occupancy}
                  suffix="명/대"
                  prefix={<UserOutlined />}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="정시 운행률"
                  value={kpiData.operational_efficiency.on_time_performance}
                  suffix="%"
                  prefix={<ClockCircleOutlined />}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="서비스 신뢰도"
                  value={kpiData.operational_efficiency.service_reliability}
                  suffix="%"
                  prefix={<DashboardOutlined />}
                />
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 재정 성과 */}
        <Col span={12}>
          <Card title="재정 성과" size="small">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="일일 수입"
                  value={kpiData.financial_performance.daily_revenue}
                  suffix="원"
                  prefix={<DollarOutlined />}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="운영 비용"
                  value={kpiData.financial_performance.daily_operating_cost}
                  suffix="원"
                  prefix={<DollarOutlined />}
                />
              </Col>
              <Col span={12}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', color: '#666' }}>비용 회수율</div>
                  <ResponsiveContainer width="100%" height={100}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={20}
                        outerRadius={40}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </Col>
              <Col span={12}>
                <Statistic
                  title="승객당 보조금"
                  value={kpiData.financial_performance.subsidy_per_passenger}
                  suffix="원"
                  prefix={<DollarOutlined />}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 사회적 영향 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={14}>
          <Card title="사회적 영향" size="small">
            <Row gutter={16}>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>고령자 이동성 개선</div>
                  <Progress
                    type="circle"
                    percent={kpiData.social_impact.elderly_mobility_improvement}
                    size={80}
                    strokeColor="#1890ff"
                  />
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>의료시설 접근성</div>
                  <Progress
                    type="circle"
                    percent={kpiData.social_impact.medical_facility_accessibility}
                    size={80}
                    strokeColor="#52c41a"
                  />
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', color: '#666', marginBottom: '8px' }}>자가용 이용 감소</div>
                  <Progress
                    type="circle"
                    percent={kpiData.social_impact.reduced_private_car_usage}
                    size={80}
                    strokeColor="#fa8c16"
                  />
                </div>
              </Col>
            </Row>
          </Card>
        </Col>

        <Col span={10}>
          <Card title="성과 트렌드" size="small">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="efficiency" stroke="#1890ff" name="운영효율성" />
                <Line type="monotone" dataKey="satisfaction" stroke="#52c41a" name="만족도" />
                <Line type="monotone" dataKey="cost_recovery" stroke="#fa8c16" name="비용회수율" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>
    </div>
  );
};