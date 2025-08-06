import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Progress, Tag, Button, Space, Statistic, Alert, Spin } from 'antd';
import { 
  EnvironmentOutlined, 
  CarOutlined, 
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  WarningOutlined
} from '@ant-design/icons';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { RegionServiceGap } from '../../types/drtMetrics';
import { drtAnalyticsApi } from '../../services/api';

interface ServiceGapAnalysisProps {
  selectedTime: any;
  predictions: any[];
}

export const ServiceGapAnalysis: React.FC<ServiceGapAnalysisProps> = ({
  selectedTime,
  predictions
}) => {
  const [regionData, setRegionData] = useState<RegionServiceGap[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    generateServiceGapData();
  }, [selectedTime]);

  const generateServiceGapData = async () => {
    setLoading(true);
    
    try {
      // 실제 API에서 데이터 가져오기 (날짜와 시간 모두 전달)
      const serviceGapData = await drtAnalyticsApi.getServiceGaps(
        selectedTime?.date, 
        selectedTime?.hour
      );
      setRegionData(serviceGapData);
    } catch (error) {
      console.error('서비스 공백 데이터 로딩 실패:', error);
      // API 실패 시 빈 배열 또는 기본값 설정
      setRegionData([]);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return '#ff4d4f';
      case 'HIGH': return '#fa8c16';
      case 'MEDIUM': return '#fadb14';
      case 'LOW': return '#52c41a';
      default: return '#d9d9d9';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'HIGH': return <WarningOutlined style={{ color: '#fa8c16' }} />;
      case 'MEDIUM': return <ExclamationCircleOutlined style={{ color: '#fadb14' }} />;
      case 'LOW': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      default: return null;
    }
  };

  const columns = [
    {
      title: '지역',
      dataIndex: 'region_kr',
      key: 'region_kr',
      render: (text: string, record: RegionServiceGap) => (
        <Space>
          <Tag color={record.drt_priority <= 2 ? 'red' : record.drt_priority <= 3 ? 'orange' : 'green'}>
            우선순위 {record.drt_priority}
          </Tag>
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: '정류장 현황',
      key: 'stops_status',
      render: (record: RegionServiceGap) => (
        <div>
          <div>전체: {record.total_stops}개</div>
          <div style={{ color: '#52c41a' }}>활성: {record.active_stops}개</div>
          <div style={{ color: '#ff4d4f' }}>미이용: {record.unused_stops}개</div>
        </div>
      ),
    },
    {
      title: '활용률',
      dataIndex: 'utilization_rate',
      key: 'utilization_rate',
      render: (rate: number) => (
        <Progress 
          percent={rate} 
          size="small"
          strokeColor={rate < 30 ? '#ff4d4f' : rate < 60 ? '#fa8c16' : '#52c41a'}
        />
      ),
    },
    {
      title: '승차 현황',
      key: 'boarding_status',
      render: (record: RegionServiceGap) => (
        <div>
          <div>총 승차: {record.total_boarding.toLocaleString()}명</div>
          <div>평균: {record.avg_boarding_per_stop.toFixed(1)}명/정류장</div>
        </div>
      ),
    },
    {
      title: '심각도',
      dataIndex: 'service_gap_severity',
      key: 'service_gap_severity',
      render: (severity: string) => (
        <Space>
          {getSeverityIcon(severity)}
          <Tag color={getSeverityColor(severity)}>{severity}</Tag>
        </Space>
      ),
    },
    {
      title: '권장 차량',
      dataIndex: 'recommended_vehicles',
      key: 'recommended_vehicles',
      render: (vehicles: number) => (
        <Space>
          <CarOutlined />
          <strong>{vehicles}대</strong>
        </Space>
      ),
    },
  ];

  // 파이차트 데이터
  const pieData = regionData.map(region => ({
    name: region.region_kr,
    value: region.unused_stops,
    color: getSeverityColor(region.service_gap_severity)
  }));

  // 바차트 데이터
  const barData = regionData.map(region => ({
    region: region.region_kr,
    활용률: region.utilization_rate,
    미이용정류장: region.unused_stops
  }));

  const totalUnusedStops = regionData.reduce((sum, region) => sum + region.unused_stops, 0);
  const totalRecommendedVehicles = regionData.reduce((sum, region) => sum + region.recommended_vehicles, 0);
  const criticalRegions = regionData.filter(region => region.service_gap_severity === 'CRITICAL').length;

  return (
    <div>
      {/* 요약 통계 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="총 미이용 정류장"
              value={totalUnusedStops}
              suffix="개소"
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<EnvironmentOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="긴급 대응 지역"
              value={criticalRegions}
              suffix="지역"
              valueStyle={{ color: '#fa8c16' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="권장 총 차량"
              value={totalRecommendedVehicles}
              suffix="대"
              valueStyle={{ color: '#1890ff' }}
              prefix={<CarOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="예상 개선율"
              value={85}
              suffix="%"
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 긴급 알림 */}
      <Alert
        message="긴급: 상면 지역 완전한 교통 사각지대"
        description="상면 지역 124개 정류장이 모두 미이용 상태입니다. 즉시 DRT 서비스 도입이 필요합니다."
        type="error"
        showIcon
        style={{ marginBottom: '24px' }}
        action={
          <Button size="small" danger>
            긴급 대응 계획 수립
          </Button>
        }
      />

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 지역별 상세 테이블 */}
        <Col span={14}>
          <Card title="지역별 서비스 공백 현황" size="small">
            <Table
              columns={columns}
              dataSource={regionData}
              rowKey="region"
              loading={loading}
              size="small"
              pagination={false}
            />
          </Card>
        </Col>

        {/* 시각화 차트 */}
        <Col span={10}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card title="미이용 정류장 분포" size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}개`}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={24}>
              <Card title="지역별 활용률 비교" size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="region" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="활용률" fill="#1890ff" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      {/* DRT 도입 권장사항 */}
      <Card title="DRT 도입 권장사항" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Card type="inner" title="Phase 1: 긴급 대응 (즉시)" size="small">
              <ul style={{ paddingLeft: '20px', margin: 0 }}>
                <li><strong>상면 지역</strong>: 4대 차량 투입</li>
                <li>기본 순환 노선 운영</li>
                <li>06:00-22:00 운영 시간</li>
                <li>30분 간격 정기 운행</li>
              </ul>
            </Card>
          </Col>
          <Col span={8}>
            <Card type="inner" title="Phase 2: 단기 확장 (3개월)" size="small">
              <ul style={{ paddingLeft: '20px', margin: 0 }}>
                <li><strong>청평면</strong>: 2대 차량 추가</li>
                <li><strong>가평읍</strong>: 3대 차량 연계</li>
                <li>관광 수요 대응 노선</li>
                <li>기존 버스와 환승 연계</li>
              </ul>
            </Card>
          </Col>
          <Col span={8}>
            <Card type="inner" title="Phase 3: 통합 운영 (6개월)" size="small">
              <ul style={{ paddingLeft: '20px', margin: 0 }}>
                <li>전 지역 통합 예약 시스템</li>
                <li>AI 기반 동적 배차</li>
                <li>북면/조종면 보완 서비스</li>
                <li>성과 측정 및 최적화</li>
              </ul>
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default ServiceGapAnalysis;