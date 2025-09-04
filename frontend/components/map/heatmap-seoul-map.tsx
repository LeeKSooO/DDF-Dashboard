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
import { DistrictData } from "@/lib/api";

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
  highlightTopStations?: boolean; // TOP 5 정류장 강조 옵션
  selectedPattern?: string | null; // 선택된 이상 패턴
  patternStations?: any[]; // 패턴별 정류장 데이터
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
      highlightTopStations = false,
      selectedPattern = null,
      patternStations = [],
    },
    ref
  ) => {
    const mapRef = useRef<HTMLDivElement>(null);
    const mapInstanceRef = useRef<any>(null);
    const stationMarkersRef = useRef<Map<string, any>>(new Map()); // 마커를 Map으로 관리 (station_id -> marker)
    
    // 애니메이션 관리 시스템
    const animationManagerRef = useRef<Map<string, number>>(new Map()); // 애니메이션 ID 관리
    
    // 애니메이션 유틸리티 함수들
    const stopAnimation = (stationId: string) => {
      const animationId = animationManagerRef.current.get(stationId);
      if (animationId) {
        cancelAnimationFrame(animationId);
        animationManagerRef.current.delete(stationId);
      }
    };
    
    const stopAllAnimations = () => {
      console.log('🛑 모든 애니메이션 중지 시작 - 현재 활성:', animationManagerRef.current.size, '개');
      animationManagerRef.current.forEach((animationId, stationId) => {
        console.log('🛑 애니메이션 중지:', stationId, animationId);
        cancelAnimationFrame(animationId);
      });
      animationManagerRef.current.clear();
      console.log('✅ 모든 애니메이션 중지 완료');
    };
    
    
    const startPatternAnimation = (stationId: string, marker: any, baseRadius: number) => {
      console.log('🎯 패턴 애니메이션 시작:', stationId, 'baseRadius:', baseRadius);
      
      // 기존 애니메이션이 있다면 먼저 정리
      stopAnimation(stationId);
      
      let growing = true;
      let currentRadius = baseRadius;
      
      const animate = () => {
        if (growing) {
          currentRadius += 0.1;
          if (currentRadius >= baseRadius * 1.15) {
            growing = false;
          }
        } else {
          currentRadius -= 0.1;
          if (currentRadius <= baseRadius * 0.95) {
            growing = true;
          }
        }
        
        if (marker && mapInstanceRef.current?.hasLayer(marker)) {
          marker.setStyle({ radius: currentRadius });
          const animationId = requestAnimationFrame(animate);
          animationManagerRef.current.set(stationId, animationId);
        } else {
          console.log('⚠️ 마커가 지도에서 제거됨, 애니메이션 중지:', stationId);
        }
      };
      
      // 애니메이션 시작
      setTimeout(() => {
        if (marker && mapInstanceRef.current?.hasLayer(marker)) {
          const animationId = requestAnimationFrame(animate);
          animationManagerRef.current.set(stationId, animationId);
          console.log('✅ 애니메이션 시작됨:', stationId, 'ID:', animationId);
        } else {
          console.log('⚠️ 마커가 없어서 애니메이션 시작 안됨:', stationId);
        }
      }, 100);
    };
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

    // TOP 5 정류장 계산
    const topStations = useMemo(() => {
      return districts
        .flatMap(d => d.stations || [])
        .sort((a, b) => b.total_traffic - a.total_traffic)
        .slice(0, 5)
        .map(station => station.station_id);
    }, [districts]);

    // TOP 5 정류장 여부 확인 함수
    const isTopStation = (stationId: string): boolean => {
      return highlightTopStations && topStations.includes(stationId);
    };

    // 패턴 정류장 여부 확인 함수
    const getPatternStation = (stationId: string) => {
      if (!selectedPattern || !patternStations.length) return null;
      return patternStations.find(station => station.station_id === stationId);
    };

    // 줌인 기능 제거 - 단순 표시만

    // District-level traffic colors (구별) - 150만-900만 범위로 세밀하게 조정
    const getDistrictTrafficColor = (traffic: number): string => {
      if (traffic > 9000000) return "#DC2626"; // Red - Very High (900만명 초과)
      if (traffic > 7500000) return "#EA580C"; // Orange-Red - High (750-900만명)
      if (traffic > 6000000) return "#F59E0B"; // Orange - Medium-High (600-750만명)
      if (traffic > 4500000) return "#EAB308"; // Yellow - Medium (450-600만명)
      if (traffic > 3000000) return "#16A34A"; // Green - Medium-Low (300-450만명)
      if (traffic > 1500000) return "#2563EB"; // Blue - Low (150-300만명)
      return "#6B7280"; // Gray - Very Low (150만명 미만)
    };

    // Station-level traffic colors (정류장별) - 10명-5만명 범위로 조정
    const getStationTrafficColor = (traffic: number): string => {
      if (traffic > 40000) return "#DC2626"; // Red - Very High (4만명 이상)
      if (traffic > 30000) return "#EA580C"; // Orange-Red - High (3-4만명)
      if (traffic > 20000) return "#F59E0B"; // Orange - Medium-High (2-3만명)
      if (traffic > 10000) return "#EAB308"; // Yellow - Medium (1만-2만명)
      if (traffic > 5000) return "#16A34A"; // Green - Medium-Low (5천-1만명)
      if (traffic > 1000) return "#2563EB"; // Blue - Low (1천-5천명)
      return "#6B7280"; // Gray - Very Low (1천명 미만)
    };


    // TOP 5 정류장 전용 색상 (금색 그라데이션)
    const getTopStationColor = (rank: number): string => {
      const colors = [
        "#FFD700", // Gold - 1위
        "#FFA500", // Orange Gold - 2위
        "#FF8C00", // Dark Orange - 3위
        "#FF6347", // Tomato - 4위
        "#FF4500", // Orange Red - 5위
      ];
      return colors[rank] || "#FFD700";
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
          fillColor: getDistrictTrafficColor(traffic),
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
          L.geoJSON(geoJsonData, {
            style: getFeatureStyle,
            onEachFeature: (feature: any, layer: any) => {
              const districtName = feature.properties.sggnm;

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
                click: (_e: any) => {
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

      // Update existing station markers instead of removing them
      const existingMarkers = stationMarkersRef.current;

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

      // 뷰모드가 district로 변경되면 모든 정류장 마커들 제거 (애니메이션 포함)
      if (viewMode === "district") {
        // 모든 애니메이션 먼저 정리
        stopAllAnimations();
        
        // 모든 정류장 마커들을 지도에서 제거
        existingMarkers.forEach((marker) => {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.removeLayer(marker);
          }
        });
        existingMarkers.clear();
        console.log('🗑️ District mode: 모든 정류장 마커 및 애니메이션 제거 완료');
      }
      
      // Add station markers if in station mode and stations available
      else if (viewMode === "station" && districts.length > 0) {
        // 패턴이 변경될 때마다 모든 마커를 완전히 제거하고 다시 생성
        console.log('🔄 패턴 변경 감지 - 모든 마커 제거 후 재생성');
        stopAllAnimations();
        
        // 모든 정류장 마커들을 지도에서 완전히 제거
        existingMarkers.forEach((marker) => {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.removeLayer(marker);
          }
        });
        existingMarkers.clear();
        console.log('🗑️ 모든 기존 마커 제거 완료 - 깨끗한 상태로 시작');
        // Filter districts - if a district is selected, show only its stations
        const districtsToShow = selectedDistrict
          ? districts.filter((d) => d.district_name === selectedDistrict)
          : districts;

        // 더 이상 다른 구 마커 제거 로직 불필요 - 모든 마커를 새로 만들기 때문

        districtsToShow.forEach((district) => {
          if (district.stations && district.stations.length > 0) {
            district.stations.forEach((station) => {
              // Check if coordinates exist and are valid
              const lat = (station.coordinate as any)?.lat || station.coordinate?.latitude;
              const lng = (station.coordinate as any)?.lng || station.coordinate?.longitude;

              if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                // 모든 마커를 새로 생성 (기존 마커 체크 없이)
                
                // 정류장 우선순위 확인
                const topStationRank = topStations.indexOf(station.station_id);
                const isTop = isTopStation(station.station_id);
                const patternStation = getPatternStation(station.station_id);
                
                // Create custom icon based on traffic (확대시 더 잘 보이도록 크기 증가)
                let iconSize = Math.min(
                  Math.max(station.total_traffic / 25000, 6), // 최소 크기 4->6, 나누는 값 50000->25000으로 조정
                  20 // 최대 크기 15->20으로 증가
                );
                
                // 우선순위별 크기 조정
                if (patternStation) {
                  iconSize = Math.max(iconSize * 2.2, 20); // 패턴 정류장 가장 크게 (16->20)
                } else if (isTop) {
                  iconSize = Math.max(iconSize * 1.8, 16); // TOP 5 정류장 (12->16)
                }
                
                // 우선순위별 색상 및 스타일 결정 (파스텔/반투명 스타일)
                let fillColor, borderColor, borderWeight, fillOpacity;
                
                if (patternStation) {
                  // 패턴 정류장 - 부드러운 파스텔 톤으로 강조
                  fillColor = patternStation.patternColor;
                  borderColor = patternStation.patternColor;
                  borderWeight = 2;
                  fillOpacity = 0.6; // 반투명
                } else if (isTop) {
                  // TOP 5 정류장 - 부드러운 골드 파스텔
                  fillColor = getTopStationColor(topStationRank);
                  borderColor = getTopStationColor(topStationRank);
                  borderWeight = 2;
                  fillOpacity = 0.7; // 약간 더 진하게
                } else {
                  // 일반 정류장 - 매우 부드러운 톤
                  fillColor = getStationTrafficColor(station.total_traffic);
                  borderColor = fillColor;
                  borderWeight = 1;
                  fillOpacity = 0.5; // 반투명
                }

                // 모든 마커를 새로 생성 (깨끗한 상태에서 시작)
                const icon = L.circleMarker([lat, lng], {
                  radius: iconSize,
                  fillColor: fillColor,
                  color: borderColor,
                  weight: borderWeight,
                  opacity: 0.8, // 부드러운 경계선
                  fillOpacity: fillOpacity,
                });
                icon.addTo(mapInstanceRef.current);
                existingMarkers.set(station.station_id, icon);
                
                // z-order 설정
                if (patternStation) {
                  icon.bringToFront();
                } else if (isTop) {
                  icon.bringToFront();
                }
                
                // 패턴 마커에만 두근두근 애니메이션 시작
                if (patternStation) {
                  startPatternAnimation(station.station_id, icon, iconSize);
                }

                // 애니메이션은 CSS로 처리

                // Add station tooltip (hover) - 우선순위별 툴팁
                let tooltipContent, tooltipClass, tooltipOffset;
                
                if (patternStation) {
                  // 패턴 정류장 툴팁
                  const patternNames = {
                    'weekend': '주말 우세',
                    'night': '심야 고수요', 
                    'underutilized': '저활용 정류장',
                    'lunchtime': '점심시간 특화',
                    'rushhour': '러시아워 핫스팟',
                    'areatype': '지역 특성'
                  };
                  
                  tooltipContent = `
                    <div style="background: linear-gradient(135deg, ${patternStation.patternColor}20, ${patternStation.patternColor}40); border: 3px solid ${patternStation.patternColor}; border-radius: 8px; padding: 8px;">
                      <div style="color: #000; font-weight: bold; font-size: 16px; margin-bottom: 4px;">
                        🎯 ${patternNames[patternStation.patternType as keyof typeof patternNames]} 
                      </div>
                      <strong style="font-size: 15px;">${station.station_name}</strong><br/>
                      <span style="color: #555;">구: ${district.district_name}</span><br/>
                      <span style="color: #555;">기본 교통량: ${station.total_traffic.toLocaleString()}명</span><br/>
                      <div style="margin-top: 6px; padding: 4px; background: #f0f0f0; border-radius: 4px; font-size: 13px;">
                        ${patternStation.patternInfo}
                      </div>
                      <div style="color: #666; font-size: 11px; margin-top: 4px; font-style: italic;">패턴 분석 결과</div>
                    </div>
                  `;
                  tooltipClass = "pattern-station-tooltip";
                  tooltipOffset = -20;
                } else if (isTop) {
                  // TOP 5 정류장 툴팁
                  tooltipContent = `
                    <div style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; font-weight: bold; border: 2px solid #FF8C00;">
                      <div style="color: #8B0000; font-weight: bold; font-size: 14px;">⭐ TOP ${topStationRank + 1} 정류장 ⭐</div>
                      <strong>${station.station_name}</strong><br/>
                      구: ${district.district_name}<br/>
                      교통량: ${station.total_traffic.toLocaleString()}명
                      <div style="color: #8B0000; font-size: 12px; margin-top: 4px;">클릭하여 상세정보 확인</div>
                    </div>
                  `;
                  tooltipClass = "top-station-tooltip";
                  tooltipOffset = -15;
                } else {
                  // 일반 정류장 툴팁
                  tooltipContent = `
                    <div>
                      <strong>${station.station_name}</strong><br/>
                      구: ${district.district_name}<br/>
                      교통량: ${station.total_traffic.toLocaleString()}명
                    </div>
                  `;
                  tooltipClass = "station-tooltip";
                  tooltipOffset = -10;
                }
                
                // 툴팁 업데이트 (기존 마커든 새 마커든 동일하게)
                icon.bindTooltip(tooltipContent, {
                  permanent: false,
                  direction: "top",
                  offset: [0, tooltipOffset],
                  className: tooltipClass,
                });
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
      highlightTopStations,
      topStations,
      selectedPattern, // 패턴 변경 시 마커 업데이트
      patternStations, // 패턴 정류장 데이터 변경 시 마커 업데이트
    ]);

    // 줌인 애니메이션 제거

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
            <p className="text-base">{error}</p>
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
        <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg text-base z-20">
          <div className="font-medium mb-2">
            {viewMode === "district" ? "구별 교통량 범례" : "정류장별 교통량 범례"}
          </div>
          
          {/* 패턴 범례 (패턴 선택시) */}
          {selectedPattern && patternStations.length > 0 && (
            <div className="mb-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded border-2 border-blue-200">
              <div className="font-medium text-blue-800 mb-2 flex items-center gap-2">
                🎯 이상 패턴 분석
              </div>
              <div className="space-y-2">
                {selectedPattern === 'weekend' && (
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-blue-500 border-2 border-black"></div>
                    <span className="text-blue-700">주말 우세 정류장 ({patternStations.length}곳)</span>
                  </div>
                )}
                {selectedPattern === 'night' && (
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-purple-500 border-2 border-black"></div>
                    <span className="text-purple-700">심야 고수요 정류장 ({patternStations.length}곳)</span>
                  </div>
                )}
                {selectedPattern === 'underutilized' && (
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-red-500 border-2 border-black"></div>
                    <span className="text-red-700">저활용 정류장 ({patternStations.length}곳)</span>
                  </div>
                )}
                {selectedPattern === 'lunchtime' && (
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-green-500 border-2 border-black"></div>
                    <span className="text-green-700">점심시간 특화 정류장 ({patternStations.length}곳)</span>
                  </div>
                )}
                {selectedPattern === 'rushhour' && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#FF6B35' }}></div>
                      <span className="text-orange-700 text-sm">🌅 오전 러시아워 (07-09시)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#DC2626' }}></div>
                      <span className="text-red-700 text-sm">🌆 오후 러시아워 (17-19시)</span>
                    </div>
                    <div className="text-xs text-gray-600 mt-1">총 {patternStations.length}곳</div>
                  </div>
                )}
                {selectedPattern === 'areatype' && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-sky-500 border border-black"></div>
                      <span className="text-sky-700 text-sm">주거지역</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-purple-500 border border-black"></div>
                      <span className="text-purple-700 text-sm">업무지역</span>
                    </div>
                  </div>
                )}
                <div className="text-xs text-gray-600 mt-2">패턴별 색상으로 강조 표시</div>
              </div>
            </div>
          )}
          
          {/* TOP 5 정류장 범례 (강조 모드일 때만) */}
          {highlightTopStations && viewMode === "station" && !selectedPattern && (
            <div className="mb-3 p-2 bg-gradient-to-r from-yellow-100 to-orange-100 rounded border">
              <div className="font-medium text-orange-800 mb-1">⭐ TOP 5 정류장</div>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-4 h-4 rounded-full bg-gradient-to-r from-yellow-400 to-orange-500 border-2 border-black"></div>
                <span className="text-orange-700">특별 강조 표시</span>
              </div>
            </div>
          )}
          
          {/* 구별 모드 범례 */}
          {viewMode === "district" && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#DC2626] rounded-sm"></div>
                <span>900만명 초과</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#EA580C] rounded-sm"></div>
                <span>750-900만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#F59E0B] rounded-sm"></div>
                <span>600-750만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#EAB308] rounded-sm"></div>
                <span>450-600만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#16A34A] rounded-sm"></div>
                <span>300-450만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#2563EB] rounded-sm"></div>
                <span>150-300만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#6B7280] rounded-sm"></div>
                <span>150만명 미만</span>
              </div>
            </div>
          )}

          {/* 정류장별 모드 범례 */}
          {viewMode === "station" && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#DC2626] rounded-sm"></div>
                <span>4만명 이상</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#EA580C] rounded-sm"></div>
                <span>3-4만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#F59E0B] rounded-sm"></div>
                <span>2-3만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#EAB308] rounded-sm"></div>
                <span>1만-2만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#16A34A] rounded-sm"></div>
                <span>5천-1만명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#2563EB] rounded-sm"></div>
                <span>1천-5천명</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-3 bg-[#6B7280] rounded-sm"></div>
                <span>1천명 미만</span>
              </div>
            </div>
          )}
        </div>

        {/* View mode indicator */}
        <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-2 shadow-sm z-20">
          <div className="text-base font-medium">
            {viewMode === "district" ? "📍 구별 히트맵" : "🎯 정류장별 히트맵"}
          </div>
          
          {/* 패턴 활성화 표시 */}
          {selectedPattern && patternStations.length > 0 && (
            <div className="text-sm mt-2 p-2 bg-blue-50 rounded border">
              <div className="font-medium text-blue-800 flex items-center gap-1">
                🎯 이상패턴 분석 중
              </div>
              <div className="text-blue-600 mt-1">
                {selectedPattern === 'weekend' && '주말 우세 정류장'}
                {selectedPattern === 'night' && '심야 고수요 정류장'}
                {selectedPattern === 'underutilized' && '저활용 정류장'}
                {selectedPattern === 'lunchtime' && '점심시간 특화 정류장'}
                {selectedPattern === 'rushhour' && '러시아워 핫스팟'}
                {selectedPattern === 'areatype' && '지역 특성 분석'}
              </div>
            </div>
          )}
          
          {/* TOP 5 강조 표시 */}
          {highlightTopStations && viewMode === "station" && !selectedPattern && (
            <div className="text-sm text-orange-600 mt-1 font-medium">
              ⭐ TOP 5 강조 모드
            </div>
          )}
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
