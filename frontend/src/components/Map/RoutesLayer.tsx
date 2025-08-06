import React, { useEffect, useState } from 'react';
import { Polyline, Popup } from 'react-leaflet';
import { BusRoute } from '../../types';

interface RoutesLayerProps {
  showRoutes: boolean;
  routeFilter?: string[]; // 특정 노선만 표시하고 싶을 때
}

export const RoutesLayer: React.FC<RoutesLayerProps> = ({ 
  showRoutes, 
  routeFilter 
}) => {
  const [routes, setRoutes] = useState<BusRoute[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (showRoutes) {
      loadRoutes();
    }
  }, [showRoutes]);

  const loadRoutes = async () => {
    setLoading(true);
    try {
      const response = await fetch('/data/bus_routes.json');
      const geojson = await response.json();
      
      const routeData: BusRoute[] = geojson.features.map((feature: any) => ({
        route_id: feature.properties.route_id,
        route_no: feature.properties.route_no,
        route_type: feature.properties.route_type,
        start_node: feature.properties.start_node,
        end_node: feature.properties.end_node,
        stop_count: feature.properties.stop_count,
        color: feature.properties.color,
        coordinates: feature.geometry.coordinates.map((coord: number[]) => [coord[1], coord[0]]) // [lng, lat] -> [lat, lng]
      }));

      setRoutes(routeData);
    } catch (error) {
      console.error('노선 데이터 로딩 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!showRoutes || loading) {
    return null;
  }

  // 필터링된 노선만 표시
  const filteredRoutes = routeFilter 
    ? routes.filter(route => routeFilter.includes(route.route_no))
    : routes;

  return (
    <>
      {filteredRoutes.map((route) => (
        <Polyline
          key={route.route_id}
          positions={route.coordinates}
          pathOptions={{
            color: route.color,
            weight: 3,
            opacity: 0.7,
            dashArray: route.route_type.includes('직행') ? '10, 5' : undefined
          }}
        >
          <Popup>
            <div style={{ minWidth: '200px' }}>
              <h4 style={{ margin: '0 0 8px 0', color: route.color }}>
                {route.route_no}번 버스
              </h4>
              <div style={{ fontSize: '12px', color: '#666' }}>
                <p style={{ margin: '4px 0' }}>
                  <strong>노선 유형:</strong> {route.route_type}
                </p>
                <p style={{ margin: '4px 0' }}>
                  <strong>출발지:</strong> {route.start_node}
                </p>
                <p style={{ margin: '4px 0' }}>
                  <strong>도착지:</strong> {route.end_node}
                </p>
                <p style={{ margin: '4px 0' }}>
                  <strong>정류장 수:</strong> {route.stop_count}개
                </p>
              </div>
            </div>
          </Popup>
        </Polyline>
      ))}
    </>
  );
};