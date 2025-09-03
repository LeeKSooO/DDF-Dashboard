"use client";

import {
  useEffect,
  useRef,
  useState,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from "react";
import dynamic from "next/dynamic";
import { DistrictData, StationData } from "@/lib/api";

// Dynamically import Leaflet to avoid SSR issues
const L = typeof window !== "undefined" ? require("leaflet") : null;

// Fix for default markers in Leaflet - only on client side
if (typeof window !== "undefined" && L) {
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
    iconUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
    shadowUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  });
}

interface HeatmapSeoulMapProps {
  onDistrictClick?: (districtName: string, districtCode: string) => void;
  selectedDistrict?: string;
  districts: DistrictData[];
  viewMode: "district" | "station";
  loading?: boolean;
}

export interface HeatmapSeoulMapRef {
  resetToSeoulCenter: () => void;
}

const HeatmapSeoulMapComponent = forwardRef<
  HeatmapSeoulMapRef,
  HeatmapSeoulMapProps
>(
  (
    {
      onDistrictClick,
      selectedDistrict,
      districts = [],
      viewMode,
      loading = false,
    },
    ref
  ) => {
    const mapRef = useRef<HTMLDivElement>(null);
    const mapInstanceRef = useRef<any>(null);
    const stationMarkersRef = useRef<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isClient, setIsClient] = useState(false);

    // Seoul bounds for initial view and constraints
    const seoulBounds: [number, number] = [37.5665, 126.978];
    const seoulBoundingBox: [[number, number], [number, number]] = [
      [37.413, 126.734], // Southwest corner
      [37.715, 127.269], // Northeast corner
    ];

    // Check if we're on client side
    useEffect(() => {
      setIsClient(true);
    }, []);

    // Expose functions to parent component
    useImperativeHandle(
      ref,
      () => ({
        resetToSeoulCenter: () => {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.setView(seoulBounds, 11);
          }
        },
      }),
      []
    );

    // Convert district data to lookup map
    const districtLookup = useMemo(() => {
      const lookup: Record<string, DistrictData> = {};
      districts.forEach((district) => {
        lookup[district.district_name] = district;
      });
      return lookup;
    }, [districts]);

    // Traffic colors based on volume
    const getTrafficColor = (traffic: number): string => {
      if (traffic > 3000000) return "#DC2626"; // Red - Very High
      if (traffic > 2000000) return "#EA580C"; // Orange - High
      if (traffic > 1500000) return "#EAB308"; // Yellow - Medium-High
      if (traffic > 1000000) return "#16A34A"; // Green - Medium
      if (traffic > 500000) return "#2563EB"; // Blue - Low
      return "#6B7280"; // Gray - Very Low
    };

    // 구별 경계선 색상 배열 (25개 구를 위한 색상)
    const districtBorderColors = [
      "#DC2626", "#EA580C", "#F59E0B", "#EAB308", "#84CC16",
      "#22C55E", "#10B981", "#14B8A6", "#06B6D4", "#0EA5E9",
      "#3B82F6", "#6366F1", "#8B5CF6", "#A855F7", "#C026D3",
      "#E11D48", "#F43F5E", "#FB923C", "#FBBF24", "#A3E635",
      "#4ADE80", "#2DD4BF", "#22D3EE", "#60A5FA", "#818CF8"
    ];

    // 구 이름을 기반으로 일관된 색상 인덱스 생성
    const getDistrictColorIndex = (districtName: string): number => {
      let hash = 0;
      for (let i = 0; i < districtName.length; i++) {
        hash = districtName.charCodeAt(i) + ((hash << 5) - hash);
      }
      return Math.abs(hash) % districtBorderColors.length;
    };

    // Style function for districts - memoized to update when dependencies change
    const getFeatureStyle = useMemo(() => {
      return (feature: any) => {
        const districtName = feature.properties.sggnm;
        const districtData = districtLookup[districtName];
        const traffic = districtData?.total_traffic || 0;
        const isSelected = selectedDistrict === districtName;

        // 정류장별 모드일 때는 구별 경계선을 명확하게, 내부는 투명하게
        if (viewMode === "station") {
          const borderColor = districtBorderColors[getDistrictColorIndex(districtName)];
          return {
            fillColor: isSelected ? "#e0e7ff" : "#ffffff", // 선택된 구는 연한 파란색, 나머지는 흰색
            weight: isSelected ? 3 : 2,  // 경계선 두께 증가
            opacity: 1,  // 경계선 불투명도 최대
            color: isSelected ? "#1e40af" : borderColor,  // 선택된 구는 진한 파란색, 나머지는 각각 다른 색
            dashArray: "",
            fillOpacity: isSelected ? 0.15 : 0.05, // 내부는 매우 투명하게
          };
        }

        // 구별 모드일 때는 기존처럼 색상 표시
        return {
          fillColor: getTrafficColor(traffic),
          weight: isSelected ? 3 : 2,
          opacity: 1,
          color: isSelected ? "#2563EB" : "#ffffff",
          dashArray: "",
          fillOpacity: 0.3,
        };
      };
    }, [viewMode, selectedDistrict, districtLookup]);

    useEffect(() => {
      if (!isClient || !L || !mapRef.current || mapInstanceRef.current) {
        console.log("Map initialization skipped:", {
          isClient,
          hasL: !!L,
          hasMapRef: !!mapRef.current,
          hasMapInstance: !!mapInstanceRef.current,
        });
        return;
      }

      console.log("🗺️ Initializing heatmap map...");

      // Initialize map with CartoDB Positron style and Seoul bounds constraints
      const map = L.map(mapRef.current, {
        center: seoulBounds,
        zoom: 11,
        minZoom: 10, // 최소 줌 레벨 설정
        maxZoom: 16, // 최대 줌 레벨 설정
        maxBounds: seoulBoundingBox, // 서울시 경계로 이동 제한
        maxBoundsViscosity: 1.0, // 경계 제한 강도 (1.0 = 완전 제한)
        zoomControl: true,
        attributionControl: true,
      });

      // CartoDB Positron tiles
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: "abcd",
          maxZoom: 19,
        }
      ).addTo(map);

      mapInstanceRef.current = map;

      // Load GeoJSON data
      const loadGeoJSON = async () => {
        try {
          setIsLoading(true);
          setError(null);

          const response = await fetch("/seoul-districts-simple.geojson");
          if (!response.ok) {
            throw new Error(`Failed to load GeoJSON: ${response.status}`);
          }

          const geoJsonData = await response.json();

          // Add all district features to map
          const layer = L.geoJSON(geoJsonData, {
            style: getFeatureStyle,
            onEachFeature: (feature, layer) => {
              const districtName = feature.properties.sggnm;
              const districtData = districtLookup[districtName];

              // Mouse events - 클로저 문제 방지를 위해 함수 내부에서 처리
              layer.on({
                mouseover: function(e: any) {
                  const layer = e.target;
                  // getFeatureStyle이 현재 viewMode를 반영하므로 직접 사용
                  const baseStyle = getFeatureStyle(feature);
                  
                  if (baseStyle.fillOpacity < 0.2) { // station mode (fillOpacity가 낮음)
                    layer.setStyle({
                      ...baseStyle,
                      weight: 4,  // 호버시 경계선 더 두껍게
                      fillOpacity: 0.1,  // 내부는 약간만 진하게
                    });
                  } else { // district mode
                    layer.setStyle({
                      ...baseStyle,
                      weight: 3,
                      fillOpacity: 0.4,
                    });
                  }
                },
                mouseout: function(e: any) {
                  const layer = e.target;
                  layer.setStyle(getFeatureStyle(feature));
                },
                click: (e) => {
                  const districtName = feature.properties.sggnm;
                  const districtCode = feature.properties.sgg;

                  // Zoom to district with padding and animation
                  map.fitBounds(layer.getBounds(), {
                    padding: [50, 50], // 여백 추가
                    duration: 0.5, // 애니메이션 시간
                    maxZoom: 13, // 너무 많이 줌인되지 않도록 제한
                  });

                  // Call callback
                  if (onDistrictClick) {
                    onDistrictClick(districtName, districtCode);
                  }
                },
              });

              // Tooltip - will be updated when data changes
              layer.bindTooltip(
                `<div>
                <strong>${districtName}</strong><br/>
                교통량: 로딩 중...
              </div>`,
                {
                  permanent: false,
                  direction: "center",
                  className: "heatmap-tooltip",
                }
              );
            },
          }).addTo(map);

          setIsLoading(false);
        } catch (err) {
          console.error("Failed to load GeoJSON:", err);
          setError(
            err instanceof Error ? err.message : "Failed to load map data"
          );
          setIsLoading(false);
        }
      };

      loadGeoJSON();

      // Cleanup function
      return () => {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }
      };
    }, [isClient]);

    // Update styles and tooltips when district data changes
    useEffect(() => {
      if (!isClient || !L || !mapInstanceRef.current) return;

      console.log("🔄 Updating heatmap styles and tooltips");

      // Clear existing station markers
      stationMarkersRef.current.forEach((marker) => {
        if (mapInstanceRef.current && marker) {
          mapInstanceRef.current.removeLayer(marker);
        }
      });
      stationMarkersRef.current = [];

      mapInstanceRef.current.eachLayer((layer: any) => {
        if (layer instanceof L.GeoJSON) {
          layer.eachLayer((featureLayer: any) => {
            if (featureLayer instanceof L.Path) {
              const feature = featureLayer.feature;
              if (feature) {
                // Update style
                featureLayer.setStyle(getFeatureStyle(feature));

                // Re-bind mouse events to ensure they use current viewMode
                featureLayer.off('mouseover mouseout'); // Remove old handlers
                featureLayer.on({
                  mouseover: function(e: any) {
                    const layer = e.target;
                    const baseStyle = getFeatureStyle(feature);
                    
                    if (baseStyle.fillOpacity < 0.2) { // station mode
                      layer.setStyle({
                        ...baseStyle,
                        weight: 4,
                        fillOpacity: 0.1,
                      });
                    } else { // district mode
                      layer.setStyle({
                        ...baseStyle,
                        weight: 3,
                        fillOpacity: 0.4,
                      });
                    }
                  },
                  mouseout: function(e: any) {
                    const layer = e.target;
                    layer.setStyle(getFeatureStyle(feature));
                  }
                });

                // Update tooltip content
                const districtName = feature.properties.sggnm;
                const districtData = districtLookup[districtName];
                const traffic = districtData?.total_traffic || 0;
                const stationCount = districtData?.stations?.length || 0;
                const rideAlightRatio =
                  districtData?.total_ride && districtData?.total_alight
                    ? (
                        districtData.total_ride / districtData.total_alight
                      ).toFixed(2)
                    : "N/A";

                featureLayer.setTooltipContent(
                  `<div>
                  <strong>${districtName}</strong><br/>
                  교통량: ${traffic.toLocaleString()}명<br/>
                  정류장: ${stationCount}개<br/>
                  승하차비율: ${rideAlightRatio}
                </div>`
                );
              }
            }
          });
        }
      });

      // Add station markers if in station mode and stations available
      if (viewMode === "station" && districts.length > 0) {
        // Filter districts - if a district is selected, show only its stations
        const districtsToShow = selectedDistrict
          ? districts.filter((d) => d.district_name === selectedDistrict)
          : districts;

        districtsToShow.forEach((district) => {
          if (district.stations && district.stations.length > 0) {
            district.stations.forEach((station) => {
              // Check if coordinates exist and are valid
              const lat =
                station.coordinate?.lat || station.coordinate?.latitude;
              const lng =
                station.coordinate?.lng || station.coordinate?.longitude;

              if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                // Create custom icon based on traffic (adjust scale for Korean traffic data)
                const iconSize = Math.min(
                  Math.max(station.total_traffic / 50000, 4),
                  15
                );
                const icon = L.circleMarker([lat, lng], {
                  radius: iconSize,
                  fillColor: getTrafficColor(station.total_traffic),
                  color: "#ffffff",
                  weight: 2,
                  opacity: 1,
                  fillOpacity: 0.8,
                  zIndexOffset: 1000, // 정류장 마커를 항상 위에 표시
                });

                // Add station tooltip (hover)
                icon.bindTooltip(
                  `
                <div>
                  <strong>${station.station_name}</strong><br/>
                  구: ${district.district_name}<br/>
                  교통량: ${station.total_traffic.toLocaleString()}명
                </div>
              `,
                  {
                    permanent: false,
                    direction: "top",
                    offset: [0, -10],
                    className: "station-tooltip",
                  }
                );

                icon.addTo(mapInstanceRef.current);
                stationMarkersRef.current.push(icon);
              } else {
                console.warn(
                  "Invalid coordinates for station:",
                  station.station_name,
                  { lat, lng }
                );
              }
            });
          }
        });
      }
    }, [
      districtLookup,
      selectedDistrict,
      isClient,
      getFeatureStyle,
      viewMode,
      districts,
    ]);

    if (loading) {
      return (
        <div className="h-[800px] bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">데이터 로딩 중...</p>
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="h-[800px] bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center text-red-500">
            <p className="font-medium">지도 로딩 실패</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      );
    }

    // Don't render anything on server side
    if (!isClient) {
      return (
        <div className="h-[800px] bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">지도 로딩 중...</p>
          </div>
        </div>
      );
    }

    return (
      <div className="relative">
        <div
          ref={mapRef}
          className="h-[800px] rounded-lg border"
          style={{ zIndex: 1 }}
        />

        {isLoading && (
          <div className="absolute inset-0 bg-gray-100 rounded-lg flex items-center justify-center z-10">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
              <p className="text-gray-600">지도 로딩 중...</p>
            </div>
          </div>
        )}

        {/* Enhanced Legend for Heatmap */}
        <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg text-xs z-20">
          <div className="font-medium mb-2">교통량 히트맵 범례</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#DC2626] rounded-sm"></div>
              <span>300만명 이상</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#EA580C] rounded-sm"></div>
              <span>200-300만명</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#EAB308] rounded-sm"></div>
              <span>150-200만명</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#16A34A] rounded-sm"></div>
              <span>100-150만명</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#2563EB] rounded-sm"></div>
              <span>50-100만명</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-3 bg-[#6B7280] rounded-sm"></div>
              <span>50만명 미만</span>
            </div>
          </div>
        </div>

        {/* View mode indicator */}
        <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-2 shadow-sm z-20">
          <div className="text-xs font-medium">
            {viewMode === "district" ? "📍 구별 히트맵" : "🎯 정류장별 히트맵"}
          </div>
        </div>
      </div>
    );
  }
);

// Export as dynamic component to prevent SSR issues
export const HeatmapSeoulMap = dynamic(
  () => Promise.resolve(HeatmapSeoulMapComponent),
  {
    ssr: false,
    loading: () => (
      <div className="h-[800px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-600">지도 로딩 중...</p>
        </div>
      </div>
    ),
  }
);
