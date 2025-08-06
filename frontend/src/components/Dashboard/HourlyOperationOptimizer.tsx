import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Space, Slider, Switch, Alert, Spin } from 'antd';
import { 
  ClockCircleOutlined, 
  CarOutlined, 
  UserOutlined,
  ThunderboltOutlined,
  PauseCircleOutlined
} from '@ant-design/icons';
import { 
  LineChart, 
  Line, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { HourlyDRTNeed } from '../../types/drtMetrics';
import { drtAnalyticsApi } from '../../services/api';

interface HourlyOperationOptimizerProps {
  selectedTime: any;
}

export const HourlyOperationOptimizer: React.FC<HourlyOperationOptimizerProps> = ({
  selectedTime
}) => {
  const [hourlyData, setHourlyData] = useState<HourlyDRTNeed[]>([]);
  const [optimizationMode, setOptimizationMode] = useState<'cost' | 'service'>('service');
  const [vehicleCount, setVehicleCount] = useState(8);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    generateHourlyOptimizationData();
  }, [selectedTime, optimizationMode, vehicleCount]);

  const generateHourlyOptimizationData = async () => {
    setLoading(true);
    
    try {
      // 실제 API에서 시간대별 데이터 가져오기 (날짜와 시간 모두 전달)
      const hourlyNeeds = await drtAnalyticsApi.getHourlyOptimization(
        selectedTime?.date, 
        selectedTime?.hour
      );
      setHourlyData(hourlyNeeds);
    } catch (error) {
      console.error('시간대별 최적화 데이터 로딩 실패:', error);
      setHourlyData([]);
    } finally {
      setLoading(false);
    }
  };

  const getOperationModeColor = (mode: string) => {
    switch (mode) {
      case 'EXCLUSIVE': return '#ff4d4f';
      case 'PRIMARY': return '#fa8c16';
      case 'SUPPLEMENTARY': return '#52c41a';
      case 'NOT_NEEDED': return '#d9d9d9';
      default: return '#1890ff';
    }
  };

  const getOperationModeIcon = (mode: string) => {
    switch (mode) {
      case 'EXCLUSIVE': return <ThunderboltOutlined />;
      case 'PRIMARY': return <CarOutlined />;
      case 'SUPPLEMENTARY': return <UserOutlined />;
      case 'NOT_NEEDED': return <PauseCircleOutlined />;
      default: return <ClockCircleOutlined />;
    }
  };

  const columns = [
    {
      title: '시간',
      dataIndex: 'hour',
      key: 'hour',
      render: (hour: number) => (
        <Tag color="blue">{hour.toString().padStart(2, '0')}:00</Tag>
      ),
    },
    {
      title: '시간대 구분',
      dataIndex: 'time_category',
      key: 'time_category',
      render: (category: string) => {
        const categoryMap: { [key: string]: { text: string; color: string } } = {
          'MORNING_PEAK': { text: '오전피크', color: 'red' },
          'EVENING_PEAK': { text: '저녁피크', color: 'red' },
          'DAYTIME_OFF_PEAK': { text: '주간오프피크', color: 'orange' },
          'EVENING_OFF_PEAK': { text: '저녁오프피크', color: 'orange' },
          'NIGHT_TIME': { text: '심야', color: 'purple' },
        };
        const config = categoryMap[category] || { text: category, color: 'default' };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '이용객 수',
      dataIndex: 'total_passengers',
      key: 'total_passengers',
      render: (passengers: number) => (
        <span>{passengers.toLocaleString()}명</span>
      ),
    },
    {
      title: '버스 서비스',
      dataIndex: 'bus_service_adequacy',
      key: 'bus_service_adequacy',
      render: (adequacy: string) => {
        const adequacyMap: { [key: string]: { text: string; color: string } } = {
          'SUFFICIENT': { text: '충분', color: 'green' },
          'NEEDS_SUPPLEMENT': { text: '보완필요', color: 'orange' },
          'INSUFFICIENT': { text: '부족', color: 'red' },
        };
        const config = adequacyMap[adequacy] || { text: adequacy, color: 'default' };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: 'DRT 운영 모드',
      dataIndex: 'drt_operation_mode',
      key: 'drt_operation_mode',
      render: (mode: string) => {
        const modeMap: { [key: string]: string } = {
          'EXCLUSIVE': '전용운영',
          'PRIMARY': '주서비스',
          'SUPPLEMENTARY': '보조서비스',
          'NOT_NEEDED': '불필요',
        };
        return (
          <Space>
            {getOperationModeIcon(mode)}
            <Tag color={getOperationModeColor(mode)}>
              {modeMap[mode] || mode}
            </Tag>
          </Space>
        );
      },
    },
    {
      title: '권장 배차간격',
      dataIndex: 'recommended_frequency',
      key: 'recommended_frequency',
      render: (frequency: number) => (
        <span>{frequency}분</span>
      ),
    },
  ];

  // 차트 데이터 준비
  const chartData = hourlyData.map(item => ({
    hour: item.hour,
    이용객수: item.total_passengers,
    권장배차간격: item.recommended_frequency,
    DRT필요도: item.drt_operation_mode === 'EXCLUSIVE' ? 100 : 
               item.drt_operation_mode === 'PRIMARY' ? 80 :
               item.drt_operation_mode === 'SUPPLEMENTARY' ? 40 : 0
  }));

  return (
    <div>
      {/* 제어 패널 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={12}>
          <Card title="최적화 설정" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <span>최적화 기준: </span>
                <Switch
                  checked={optimizationMode === 'service'}
                  onChange={(checked) => setOptimizationMode(checked ? 'service' : 'cost')}
                  checkedChildren="서비스 중심"
                  unCheckedChildren="비용 중심"
                />
              </div>
              <div>
                <span>총 운영 차량: {vehicleCount}대</span>
                <Slider
                  min={4}
                  max={16}
                  value={vehicleCount}
                  onChange={setVehicleCount}
                  marks={{ 4: '4대', 8: '8대', 12: '12대', 16: '16대' }}
                />
              </div>
            </Space>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="운영 요약" size="small">
            <Row gutter={8}>
              <Col span={12}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>
                    14:00
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>DRT 최적 운영 시간</div>
                </div>
              </Col>
              <Col span={12}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>
                    85%
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>예상 운영 효율성</div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 중요 권장사항 알림 */}
      <Alert
        message="주간 오프피크 시간대(10-16시) DRT 주 서비스 운영 권장"
        description="이 시간대는 버스 서비스가 부족하면서도 지속적인 수요가 있어 DRT 운영 효과가 가장 높습니다."
        type="info"
        showIcon
        style={{ marginBottom: '24px' }}
      />

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 시간대별 상세 테이블 */}
        <Col span={14}>
          <Card title="시간대별 DRT 운영 계획" size="small">
            <Table
              columns={columns}
              dataSource={hourlyData}
              rowKey="hour"
              loading={loading}
              size="small"
              pagination={false}
              scroll={{ y: 400 }}
            />
          </Card>
        </Col>

        {/* 시각화 차트 */}
        <Col span={10}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card title="시간대별 이용객 수 vs DRT 필요도" size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="이용객수"
                      stackId="1"
                      stroke="#1890ff"
                      fill="#1890ff"
                      fillOpacity={0.3}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="DRT필요도"
                      stroke="#ff4d4f"
                      strokeWidth={3}
                      dot={{ fill: '#ff4d4f', strokeWidth: 2, r: 4 }}
                    />
                    <ReferenceLine yAxisId="right" y={60} stroke="#fa8c16" strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={24}>
              <Card title="권장 배차 간격" size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" />
                    <YAxis />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="권장배차간격"
                      stroke="#52c41a"
                      fill="#52c41a"
                      fillOpacity={0.6}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      {/* 운영 전략 카드 */}
      <Row gutter={16}>
        <Col span={6}>
          <Card type="inner" title="심야 운영 (00-06시)" size="small">
            <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '12px' }}>
              <li>전용 DRT 서비스</li>
              <li>60-120분 배차</li>
              <li>응급/의료 수요 대응</li>
              <li>2대 차량 순환</li>
            </ul>
          </Card>
        </Col>
        <Col span={6}>
          <Card type="inner" title="피크 시간 (07-09, 17-19시)" size="small">
            <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '12px' }}>
              <li>버스 보조 서비스</li>
              <li>12-20분 배차</li>
              <li>환승 연계 중심</li>
              <li>4대 차량 집중</li>
            </ul>
          </Card>
        </Col>
        <Col span={6}>
          <Card type="inner" title="주간 오프피크 (10-16시)" size="small">
            <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '12px' }}>
              <li><strong>주 서비스 운영</strong></li>
              <li>8-10분 고빈도 배차</li>
              <li>최대 6대 차량 투입</li>
              <li>수요 대응형 운영</li>
            </ul>
          </Card>
        </Col>
        <Col span={6}>
          <Card type="inner" title="저녁 오프피크 (20-23시)" size="small">
            <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '12px' }}>
              <li>DRT 주 서비스</li>
              <li>25-40분 배차</li>
              <li>야간 연계 교통</li>
              <li>3대 차량 운영</li>
            </ul>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default HourlyOperationOptimizer;