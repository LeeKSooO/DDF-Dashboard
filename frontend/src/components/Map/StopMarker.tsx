import React from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { BusStop, DRTPrediction } from '../../types';

interface StopMarkerProps {
  stop: BusStop;
  prediction?: DRTPrediction;
  isSelected?: boolean;
  onClick: (stopId: string) => void;
}

export const StopMarker: React.FC<StopMarkerProps> = ({
  stop,
  prediction,
  isSelected = false,
  onClick,
}) => {
  // DRT 확률에 따른 색상 결정
  const getMarkerColor = (drtProbability?: number): string => {
    if (!drtProbability) return '#cccccc'; // 회색 - 데이터 없음
    if (drtProbability >= 0.8) return '#ff0000'; // 빨간색 - 매우 높음
    if (drtProbability >= 0.6) return '#ff8000'; // 주황색 - 높음
    if (drtProbability >= 0.4) return '#ffff00'; // 노란색 - 보통
    return '#00ff00'; // 초록색 - 낮음
  };

  // 커스텀 마커 아이콘 생성
  const createMarkerIcon = () => {
    const color = getMarkerColor(prediction?.drt_probability);
    const size = isSelected ? 16 : 12;
    const borderColor = isSelected ? '#000' : '#fff';
    const borderWidth = isSelected ? 3 : 2;

    return L.divIcon({
      html: `
        <div style="
          background-color: ${color};
          width: ${size}px;
          height: ${size}px;
          border-radius: 50%;
          border: ${borderWidth}px solid ${borderColor};
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 8px;
          font-weight: bold;
          color: ${color === '#ffff00' ? '#000' : '#fff'};
        ">
          ${prediction ? Math.round(prediction.drt_probability * 100) : ''}
        </div>
      `,
      className: 'custom-stop-marker',
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  };

  // 확률 레벨 텍스트
  const getProbabilityLevel = (probability?: number): string => {
    if (!probability) return '정보없음';
    if (probability >= 0.8) return '매우 높음';
    if (probability >= 0.6) return '높음';
    if (probability >= 0.4) return '보통';
    return '낮음';
  };

  return (
    <Marker
      position={[stop.latitude, stop.longitude]}
      icon={createMarkerIcon()}
      eventHandlers={{
        click: () => onClick(stop.stop_id),
      }}
    >
      <Popup>
        <div style={{ minWidth: '250px', maxWidth: '300px' }}>
          <div style={{ 
            borderBottom: '1px solid #f0f0f0', 
            paddingBottom: '8px', 
            marginBottom: '8px' 
          }}>
            <h4 style={{ 
              margin: '0', 
              color: '#1890ff', 
              fontSize: '14px',
              fontWeight: 'bold'
            }}>
              {stop.stop_name || stop.stop_id}
            </h4>
            <div style={{ fontSize: '11px', color: '#999', marginTop: '2px' }}>
              {stop.stop_id} • {stop.district}
            </div>
          </div>

          {prediction && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                marginBottom: '4px' 
              }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                  DRT 수요 확률:
                </span>
                <span style={{ 
                  marginLeft: '8px',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  color: getMarkerColor(prediction.drt_probability)
                }}>
                  {(prediction.drt_probability * 100).toFixed(1)}%
                </span>
                <span style={{ 
                  marginLeft: '4px',
                  fontSize: '10px',
                  color: '#666',
                  fontStyle: 'italic'
                }}>
                  ({getProbabilityLevel(prediction.drt_probability)})
                </span>
              </div>

              <div style={{ fontSize: '11px', color: '#666' }}>
                <div style={{ marginBottom: '2px' }}>
                  예상 승차 인원: {prediction.predicted_boarding_count.toFixed(1)}명
                </div>
                <div style={{ marginBottom: '2px' }}>
                  신뢰구간: {prediction.confidence_interval.lower.toFixed(1)} ~ {prediction.confidence_interval.upper.toFixed(1)}명
                </div>
                <div>
                  예측 시점: 다음 {prediction.prediction_horizon}시간
                </div>
              </div>
            </div>
          )}

          <div style={{ 
            fontSize: '10px', 
            color: '#999', 
            paddingTop: '4px',
            borderTop: '1px solid #f0f0f0'
          }}>
            <div>위도: {stop.latitude.toFixed(6)}</div>
            <div>경도: {stop.longitude.toFixed(6)}</div>
            {!stop.is_active && (
              <div style={{ color: '#ff4d4f', fontWeight: 'bold' }}>
                ⚠ 비활성 정류장
              </div>
            )}
          </div>

          <div style={{ 
            marginTop: '8px', 
            textAlign: 'center' 
          }}>
            <button
              onClick={() => onClick(stop.stop_id)}
              style={{
                background: '#1890ff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              상세 정보 보기
            </button>
          </div>
        </div>
      </Popup>
    </Marker>
  );
};