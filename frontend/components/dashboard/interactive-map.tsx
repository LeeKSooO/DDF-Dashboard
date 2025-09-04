"use client";

import { useEffect, useState, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// 서울시 각 구의 중심 좌표
const DISTRICT_CENTERS: Record<string, [number, number]> = {
  "강남구": [37.5172, 127.0473],
  "강동구": [37.5301, 127.1238],
  "강북구": [37.6390, 127.0256],
  "강서구": [37.5509, 126.8495],
  "관악구": [37.4784, 126.9516],
  "광진구": [37.5384, 127.0822],
  "구로구": [37.4955, 126.8872],
  "금천구": [37.4565, 126.8956],
  "노원구": [37.6542, 127.0566],
  "도봉구": [37.6688, 127.0472],
  "동대문구": [37.5744, 127.0395],
  "동작구": [37.5124, 126.9393],
  "마포구": [37.5663, 126.9019],
  "서대문구": [37.5791, 126.9368],
  "서초구": [37.4837, 127.0324],
  "성동구": [37.5634, 127.0371],
  "성북구": [37.5894, 127.0167],
  "송파구": [37.5146, 127.1056],
  "양천구": [37.5168, 126.8665],
  "영등포구": [37.5264, 126.8962],
  "용산구": [37.5384, 126.9908],
  "은평구": [37.6026, 126.9292],
  "종로구": [37.5735, 126.9788],
  "중구": [37.5641, 126.9979],
  "중랑구": [37.6063, 127.0925],
};

// 서울시 전체 중심점
const SEOUL_CENTER: [number, number] = [37.5665, 126.9780];

// 서울시 경계 (대략적인 바운더리)
const SEOUL_BOUNDS = {
  north: 37.7,
  south: 37.4,
  east: 127.3,
  west: 126.7,
};

// 커스텀 마커 아이콘
const createCustomIcon = (rank: number, color: string, customSize?: number) => {
  const size = customSize || (40 - rank * 4);
  const fontSize = customSize ? 18 : (16 - rank);
  
  const iconHtml = `
    <div style="
      width: ${size}px; 
      height: ${size}px; 
      background: linear-gradient(135deg, ${color}, ${color}dd);
      border: 3px solid white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: ${fontSize}px;
      color: white;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      animation: bounce 2s infinite;
      z-index: ${customSize ? 1000 : 500};
      position: relative;
    ">
      ${rank + 1}
    </div>
  `;
  
  return L.divIcon({
    html: iconHtml,
    className: "custom-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
};

interface MapUpdaterProps {
  selectedRegion: string;
}

// 지도 업데이트 컴포넌트
function MapUpdater({ selectedRegion }: MapUpdaterProps) {
  const map = useMap();

  useEffect(() => {
    // 서울시 경계 제한 설정
    const bounds = L.latLngBounds(
      L.latLng(SEOUL_BOUNDS.south, SEOUL_BOUNDS.west),
      L.latLng(SEOUL_BOUNDS.north, SEOUL_BOUNDS.east)
    );
    
    if (selectedRegion === "전체") {
      // 전체 선택시 서울시 전체 뷰
      map.flyTo(SEOUL_CENTER, 11, {
        animate: true,
        duration: 1.5,
        easeLinearity: 0.25,
      });
      // 전체 선택시에는 줌 레벨을 10-13으로 제한
      map.setMaxZoom(13);
      map.setMinZoom(10);
    } else {
      // 구 선택시 해당 구로 확대
      const center = DISTRICT_CENTERS[selectedRegion];
      if (center) {
        map.flyTo(center, 14, {
          animate: true,
          duration: 1.5,
          easeLinearity: 0.25,
        });
        // 구 선택시에는 줌 레벨을 12-16으로 제한 (적당한 락)
        map.setMaxZoom(16);
        map.setMinZoom(12);
      }
    }
    
    // 서울시 경계 밖으로 나가지 못하도록 제한
    map.setMaxBounds(bounds);
    
  }, [selectedRegion, map]);

  return null;
}

interface InteractiveMapProps {
  selectedRegion: string;
  topStations: Array<{
    station_id: string;
    station_name: string;
    total_traffic: number;
    total_ride?: number;
    total_alight?: number;
  }>;
  highlightedStationId?: string;
  onStationClick?: (stationId: string) => void;
  openPopupStationId?: string;
  onPopupToggle?: (stationId: string | null) => void;
}

export function InteractiveMap({ selectedRegion, topStations, highlightedStationId, onStationClick, openPopupStationId, onPopupToggle }: InteractiveMapProps) {
  const [isClient, setIsClient] = useState(false);
  const markerRefs = useRef<{ [key: string]: L.Marker }>({});

  useEffect(() => {
    setIsClient(true);
  }, []);

  // 외부에서 팝업 제어
  useEffect(() => {
    if (openPopupStationId && markerRefs.current[openPopupStationId]) {
      markerRefs.current[openPopupStationId].openPopup();
    }
  }, [openPopupStationId]);


  if (!isClient) {
    return (
      <div className="w-full h-[700px] bg-gradient-to-br from-blue-50 to-green-50 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-600">지도 로딩 중...</p>
        </div>
      </div>
    );
  }

  // 마커 색상 배열
  const markerColors = [
    "#FF6B6B", // 1위 - 빨간색
    "#4ECDC4", // 2위 - 청록색  
    "#45B7D1", // 3위 - 파란색
    "#96CEB4", // 4위 - 초록색
    "#FECA57", // 5위 - 노란색
  ];

  return (
    <div className="w-full h-[700px] rounded-lg overflow-hidden shadow-lg">
      <style jsx global>{`
        @keyframes bounce {
          0%, 20%, 50%, 80%, 100% {
            transform: translateY(0);
          }
          40% {
            transform: translateY(-8px);
          }
          60% {
            transform: translateY(-4px);
          }
        }
        
        .custom-marker {
          background: none !important;
          border: none !important;
        }

        .leaflet-popup-content-wrapper {
          background: rgba(255, 255, 255, 0.95);
          backdrop-filter: blur(10px);
          border-radius: 12px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }

        .leaflet-popup-tip {
          background: rgba(255, 255, 255, 0.95);
          backdrop-filter: blur(10px);
        }
      `}</style>
      
      <MapContainer
        center={selectedRegion === "전체" ? SEOUL_CENTER : DISTRICT_CENTERS[selectedRegion] || SEOUL_CENTER}
        zoom={selectedRegion === "전체" ? 11 : 14}
        style={{ height: "100%", width: "100%" }}
        zoomControl={true}
        scrollWheelZoom={true}
        className="rounded-lg"
        maxZoom={selectedRegion === "전체" ? 13 : 16}
        minZoom={selectedRegion === "전체" ? 10 : 12}
        maxBounds={[
          [SEOUL_BOUNDS.south, SEOUL_BOUNDS.west],
          [SEOUL_BOUNDS.north, SEOUL_BOUNDS.east]
        ]}
        maxBoundsViscosity={1.0}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        
        <MapUpdater selectedRegion={selectedRegion} />
        
        {selectedRegion !== "전체" && topStations.map((station, index) => {
          // 구의 중심점 주변에 정류장들을 배치 (실제로는 좌표 데이터가 있어야 함)
          const districtCenter = DISTRICT_CENTERS[selectedRegion] || SEOUL_CENTER;
          
          // 임시로 구 중심점 주변에 랜덤하게 배치
          const positions = [
            [districtCenter[0] + 0.008, districtCenter[1] - 0.012],
            [districtCenter[0] - 0.006, districtCenter[1] + 0.010],
            [districtCenter[0] + 0.012, districtCenter[1] + 0.008],
            [districtCenter[0] - 0.010, districtCenter[1] - 0.008],
            [districtCenter[0] + 0.005, districtCenter[1] + 0.015],
          ];
          
          const position = positions[index] || districtCenter;
          const isHighlighted = highlightedStationId === station.station_id;
          const isPopupOpen = openPopupStationId === station.station_id;

          // 하이라이트된 마커는 더 큰 아이콘 사용
          const iconColor = isHighlighted ? "#FF1493" : markerColors[index]; // 하이라이트시 핫핑크
          const iconSize = isHighlighted ? 50 : 40 - index * 4;

          return (
            <Marker
              key={station.station_id}
              position={position as [number, number]}
              icon={createCustomIcon(index, iconColor, isHighlighted ? iconSize : undefined)}
              ref={(ref) => {
                if (ref) {
                  markerRefs.current[station.station_id] = ref;
                }
              }}
              eventHandlers={{
                click: () => {
                  onStationClick?.(station.station_id);
                }
              }}
            >
              <Popup 
                className="custom-popup"
                autoPan={true}
                closeOnEscapeKey={true}
                eventHandlers={{
                  popupopen: () => {
                    onPopupToggle?.(station.station_id);
                  },
                  popupclose: () => {
                    onPopupToggle?.(null);
                  }
                }}
              >
                <div className="p-3 min-w-[200px]">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">
                      {index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : `${index + 1}위`}
                    </span>
                    <h3 className="font-bold text-lg text-gray-800">
                      {station.station_name}
                    </h3>
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">일일 이용객:</span>
                      <span className="font-semibold text-blue-600">
                        {station.total_traffic.toLocaleString()}명
                      </span>
                    </div>
                    
                    {station.total_ride && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">승차:</span>
                        <span className="font-medium text-green-600">
                          {station.total_ride.toLocaleString()}명
                        </span>
                      </div>
                    )}
                    
                    {station.total_alight && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">하차:</span>
                        <span className="font-medium text-red-600">
                          {station.total_alight.toLocaleString()}명
                        </span>
                      </div>
                    )}
                  </div>
                  
                  <div className="mt-3 pt-2 border-t border-gray-200">
                    <div className="text-xs text-gray-500 text-center">
                      📍 {selectedRegion} #{index + 1} 인기 정류장
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}