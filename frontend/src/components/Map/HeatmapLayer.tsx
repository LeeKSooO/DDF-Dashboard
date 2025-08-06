import React, { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';
import { HeatmapData } from '../../types';

interface HeatmapLayerProps {
  data: HeatmapData[];
  options?: {
    radius?: number;
    blur?: number;
    maxZoom?: number;
    max?: number;
    minOpacity?: number;
    gradient?: { [key: number]: string };
  };
}

export const HeatmapLayer: React.FC<HeatmapLayerProps> = ({ 
  data, 
  options = {} 
}) => {
  const map = useMap();

  useEffect(() => {
    if (!data || data.length === 0) return;

    // 히트맵 데이터 포인트 준비
    const heatPoints: [number, number, number][] = data.map(point => [
      point.latitude,
      point.longitude,
      point.intensity, // DRT 확률 (0-1)
    ]);

    // 히트맵 옵션 설정
    const heatmapOptions = {
      radius: options.radius || 25,
      blur: options.blur || 15,
      maxZoom: options.maxZoom || 17,
      max: options.max || 1.0,
      minOpacity: options.minOpacity || 0.4,
      gradient: options.gradient || {
        0.0: '#00ff00',  // 초록색 - 낮은 확률
        0.4: '#ffff00',  // 노란색 - 보통 확률
        0.6: '#ff8000',  // 주황색 - 높은 확률
        0.8: '#ff0000',  // 빨간색 - 매우 높은 확률
        1.0: '#800080',  // 보라색 - 최고 확률
      },
    };

    // 히트맵 레이어 생성
    const heatLayer = (L as typeof L & { heatLayer: (points: [number, number, number][], options: Record<string, unknown>) => L.Layer }).heatLayer(heatPoints, heatmapOptions);
    
    // 지도에 히트맵 레이어 추가
    heatLayer.addTo(map);

    // 컴포넌트 언마운트 시 레이어 제거
    return () => {
      map.removeLayer(heatLayer);
    };
  }, [map, data, options]);

  return null; // 이 컴포넌트는 시각적 렌더링을 하지 않음
};