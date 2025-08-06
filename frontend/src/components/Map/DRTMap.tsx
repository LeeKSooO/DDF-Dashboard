import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { BusStop, HeatmapData } from '../../types';
import { HeatmapLayer } from './HeatmapLayer';
import { RoutesLayer } from './RoutesLayer';

// Leaflet 기본 아이콘 수정
delete (L.Icon.Default.prototype as L.Icon.Default & { _getIconUrl?: () => string })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

interface DRTMapProps {
  busStops: BusStop[];
  heatmapData: HeatmapData[];
  onStopClick: (stopId: string) => void;
  selectedStopId?: string;
  showRoutes?: boolean;
}

export const DRTMap: React.FC<DRTMapProps> = ({
  busStops,
  heatmapData,
  onStopClick,
  selectedStopId,
  showRoutes = false,
}) => {
  const mapRef = useRef<L.Map | null>(null);

  // 가평군 중심 좌표
  const gapyeongCenter: [number, number] = [37.7497, 127.3269];
  
  // 가평군 영역 bounds
  const gapyeongBounds: L.LatLngBoundsExpression = [
    [37.512117, 127.044667], // 남서쪽
    [37.986850, 127.607017], // 북동쪽
  ];

  useEffect(() => {
    if (mapRef.current && heatmapData.length > 0) {
      // 히트맵 데이터가 있는 영역으로 지도 뷰 조정
      const bounds = L.latLngBounds(
        heatmapData.map(point => [point.latitude, point.longitude])
      );
      mapRef.current.fitBounds(bounds, { padding: [20, 20] });
    }
  }, [heatmapData]);

  // DRT 확률에 따른 마커 색상 결정
  const getMarkerColor = (drtProbability: number, isTopStop: boolean): string => {
    if (!isTopStop) return '#cccccc'; // 회색 - 일반 정류장
    if (drtProbability >= 0.8) return '#ff0000'; // 빨간색 - 매우 높음
    if (drtProbability >= 0.6) return '#ff8000'; // 주황색 - 높음
    if (drtProbability >= 0.4) return '#ffff00'; // 노란색 - 보통
    return '#00ff00'; // 초록색 - 낮음
  };

  // 커스텀 마커 아이콘 생성
  const createCustomIcon = (color: string, isSelected: boolean = false) => {
    return L.divIcon({
      html: `<div style="
        background-color: ${color};
        width: ${isSelected ? '16px' : '12px'};
        height: ${isSelected ? '16px' : '12px'};
        border-radius: 50%;
        border: 2px solid ${isSelected ? '#000' : '#fff'};
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      "></div>`,
      className: 'custom-div-icon',
      iconSize: [isSelected ? 16 : 12, isSelected ? 16 : 12],
      iconAnchor: [isSelected ? 8 : 6, isSelected ? 8 : 6],
    });
  };

  return (
    <MapContainer
      center={gapyeongCenter}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      maxBounds={gapyeongBounds}
      maxBoundsViscosity={1.0}
      ref={mapRef}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      {/* 버스 노선 레이어 */}
      <RoutesLayer showRoutes={showRoutes} />
      
      {/* 히트맵 레이어 */}
      {heatmapData.length > 0 && (
        <HeatmapLayer data={heatmapData} />
      )}
      
      {/* 버스 정류장 마커들 */}
      {busStops.map((stop) => {
        const heatmapPoint = heatmapData.find(h => h.stop_id === stop.stop_id);
        const drtProbability = heatmapPoint?.intensity || 0;
        const isSelected = selectedStopId === stop.stop_id;
        const isTopStop = heatmapData.some(h => h.stop_id === stop.stop_id);
        
        // 모든 정류장 표시 (단, Top 10은 특별한 색상으로)
        
        return (
          <Marker
            key={stop.stop_id}
            position={[stop.latitude, stop.longitude]}
            icon={createCustomIcon(getMarkerColor(drtProbability, isTopStop), isSelected)}
            eventHandlers={{
              click: () => onStopClick(stop.stop_id),
            }}
          >
            <Popup>
              <div style={{ minWidth: '200px' }}>
                <h4 style={{ margin: '0 0 8px 0', color: '#1890ff' }}>
                  {stop.stop_name || stop.stop_id}
                </h4>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  <p style={{ margin: '4px 0' }}>
                    <strong>정류장 ID:</strong> {stop.stop_id}
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>지역:</strong> {stop.district}
                  </p>
                  {heatmapPoint && (
                    <p style={{ margin: '4px 0' }}>
                      <strong>DRT 확률:</strong> 
                      <span style={{ 
                        color: getMarkerColor(heatmapPoint.intensity, true),
                        fontWeight: 'bold'
                      }}>
                        {' '}{(heatmapPoint.intensity * 100).toFixed(1)}%
                      </span>
                    </p>
                  )}
                  <p style={{ margin: '4px 0', fontSize: '10px', color: '#999' }}>
                    위도: {stop.latitude.toFixed(6)}<br/>
                    경도: {stop.longitude.toFixed(6)}
                  </p>
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
};