import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Progress, Alert, Badge, Statistic, Timeline } from 'antd';
import { 
  CarOutlined, 
  ClockCircleOutlined, 
  ExclamationCircleOutlined, 
  CheckCircleOutlined,
  WarningOutlined
} from '@ant-design/icons';
import moment from 'moment';

interface OperationalMonitorProps {
  selectedTime: any;
  predictions: any[];
}

interface VehicleStatus {
  vehicleId: string;
  routeName: string;
  currentLoad: number;
  maxCapacity: number;
  status: 'active' | 'idle' | 'maintenance';
  lastUpdate: string;
  estimatedArrival: string;
}

interface ServiceAlert {
  id: string;
  type: 'warning' | 'error' | 'info';
  title: string;
  description: string;
  timestamp: string;
  resolved: boolean;
}

interface RoutePerformance {
  routeId: string;
  routeName: string;
  onTimePerformance: number;
  demandSatisfaction: number;
  averageWaitTime: number;
  totalRiders: number;
}

export const OperationalMonitor: React.FC<OperationalMonitorProps> = ({
  selectedTime,
  predictions
}) => {
  const [vehicleData, setVehicleData] = useState<VehicleStatus[]>([]);
  const [alerts, setAlerts] = useState<ServiceAlert[]>([]);
  const [routePerformance, setRoutePerformance] = useState<RoutePerformance[]>([]);
  const [systemStatus, setSystemStatus] = useState({
    totalVehicles: 0,
    activeVehicles: 0,
    systemUptime: 99.5,
    responseTime: 156
  });

  useEffect(() => {
    generateOperationalData();
    
    // 30초마다 데이터 업데이트 시뮬레이션
    const interval = setInterval(generateOperationalData, 30000);
    return () => clearInterval(interval);
  }, []);

  const generateOperationalData = () => {
    // 차량 상태 시뮬레이션
    const vehicles: VehicleStatus[] = [
      {
        vehicleId: 'DRT-001',
        routeName: '40-5',
        currentLoad: 8,
        maxCapacity: 12,
        status: 'active',
        lastUpdate: moment().subtract(2, 'minutes').format('HH:mm:ss'),
        estimatedArrival: moment().add(5, 'minutes').format('HH:mm')
      },
      {
        vehicleId: 'DRT-002', 
        routeName: '1330-44',
        currentLoad: 15,
        maxCapacity: 25,
        status: 'active',
        lastUpdate: moment().subtract(1, 'minute').format('HH:mm:ss'),
        estimatedArrival: moment().add(3, 'minutes').format('HH:mm')
      },
      {
        vehicleId: 'DRT-003',
        routeName: '7000',
        currentLoad: 0,
        maxCapacity: 45,
        status: 'idle',
        lastUpdate: moment().subtract(10, 'minutes').format('HH:mm:ss'),
        estimatedArrival: '-'
      },
      {
        vehicleId: 'DRT-004',
        routeName: '43',
        currentLoad: 0,
        maxCapacity: 20,
        status: 'maintenance',
        lastUpdate: moment().subtract(30, 'minutes').format('HH:mm:ss'),
        estimatedArrival: '-'
      }
    ];
    setVehicleData(vehicles);

    // 시스템 알림 시뮬레이션
    const systemAlerts: ServiceAlert[] = [
      {
        id: '1',
        type: 'warning',
        title: '가평터미널 수요 급증',
        description: '예상 대비 40% 높은 수요가 감지되었습니다.',
        timestamp: moment().subtract(5, 'minutes').format('HH:mm'),
        resolved: false
      },
      {
        id: '2', 
        type: 'info',
        title: '노선 40-5 정상 운행',
        description: '지연 없이 정상 운행 중입니다.',
        timestamp: moment().subtract(15, 'minutes').format('HH:mm'),
        resolved: true
      },
      {
        id: '3',
        type: 'error',
        title: 'DRT-004 정비 필요',
        description: '정기 점검으로 인한 운행 중단',
        timestamp: moment().subtract(25, 'minutes').format('HH:mm'),
        resolved: false
      }
    ];
    setAlerts(systemAlerts);

    // 노선 성과 시뮬레이션
    const performance: RoutePerformance[] = [
      {
        routeId: 'GGB239000005',
        routeName: '40-5',
        onTimePerformance: 94,
        demandSatisfaction: 87,
        averageWaitTime: 8.5,
        totalRiders: 156
      },
      {
        routeId: 'GGB239000024', 
        routeName: '1330-44',
        onTimePerformance: 89,
        demandSatisfaction: 92,
        averageWaitTime: 12.3,
        totalRiders: 234
      },
      {
        routeId: 'GGB239000139',
        routeName: '7000',
        onTimePerformance: 96,
        demandSatisfaction: 85,
        averageWaitTime: 6.8,
        totalRiders: 189
      }
    ];
    setRoutePerformance(performance);

    // 시스템 상태 업데이트
    setSystemStatus({
      totalVehicles: vehicles.length,
      activeVehicles: vehicles.filter(v => v.status === 'active').length,
      systemUptime: 99.5 + Math.random() * 0.4,
      responseTime: 150 + Math.random() * 20
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'green';
      case 'idle': return 'orange';
      case 'maintenance': return 'red';
      default: return 'default';
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'error': return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'warning': return <WarningOutlined style={{ color: '#fa8c16' }} />;
      case 'info': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      default: return null;
    }
  };

  const vehicleColumns = [
    {
      title: '차량 ID',
      dataIndex: 'vehicleId',
      key: 'vehicleId',
    },
    {
      title: '노선',
      dataIndex: 'routeName',
      key: 'routeName',
    },
    {
      title: '승차율',
      key: 'occupancy',
      render: (record: VehicleStatus) => (
        <div>
          <Progress 
            percent={Math.round((record.currentLoad / record.maxCapacity) * 100)}
            size="small"
            status={record.currentLoad / record.maxCapacity > 0.8 ? 'exception' : 'normal'}
          />
          <span style={{ fontSize: '12px', color: '#666' }}>
            {record.currentLoad}/{record.maxCapacity}
          </span>
        </div>
      ),
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {status === 'active' ? '운행중' : status === 'idle' ? '대기' : '정비'}
        </Tag>
      ),
    },
    {
      title: '도착 예정',
      dataIndex: 'estimatedArrival',
      key: 'estimatedArrival',
    },
  ];

  const performanceColumns = [
    {
      title: '노선',
      dataIndex: 'routeName',
      key: 'routeName',
    },
    {
      title: '정시 운행률',
      dataIndex: 'onTimePerformance',
      key: 'onTimePerformance',
      render: (value: number) => `${value}%`,
    },
    {
      title: '수요 충족률',
      dataIndex: 'demandSatisfaction', 
      key: 'demandSatisfaction',
      render: (value: number) => `${value}%`,
    },
    {
      title: '평균 대기시간',
      dataIndex: 'averageWaitTime',
      key: 'averageWaitTime',
      render: (value: number) => `${value}분`,
    },
    {
      title: '총 이용객',
      dataIndex: 'totalRiders',
      key: 'totalRiders',
      render: (value: number) => `${value}명`,
    },
  ];

  return (
    <div style={{ padding: '16px' }}>
      {/* 시스템 상태 개요 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="총 차량 수"
              value={systemStatus.totalVehicles}
              suffix="대"
              prefix={<CarOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="운행 중 차량"
              value={systemStatus.activeVehicles}
              suffix="대"
              valueStyle={{ color: '#52c41a' }}
              prefix={<CarOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="시스템 가동률"
              value={systemStatus.systemUptime}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="평균 응답시간"
              value={systemStatus.responseTime}
              suffix="ms"
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {/* 실시간 차량 현황 */}
        <Col span={16}>
          <Card title="실시간 차량 현황" size="small">
            <Table
              dataSource={vehicleData}
              columns={vehicleColumns}
              pagination={false}
              size="small"
              rowKey="vehicleId"
            />
          </Card>
        </Col>

        {/* 시스템 알림 */}
        <Col span={8}>
          <Card title="시스템 알림" size="small">
            <Timeline
              items={alerts.map(alert => ({
                color: alert.type === 'error' ? 'red' : alert.type === 'warning' ? 'orange' : 'green',
                children: (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {getAlertIcon(alert.type)}
                      <strong>{alert.title}</strong>
                      <Badge status={alert.resolved ? 'success' : 'processing'} />
                    </div>
                    <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                      {alert.description}
                    </div>
                    <div style={{ fontSize: '11px', color: '#999', marginTop: '2px' }}>
                      {alert.timestamp}
                    </div>
                  </div>
                )
              }))}
            />
          </Card>
        </Col>
      </Row>

      {/* 노선별 성과 지표 */}
      <Row gutter={16}>
        <Col span={24}>
          <Card title="노선별 운영 성과" size="small">
            <Table
              dataSource={routePerformance}
              columns={performanceColumns}
              pagination={false}
              size="small"
              rowKey="routeId"
            />
          </Card>
        </Col>
      </Row>

      {/* 미해결 알림이 있을 경우 경고 표시 */}
      {alerts.some(alert => !alert.resolved) && (
        <Alert
          message="주의가 필요한 상황이 있습니다"
          description="미해결 알림을 확인하고 필요한 조치를 취해주세요."
          type="warning"
          showIcon
          style={{ marginTop: '16px' }}
        />
      )}
    </div>
  );
};