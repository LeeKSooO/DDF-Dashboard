import React, { useState } from 'react';
import { Card, Row, Col, Table, Tag, Button, Space, Modal } from 'antd';
import { EnvironmentOutlined, CarOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { DRTServiceZone } from '../../types/drtMetrics';

export const DRTZoneManager: React.FC = () => {
  const [zones] = useState<DRTServiceZone[]>([
    {
      zone_id: 'ZONE_001',
      zone_name: '상면 우선 권역',
      region: '상면',
      center_lat: 37.72,
      center_lng: 127.32,
      coverage_radius: 5.0,
      total_stops: 124,
      target_stops: [],
      service_type: 'SCHEDULED',
      operating_hours: { start: '06:00', end: '22:00' },
      recommended_vehicles: 4,
      expected_daily_trips: 150,
      connection_points: ['청평역', '가평터미널']
    },
    {
      zone_id: 'ZONE_002',
      zone_name: '청평면 관광 권역',
      region: '청평면',
      center_lat: 37.78,
      center_lng: 127.33,
      coverage_radius: 3.5,
      total_stops: 38,
      target_stops: [],
      service_type: 'HYBRID',
      operating_hours: { start: '07:00', end: '20:00' },
      recommended_vehicles: 2,
      expected_daily_trips: 80,
      connection_points: ['청평역', '청평터미널']
    }
  ]);

  const [modalVisible, setModalVisible] = useState(false);

  const columns = [
    {
      title: '권역명',
      dataIndex: 'zone_name',
      key: 'zone_name',
      render: (text: string, record: DRTServiceZone) => (
        <Space>
          <Tag color="blue">{record.zone_id}</Tag>
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: '서비스 타입',
      dataIndex: 'service_type',
      key: 'service_type',
      render: (type: string) => {
        const typeMap: { [key: string]: { text: string; color: string } } = {
          'ON_DEMAND': { text: '호출형', color: 'orange' },
          'SCHEDULED': { text: '정기형', color: 'green' },
          'HYBRID': { text: '혼합형', color: 'blue' },
        };
        const config = typeMap[type];
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '운영시간',
      key: 'operating_hours',
      render: (record: DRTServiceZone) => (
        <Space>
          <ClockCircleOutlined />
          <span>{record.operating_hours.start} - {record.operating_hours.end}</span>
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
          <span>{vehicles}대</span>
        </Space>
      ),
    },
    {
      title: '예상 일일 운행',
      dataIndex: 'expected_daily_trips',
      key: 'expected_daily_trips',
      render: (trips: number) => `${trips}회`,
    },
    {
      title: '관리',
      key: 'action',
      render: () => (
        <Space>
          <Button size="small" type="primary">수정</Button>
          <Button size="small">상세</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={24}>
          <Card>
            <Row gutter={16}>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>2</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>운영 권역</div>
                </div>
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>6</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>총 권장 차량</div>
                </div>
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fa8c16' }}>230</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>예상 일일 운행</div>
                </div>
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#722ed1' }}>162</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>서비스 대상 정류장</div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Card 
        title="DRT 서비스 권역 관리" 
        size="small"
        extra={
          <Button 
            type="primary" 
            onClick={() => setModalVisible(true)}
          >
            새 권역 추가
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={zones}
          rowKey="zone_id"
          size="small"
          pagination={false}
        />
      </Card>

      <Modal
        title="새 DRT 서비스 권역 추가"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
      >
        <p>권역 설정 기능이 곧 추가됩니다.</p>
      </Modal>
    </div>
  );
};