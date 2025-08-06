import React from 'react';
import { Statistic, Row, Col, Progress } from 'antd';
import { HeatmapData, DRTPrediction } from '../../types';

interface StatsPanelProps {
  heatmapData: HeatmapData[];
  predictions: DRTPrediction[];
  loading?: boolean;
}

export const StatsPanel: React.FC<StatsPanelProps> = ({
  heatmapData,
  predictions,
  loading = false,
}) => {
  // 통계 계산
  const totalStops = predictions.length;
  const averageDRTProb = predictions.length > 0 
    ? predictions.reduce((sum, p) => sum + p.drt_probability, 0) / predictions.length
    : 0;
  
  const highDemandStops = predictions.filter(p => p.drt_probability >= 0.6).length;
  const totalBoardingCount = predictions.reduce((sum, p) => sum + p.predicted_boarding_count, 0);

  // 확률 분포 계산
  const probabilityDistribution = {
    low: predictions.filter(p => p.drt_probability < 0.4).length,
    medium: predictions.filter(p => p.drt_probability >= 0.4 && p.drt_probability < 0.6).length,
    high: predictions.filter(p => p.drt_probability >= 0.6 && p.drt_probability < 0.8).length,
    veryHigh: predictions.filter(p => p.drt_probability >= 0.8).length,
  };

  return (
    <div style={{
      background: '#fff',
      borderRadius: '8px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      marginBottom: '16px'
    }}>
      <div style={{
        padding: '16px 24px 12px 24px',
        borderBottom: '1px solid #f0f0f0'
      }}>
        <h3 style={{
          margin: '0',
          fontSize: '16px',
          fontWeight: 'bold',
          color: '#1890ff'
        }}>
          예측 통계
        </h3>
      </div>

      <div style={{ padding: '16px 24px' }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="전체 정류장"
              value={totalStops}
              suffix="개"
              loading={loading}
              valueStyle={{ fontSize: '20px', fontWeight: 'bold' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="평균 DRT 확률"
              value={averageDRTProb * 100}
              precision={1}
              suffix="%"
              loading={loading}
              valueStyle={{ fontSize: '20px', fontWeight: 'bold', color: '#52c41a' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="고수요 정류장"
              value={highDemandStops}
              suffix="개"
              loading={loading}
              valueStyle={{ fontSize: '20px', fontWeight: 'bold', color: '#ff4d4f' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="예상 총 승차 인원"
              value={totalBoardingCount}
              precision={0}
              suffix="명"
              loading={loading}
              valueStyle={{ fontSize: '20px', fontWeight: 'bold', color: '#1890ff' }}
            />
          </Col>
        </Row>

        {/* 확률 분포 차트 */}
        <div style={{ marginTop: '24px' }}>
          <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 'bold' }}>
            DRT 수요 확률 분포
          </h4>
          
          <div style={{ marginBottom: '12px' }}>
            <Row gutter={8} align="middle">
              <Col span={4}>
                <span style={{ fontSize: '12px', color: '#666' }}>낮음 (0-40%)</span>
              </Col>
              <Col span={16}>
                <Progress
                  percent={totalStops > 0 ? (probabilityDistribution.low / totalStops) * 100 : 0}
                  strokeColor="#52c41a"
                  showInfo={false}
                  size="small"
                />
              </Col>
              <Col span={4} style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  {probabilityDistribution.low}개
                </span>
              </Col>
            </Row>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <Row gutter={8} align="middle">
              <Col span={4}>
                <span style={{ fontSize: '12px', color: '#666' }}>보통 (40-60%)</span>
              </Col>
              <Col span={16}>
                <Progress
                  percent={totalStops > 0 ? (probabilityDistribution.medium / totalStops) * 100 : 0}
                  strokeColor="#faad14"
                  showInfo={false}
                  size="small"
                />
              </Col>
              <Col span={4} style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  {probabilityDistribution.medium}개
                </span>
              </Col>
            </Row>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <Row gutter={8} align="middle">
              <Col span={4}>
                <span style={{ fontSize: '12px', color: '#666' }}>높음 (60-80%)</span>
              </Col>
              <Col span={16}>
                <Progress
                  percent={totalStops > 0 ? (probabilityDistribution.high / totalStops) * 100 : 0}
                  strokeColor="#fa8c16"
                  showInfo={false}
                  size="small"
                />
              </Col>
              <Col span={4} style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  {probabilityDistribution.high}개
                </span>
              </Col>
            </Row>
          </div>

          <div style={{ marginBottom: '8px' }}>
            <Row gutter={8} align="middle">
              <Col span={4}>
                <span style={{ fontSize: '12px', color: '#666' }}>매우높음 (80%+)</span>
              </Col>
              <Col span={16}>
                <Progress
                  percent={totalStops > 0 ? (probabilityDistribution.veryHigh / totalStops) * 100 : 0}
                  strokeColor="#ff4d4f"
                  showInfo={false}
                  size="small"
                />
              </Col>
              <Col span={4} style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  {probabilityDistribution.veryHigh}개
                </span>
              </Col>
            </Row>
          </div>
        </div>

        {/* Top 3 정류장 */}
        {heatmapData.length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 'bold' }}>
              Top 3 고수요 정류장
            </h4>
            {heatmapData.slice(0, 3).map((item, index) => (
              <div key={item.stop_id} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 12px',
                background: index === 0 ? '#fff2e8' : index === 1 ? '#fff7e6' : '#fafafa',
                borderRadius: '4px',
                marginBottom: '4px',
                fontSize: '12px'
              }}>
                <span style={{ fontWeight: 'bold' }}>
                  #{index + 1} {item.stop_name || item.stop_id}
                </span>
                <span style={{ 
                  color: index === 0 ? '#fa541c' : index === 1 ? '#fa8c16' : '#8c8c8c',
                  fontWeight: 'bold'
                }}>
                  {(item.intensity * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};