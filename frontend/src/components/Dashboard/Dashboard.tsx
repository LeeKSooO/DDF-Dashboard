import React, { useState, useEffect } from 'react';
import { Layout, Button, Alert, Spin, notification, Switch, Tabs } from 'antd';
import { ReloadOutlined, EnvironmentOutlined, BranchesOutlined, BarChartOutlined, DashboardOutlined } from '@ant-design/icons';
import { TimeSelector } from '../TimeSelector/TimeSelector';
import { DRTMap } from '../Map/DRTMap';
import { StatsPanel } from '../StatsPanel/StatsPanel';
import { DemandAnalytics } from './DemandAnalytics';
import { DRTOperationalDashboard } from './DRTOperationalDashboard';
import { predictionApi, busStopApi } from '../../services/api';
import { TimeSelection, BusStop, HeatmapData, DRTPrediction } from '../../types';

const { Header, Content, Sider } = Layout;

export const Dashboard: React.FC = () => {
  // 상태 관리 - 데이터 범위 내 날짜로 초기값 설정
  const [selectedTime, setSelectedTime] = useState<TimeSelection>({
    date: '2024-11-15', // 데이터 범위 내 날짜
    hour: 9,
  });
  
  const [busStops, setBusStops] = useState<BusStop[]>([]);
  const [heatmapData, setHeatmapData] = useState<HeatmapData[]>([]);
  const [predictions, setPredictions] = useState<DRTPrediction[]>([]);
  const [selectedStopId, setSelectedStopId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [showRoutes, setShowRoutes] = useState(false);

  // 초기 데이터 로딩
  useEffect(() => {
    loadBusStops();
  }, []);

  // 정류장 데이터 로딩
  const loadBusStops = async () => {
    try {
      const stops = await busStopApi.getAllStops();
      setBusStops(stops);
    } catch (err) {
      console.error('정류장 데이터 로딩 실패:', err);
      setError('정류장 데이터를 불러오는데 실패했습니다.');
    }
  };

  // 예측 데이터 로딩
  const loadPredictions = async () => {
    if (!selectedTime.date || selectedTime.hour === undefined) return;

    setLoading(true);
    setError('');

    try {
      const targetDatetime = `${selectedTime.date} ${String(selectedTime.hour).padStart(2, '0')}:00:00`;
      
      // 전체 예측 데이터 가져오기 (한 번의 API 호출)
      const fullPredictionResponse = await predictionApi.getPredictions(targetDatetime);
      setPredictions(fullPredictionResponse.predictions);

      // 히트맵 데이터 생성 (상위 10개 정류장)
      const busStops = await busStopApi.getAllStops();
      const topPredictions = fullPredictionResponse.predictions
        .sort((a, b) => b.drt_probability - a.drt_probability)
        .slice(0, 10);
      
      const heatmapData = topPredictions.map((pred) => {
        const stop = busStops.find(s => s.stop_id === pred.stop_id);
        return {
          latitude: stop?.latitude || 0,
          longitude: stop?.longitude || 0,
          intensity: pred.drt_probability,
          stop_id: pred.stop_id,
          stop_name: stop?.stop_name,
        };
      });
      setHeatmapData(heatmapData);

      notification.success({
        message: '예측 완료',
        description: `${targetDatetime} 시점의 DRT 수요 예측이 완료되었습니다.`,
        duration: 3,
      });

    } catch (err: any) {
      console.error('예측 데이터 로딩 실패:', err);
      let errorMsg = '예측 데이터를 불러오는데 실패했습니다.';
      
      // API 오류 메시지 추출
      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMsg = err.response.data.detail;
        } else {
          errorMsg = '서버 오류가 발생했습니다.';
        }
      }
      
      setError(errorMsg);
      
      notification.error({
        message: '예측 실패',
        description: errorMsg,
        duration: 5,
      });
    } finally {
      setLoading(false);
    }
  };

  // 정류장 클릭 핸들러
  const handleStopClick = (stopId: string) => {
    setSelectedStopId(selectedStopId === stopId ? '' : stopId);
  };

  // 새로고침 핸들러
  const handleRefresh = () => {
    loadPredictions();
  };

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Header style={{
        background: '#1890ff',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <EnvironmentOutlined style={{ 
            fontSize: '24px', 
            color: 'white', 
            marginRight: '12px' 
          }} />
          <h1 style={{
            color: 'white',
            margin: 0,
            fontSize: '20px',
            fontWeight: 'bold'
          }}>
            가평군 DRT 수요 예측 대시보드
          </h1>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BranchesOutlined style={{ color: 'white', fontSize: '16px' }} />
            <span style={{ color: 'white', fontSize: '14px' }}>노선 표시</span>
            <Switch
              checked={showRoutes}
              onChange={setShowRoutes}
              size="small"
            />
          </div>
          <span style={{ color: 'white', fontSize: '14px' }}>
            MST-GCN 모델 기반 예측
          </span>
          <Button
            type="primary"
            ghost
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading}
          >
            새로고침
          </Button>
        </div>
      </Header>

      <Layout>
        <Sider 
          width={350} 
          style={{ 
            background: 'transparent',
            padding: '16px 0 16px 16px'
          }}
        >
          <div style={{ height: '100%', overflowY: 'auto' }}>
            {/* 시간 선택기 */}
            <TimeSelector
              selectedTime={selectedTime}
              onChange={(newTime) => {
                setSelectedTime(newTime);
                // 시간 변경 시 자동으로 예측 데이터 새로고침
                if (newTime.date && newTime.hour !== undefined) {
                  setTimeout(() => loadPredictions(), 100);
                }
              }}
              loading={loading}
              onPredict={loadPredictions}
            />

            {/* 통계 패널 */}
            <StatsPanel
              heatmapData={heatmapData}
              predictions={predictions}
              loading={loading}
            />

            {/* 오류 표시 */}
            {error && (
              <Alert
                message="오류 발생"
                description={error}
                type="error"
                closable
                onClose={() => setError('')}
                style={{ marginBottom: '16px' }}
              />
            )}

            {/* 로딩 상태 */}
            {loading && (
              <div style={{
                background: '#fff',
                borderRadius: '8px',
                padding: '24px',
                textAlign: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
              }}>
                <Spin size="large" />
                <div style={{ marginTop: '12px', color: '#666' }}>
                  DRT 수요 예측 중...
                </div>
              </div>
            )}
          </div>
        </Sider>

        <Content style={{ 
          margin: '16px 16px 16px 0',
          background: '#fff',
          borderRadius: '8px',
          overflow: 'hidden',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}>
          <Tabs
            defaultActiveKey="map"
            style={{ height: '100%' }}
            items={[
              {
                key: 'map',
                label: (
                  <span>
                    <EnvironmentOutlined />
                    지도 뷰
                  </span>
                ),
                children: (
                  <div style={{ height: 'calc(100vh - 180px)', position: 'relative' }}>
                    {/* 지도 컴포넌트 */}
                    <DRTMap
                      busStops={busStops}
                      heatmapData={heatmapData}
                      onStopClick={handleStopClick}
                      selectedStopId={selectedStopId}
                      showRoutes={showRoutes}
                    />

                    {/* 지도 위 정보 패널 */}
                    <div style={{
                      position: 'absolute',
                      top: '16px',
                      right: '16px',
                      background: 'rgba(255, 255, 255, 0.95)',
                      borderRadius: '6px',
                      padding: '12px 16px',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                      fontSize: '12px',
                      maxWidth: '200px'
                    }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#1890ff' }}>
                        범례
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ 
                          width: '12px', 
                          height: '12px', 
                          background: '#ff0000', 
                          borderRadius: '50%',
                          marginRight: '8px' 
                        }} />
                        <span>매우 높음 (80%+)</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ 
                          width: '12px', 
                          height: '12px', 
                          background: '#ff8000', 
                          borderRadius: '50%',
                          marginRight: '8px' 
                        }} />
                        <span>높음 (60-80%)</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ 
                          width: '12px', 
                          height: '12px', 
                          background: '#ffff00', 
                          borderRadius: '50%',
                          marginRight: '8px' 
                        }} />
                        <span>보통 (40-60%)</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ 
                          width: '12px', 
                          height: '12px', 
                          background: '#00ff00', 
                          borderRadius: '50%',
                          marginRight: '8px' 
                        }} />
                        <span>낮음 (0-40%)</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{ 
                          width: '12px', 
                          height: '12px', 
                          background: '#cccccc', 
                          borderRadius: '50%',
                          marginRight: '8px' 
                        }} />
                        <span>일반 정류장</span>
                      </div>
                    </div>
                  </div>
                )
              },
              {
                key: 'analytics',
                label: (
                  <span>
                    <BarChartOutlined />
                    수요 분석
                  </span>
                ),
                children: (
                  <div style={{ height: 'calc(100vh - 180px)', overflow: 'auto' }}>
                    <DemandAnalytics
                      selectedTime={selectedTime}
                      predictions={predictions}
                      heatmapData={heatmapData}
                    />
                  </div>
                )
              },
              {
                key: 'drt-management',
                label: (
                  <span>
                    <DashboardOutlined />
                    DRT 운영 관리
                  </span>
                ),
                children: (
                  <div style={{ height: 'calc(100vh - 180px)', overflow: 'auto' }}>
                    <DRTOperationalDashboard
                      selectedTime={selectedTime}
                      predictions={predictions}
                      heatmapData={heatmapData}
                    />
                  </div>
                )
              }
            ]}
          />
        </Content>
      </Layout>
    </Layout>
  );
};