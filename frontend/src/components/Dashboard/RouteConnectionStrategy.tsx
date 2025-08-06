import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Progress, Space, Button, Spin } from 'antd';
import { CarOutlined, NodeIndexOutlined, LinkOutlined } from '@ant-design/icons';
import { RouteConnectionStrategy as RouteStrategy } from '../../types/drtMetrics';
import { drtAnalyticsApi } from '../../services/api';

export const RouteConnectionStrategy: React.FC = () => {
  const [routeData, setRouteData] = useState<RouteStrategy[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadRouteStrategies();
  }, []);

  const loadRouteStrategies = async () => {
    setLoading(true);
    
    try {
      const strategies = await drtAnalyticsApi.getRouteStrategies();
      setRouteData(strategies);
    } catch (error) {
      console.error('노선 연계 전략 데이터 로딩 실패:', error);
      setRouteData([]);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '노선',
      dataIndex: 'route_number',
      key: 'route_number',
      render: (text: string, record: RouteStrategy) => (
        <Space>
          <Tag color="blue">{text}</Tag>
          <span style={{ fontSize: '12px' }}>{record.route_type}</span>
        </Space>
      ),
    },
    {
      title: '효율성',
      dataIndex: 'efficiency_grade',
      key: 'efficiency_grade',
      render: (grade: string) => {
        const gradeMap: { [key: string]: { text: string; color: string } } = {
          'HIGH_EFFICIENCY': { text: '높음', color: 'green' },
          'MEDIUM_EFFICIENCY': { text: '보통', color: 'orange' },
          'LOW_EFFICIENCY': { text: '낮음', color: 'red' },
          'POOR_EFFICIENCY': { text: '매우낮음', color: 'red' },
        };
        const config = gradeMap[grade];
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '정류장 활용률',
      dataIndex: 'utilization_rate',
      key: 'utilization_rate',
      render: (rate: number) => (
        <Progress 
          percent={rate} 
          size="small"
          strokeColor={rate >= 80 ? '#52c41a' : rate >= 60 ? '#fa8c16' : '#ff4d4f'}
        />
      ),
    },
    {
      title: 'DRT 연계 전략',
      dataIndex: 'drt_connection_type',
      key: 'drt_connection_type',
      render: (type: string) => {
        const typeMap: { [key: string]: { text: string; color: string; icon: any } } = {
          'HUB_CONNECTION': { text: '허브연계', color: 'blue', icon: <NodeIndexOutlined /> },
          'FEEDER_SERVICE': { text: '피더서비스', color: 'green', icon: <LinkOutlined /> },
          'ROUTE_REPLACEMENT': { text: '노선대체', color: 'orange', icon: <CarOutlined /> },
          'NO_CONNECTION': { text: '연계불필요', color: 'default', icon: null },
        };
        const config = typeMap[type];
        return (
          <Space>
            {config.icon}
            <Tag color={config.color}>{config.text}</Tag>
          </Space>
        );
      },
    },
    {
      title: '미활용 정류장',
      dataIndex: 'underutilized_stops',
      key: 'underutilized_stops',
      render: (stops: number) => (
        <span style={{ color: stops > 50 ? '#ff4d4f' : '#666' }}>
          {stops}개
        </span>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>8개</div>
              <div style={{ fontSize: '12px', color: '#666' }}>고효율 노선</div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fa8c16' }}>4개</div>
              <div style={{ fontSize: '12px', color: '#666' }}>저효율 노선</div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>118개</div>
              <div style={{ fontSize: '12px', color: '#666' }}>DRT 대상 정류장</div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="노선별 DRT 연계 전략" size="small">
        <Table
          columns={columns}
          dataSource={routeData}
          rowKey="route_number"
          size="small"
          pagination={false}
          loading={loading}
        />
      </Card>

      <Row gutter={16} style={{ marginTop: '16px' }}>
        <Col span={8}>
          <Card type="inner" title="허브 연계형" size="small">
            <p style={{ fontSize: '12px' }}>고효율 노선과 DRT 환승 허브 구축</p>
            <Button size="small" type="primary">세부 계획</Button>
          </Card>
        </Col>
        <Col span={8}>
          <Card type="inner" title="피더 서비스형" size="small">
            <p style={{ fontSize: '12px' }}>버스 정류장까지 연결 서비스</p>
            <Button size="small" type="primary">세부 계획</Button>
          </Card>
        </Col>
        <Col span={8}>
          <Card type="inner" title="노선 대체형" size="small">
            <p style={{ fontSize: '12px' }}>저효율 구간 DRT 전환</p>
            <Button size="small" type="primary">세부 계획</Button>
          </Card>
        </Col>
      </Row>
    </div>
  );
};