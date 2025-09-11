"use client";

import { useState, useEffect, useMemo } from "react";
import DeckGL from '@deck.gl/react';
import { ArcLayer, ScatterplotLayer, GeoJsonLayer, BitmapLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { MapPin } from "lucide-react";
import { ensureFeatureCollection } from "@/lib/geojson-utils";

// TypeScript interfaces - 새로운 API 구조에 맞게 수정
interface Station {
  id: string;
  name: string;
  lat: number;
  lng: number;
  totalVolume?: number;
  station_num?: string;
  district?: string;
}

interface ODPair {
  from_station_id: string;
  from_station_name: string;
  from_station_num: string;
  to_station_id: string;
  to_station_name: string;
  to_station_num: string;
  from_district: string;
  to_district: string;
  distance_km: number;
}

interface ODData {
  od_pair: ODPair;
  daily_demand: number;
  transfer_required: boolean;
  priority_category: string;
  // 시각화를 위한 추가 필드
  origin?: Station;
  destination?: Station;
}

interface ODAnalysisContentProps {
  selectedMonth?: string;
  selectedRegion?: string;
}

// 우선순위 카테고리별 색상 매핑 함수
const getColorByPriority = (category: string): [number, number, number, number] => {
  if (category.includes('P1_고수요_환승구간')) return [220, 38, 38, 220];    // 빨간색 - 긴급
  if (category.includes('P1_저수요_환승구간')) return [249, 115, 22, 200];   // 주황색 - 중요
  if (category.includes('P2')) return [59, 130, 246, 180];                 // 파란색 - 개선 필요
  if (category.includes('P3')) return [147, 51, 234, 160];                 // 보라색 - 통합 검토
  return [156, 163, 175, 140];                                             // 회색 - 기본
};

// 우선순위별 표시 텍스트
const getPriorityLabel = (category: string): string => {
  if (category.includes('P1_고수요_환승구간')) return '🚨 P1 고수요 환승';
  if (category.includes('P1_저수요_환승구간')) return '⚠️ P1 저수요 환승';
  if (category.includes('P2')) return '🔄 P2 직행부족';
  if (category.includes('P3')) return '📏 P3 장거리';
  return '기타';
};

// 정류장 이름으로 좌표를 매핑하는 함수 (실제로는 API에서 받아와야 함)
const getStationCoordinates = (stationName: string): { lat: number; lng: number } => {
  const stationCoords: { [key: string]: { lat: number; lng: number } } = {
    "대방역": { lat: 37.5136, lng: 126.9267 },
    "국회의사당역.KB국민은행": { lat: 37.5292, lng: 126.9171 },
    "경복궁.국립민속박물관": { lat: 37.5796, lng: 126.9770 },
    "안국역6번출구.인사동문화의거리": { lat: 37.5759, lng: 126.9852 },
    "남산서울타워": { lat: 37.5512, lng: 126.9882 },
    "광화문역2번출구.KT광화문지사": { lat: 37.5709, lng: 126.9768 },
    "남대문세무서": { lat: 37.5582, lng: 126.9783 },
    "춘추문": { lat: 37.5808, lng: 126.9742 },
    "미아사거리역": { lat: 37.6129, lng: 127.0257 },
    "정릉길음시장.길음뉴타운9단지": { lat: 37.6059, lng: 127.0264 },
    "강남역": { lat: 37.4979, lng: 127.0276 },
    "역삼역": { lat: 37.5006, lng: 127.0365 },
    "수서역": { lat: 37.4875, lng: 127.1008 },
    "명동역": { lat: 37.5638, lng: 126.9822 }
  };
  
  return stationCoords[stationName] || { lat: 37.5665, lng: 126.9780 }; // 기본값: 서울 중심
};

export const ODAnalysisContent = ({ selectedMonth = "7", selectedRegion = "전체" }: ODAnalysisContentProps) => {
  const [selectedStation, setSelectedStation] = useState<string | null>(null);
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);
  const [odData, setOdData] = useState<ODData[]>([]);
  const [stationData, setStationData] = useState<Station[]>([]);
  const [seoulCtprvnGeoJson, setSeoulCtprvnGeoJson] = useState<any>(null); // 시도 (서울특별시)
  const [seoulSigGeoJson, setSeoulSigGeoJson] = useState<any>(null);       // 구 (25개)
  const [seoulEmdGeoJson, setSeoulEmdGeoJson] = useState<any>(null);       // 동 (467개)
  const [loading, setLoading] = useState(true);
  const [viewState, setViewState] = useState({
    longitude: 127.0276,
    latitude: 37.4979,
    zoom: 11,
    pitch: 45,
    bearing: 0,
  });

  // 필터 상태 - 새로운 우선순위 체계
  const [filters, setFilters] = useState({
    showP1High: true,     // P1 고수요 환승구간
    showP1Low: true,      // P1 저수요 환승구간
    showP2: false,        // P2 직행부족
    showP3: false,        // P3 장거리
    selectedPriority: 'P1' as 'P1' | 'P2' | 'P3' | 'ALL',
    flowDirection: 'both' as 'outbound' | 'inbound' | 'both',
    showMapBackground: true,
    showDistrictBoundaries: false,  // 구 경계
    showDetailedBoundaries: false   // 동 경계
  });

  // 데이터 로드 (임시 더미 데이터 + GeoJSON)
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // 3단계 행정구역 GeoJSON 데이터 로드 (한글 인코딩 수정된 버전)
        const loadPromises = [
          // 1. 시도 (서울특별시)
          fetch('/reference/seoul_ctprvn_fixed.json').then(r => r.json()).then(data => {
            setSeoulCtprvnGeoJson(ensureFeatureCollection(data));
            console.log(`✅ Seoul CTPRVN data loaded: ${data.features?.length || 0} features`);
          }).catch(e => console.warn('시도 지도 로드 실패:', e)),
          
          // 2. 구 (25개 구)
          fetch('/reference/seoul_sig_fixed.json').then(r => r.json()).then(data => {
            setSeoulSigGeoJson(ensureFeatureCollection(data));
            console.log(`✅ Seoul SIG data loaded: ${data.features?.length || 0} features`);
          }).catch(e => console.warn('구 단위 지도 로드 실패:', e)),
          
          // 3. 동 (467개 동)
          fetch('/reference/seoul_emd_fixed.json').then(r => r.json()).then(data => {
            setSeoulEmdGeoJson(ensureFeatureCollection(data));
            console.log(`✅ Seoul EMD data loaded: ${data.features?.length || 0} features`);
          }).catch(e => console.warn('동 단위 지도 로드 실패:', e))
        ];
        
        // 모든 지도 데이터 로드를 병렬로 실행
        await Promise.allSettled(loadPromises);
        
        // 실제 API 호출로 교체 가능
        // const loadODPriorityData = async (priority: 'P1' | 'P2' | 'P3') => {
        //   try {
        //     const response = await fetch(`http://localhost:8000/api/v1/od/priority/${priority.toLowerCase()}?analysis_month=2025-07-01&top_n=20`);
        //     const data = await response.json();
        //     return data as ODData[];
        //   } catch (error) {
        //     console.warn(`Failed to load ${priority} data:`, error);
        //     return [];
        //   }
        // };

        // 모든 우선순위 데이터를 병렬로 로드
        // const [p1Data, p2Data, p3Data] = await Promise.all([
        //   loadODPriorityData('P1'),
        //   loadODPriorityData('P2'), 
        //   loadODPriorityData('P3')
        // ]);
        // const allODData = [...p1Data, ...p2Data, ...p3Data];
        
        // 새로운 API 구조에 맞는 더미 데이터 (팀장님이 제공한 실제 데이터 기반)
        const dummyODData: ODData[] = [
          {
            od_pair: {
              from_station_id: "118000215",
              from_station_name: "대방역",
              from_station_num: "19306.0",
              to_station_id: "118000047",
              to_station_name: "국회의사당역.KB국민은행",
              to_station_num: "19132.0",
              from_district: "영등포구",
              to_district: "영등포구",
              distance_km: 1.8
            },
            daily_demand: 158,
            transfer_required: true,
            priority_category: "P1_고수요_환승구간"
          },
          {
            od_pair: {
              from_station_id: "100000418",
              from_station_name: "경복궁.국립민속박물관",
              from_station_num: "1603.0",
              to_station_id: "100000104",
              to_station_name: "안국역6번출구.인사동문화의거리",
              to_station_num: "1200.0",
              from_district: "종로구",
              to_district: "종로구",
              distance_km: 0.57
            },
            daily_demand: 141,
            transfer_required: true,
            priority_category: "P1_고수요_환승구간"
          },
          {
            od_pair: {
              from_station_id: "102000226",
              from_station_name: "남산서울타워",
              from_station_num: "3320.0",
              to_station_id: "100000023",
              to_station_name: "광화문역2번출구.KT광화문지사",
              to_station_num: "1118.0",
              from_district: "중구",
              to_district: "종로구",
              distance_km: 2.66
            },
            daily_demand: 138,
            transfer_required: true,
            priority_category: "P1_고수요_환승구간"
          },
          {
            od_pair: {
              from_station_id: "100000418",
              from_station_name: "경복궁.국립민속박물관",
              from_station_num: "1603.0",
              to_station_id: "101000001",
              to_station_name: "남대문세무서",
              to_station_num: "2001.0",
              from_district: "종로구",
              to_district: "중구",
              distance_km: 1.75
            },
            daily_demand: 96,
            transfer_required: true,
            priority_category: "P1_저수요_환승구간"
          },
          {
            od_pair: {
              from_station_id: "100000023",
              from_station_name: "광화문역2번출구.KT광화문지사",
              from_station_num: "1118.0",
              to_station_id: "100000417",
              to_station_name: "춘추문",
              to_station_num: "1602.0",
              from_district: "종로구",
              to_district: "종로구",
              distance_km: 1.22
            },
            daily_demand: 90,
            transfer_required: true,
            priority_category: "P1_저수요_환승구간"
          },
          {
            od_pair: {
              from_station_id: "108000011",
              from_station_name: "미아사거리역",
              from_station_num: "9011.0",
              to_station_id: "107000032",
              to_station_name: "정릉길음시장.길음뉴타운9단지",
              to_station_num: "8122.0",
              from_district: "강북구",
              to_district: "성북구",
              distance_km: 1.55
            },
            daily_demand: 88,
            transfer_required: true,
            priority_category: "P1_저수요_환승구간"
          },
          // P2, P3 샘플 데이터 추가
          {
            od_pair: {
              from_station_id: "121000001",
              from_station_name: "강남역",
              from_station_num: "21001.0",
              to_station_id: "121000002",
              to_station_name: "역삼역",
              to_station_num: "21002.0",
              from_district: "강남구",
              to_district: "강남구",
              distance_km: 2.1
            },
            daily_demand: 340,
            transfer_required: false,
            priority_category: "P2_직행부족"
          },
          {
            od_pair: {
              from_station_id: "125000001",
              from_station_name: "수서역",
              from_station_num: "25001.0",
              to_station_id: "101000010",
              to_station_name: "명동역",
              to_station_num: "2010.0",
              from_district: "강남구",
              to_district: "중구",
              distance_km: 15.2
            },
            daily_demand: 42,
            transfer_required: false,
            priority_category: "P3_장거리"
          }
        ];

        // 정류장 데이터를 OD 데이터에서 추출
        const stationMap = new Map<string, Station>();
        
        dummyODData.forEach(od => {
          // 출발지 정류장
          const fromKey = od.od_pair.from_station_id;
          if (!stationMap.has(fromKey)) {
            // 정류장 좌표 - 실제로는 API에서 받아와야 함
            const coords = getStationCoordinates(od.od_pair.from_station_name);
            stationMap.set(fromKey, {
              id: fromKey,
              name: od.od_pair.from_station_name,
              lat: coords.lat,
              lng: coords.lng,
              station_num: od.od_pair.from_station_num,
              district: od.od_pair.from_district
            });
          }
          
          // 도착지 정류장
          const toKey = od.od_pair.to_station_id;
          if (!stationMap.has(toKey)) {
            const coords = getStationCoordinates(od.od_pair.to_station_name);
            stationMap.set(toKey, {
              id: toKey,
              name: od.od_pair.to_station_name,
              lat: coords.lat,
              lng: coords.lng,
              station_num: od.od_pair.to_station_num,
              district: od.od_pair.to_district
            });
          }
          
          // OD 데이터에 origin, destination 추가
          od.origin = stationMap.get(fromKey);
          od.destination = stationMap.get(toKey);
        });

        const dummyStations = Array.from(stationMap.values());

        setStationData(dummyStations);
        setOdData(dummyODData);
      } catch (error) {
        console.error("Failed to load OD data:", error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedMonth, selectedRegion]);

  // 선택된 정류장의 OD 플로우 필터링
  const selectedStationFlows = useMemo(() => {
    if (!selectedStation) return [];
    
    let flows = odData.filter(od => {
      if (filters.flowDirection === 'outbound') {
        return od.origin?.id === selectedStation;
      } else if (filters.flowDirection === 'inbound') {
        return od.destination?.id === selectedStation;
      } else {
        return od.origin?.id === selectedStation || od.destination?.id === selectedStation;
      }
    });

    // 우선순위별 필터링
    flows = flows.filter(od => {
      if (od.priority_category.includes('P1_고수요_환승구간') && filters.showP1High) return true;
      if (od.priority_category.includes('P1_저수요_환승구간') && filters.showP1Low) return true;
      if (od.priority_category.includes('P2') && filters.showP2) return true;
      if (od.priority_category.includes('P3') && filters.showP3) return true;
      return false;
    });

    return flows;
  }, [selectedStation, odData, filters]);

  // 정류장 레이어
  const stationLayer = new ScatterplotLayer({
    id: 'stations',
    data: stationData,
    getPosition: (d: Station) => [d.lng, d.lat],
    getRadius: (d: Station) => {
      if (selectedStation === d.id) return 300;
      if (hoveredStation === d.id) return 200;
      return Math.max(80, Math.log(d.totalVolume || 1000) * 15);
    },
    getFillColor: (d: Station) => {
      if (selectedStation === d.id) return [255, 50, 50, 255];
      if (hoveredStation === d.id) return [255, 165, 0, 220];
      return [59, 130, 246, 200]; // 더 진한 파랑
    },
    getLineColor: [255, 255, 255, 100],
    lineWidthMinPixels: 2,
    pickable: true,
    onHover: ({ object }) => {
      setHoveredStation(object?.id || null);
    },
    onClick: ({ object }) => {
      setSelectedStation(object?.id || null);
    },
    updateTriggers: {
      getRadius: [selectedStation, hoveredStation],
      getFillColor: [selectedStation, hoveredStation]
    }
  });

  // OD 플로우 레이어 - 선택 안 했을 때는 필터링된 OD 표시
  const filteredFlowData = useMemo(() => {
    if (selectedStation) return selectedStationFlows;
    
    // 우선순위별 필터링
    return odData.filter(od => {
      if (od.priority_category.includes('P1_고수요_환승구간') && filters.showP1High) return true;
      if (od.priority_category.includes('P1_저수요_환승구간') && filters.showP1Low) return true;
      if (od.priority_category.includes('P2') && filters.showP2) return true;
      if (od.priority_category.includes('P3') && filters.showP3) return true;
      return false;
    });
  }, [selectedStation, selectedStationFlows, odData, filters]);

  const flowLayer = new ArcLayer({
    id: 'od-flows',
    data: filteredFlowData,
    getSourcePosition: (d: ODData) => [d.origin?.lng || 0, d.origin?.lat || 0],
    getTargetPosition: (d: ODData) => [d.destination?.lng || 0, d.destination?.lat || 0],
    getHeight: (d: ODData) => {
      const demandHeight = Math.log(d.daily_demand + 1) * 0.12;
      const distanceMultiplier = d.od_pair.distance_km > 5 ? 1.5 : 1.0;
      const transferMultiplier = d.transfer_required ? 1.3 : 1.0;
      return demandHeight * distanceMultiplier * transferMultiplier;
    },
    getSourceColor: (d: ODData) => getColorByPriority(d.priority_category),
    getTargetColor: (d: ODData) => getColorByPriority(d.priority_category),
    getWidth: (d: ODData) => Math.max(3, Math.log(d.daily_demand + 1) * 2),
    pickable: true,
    autoHighlight: true,
  });

  // 1단계: 시도 배경 레이어 (서울특별시 전체)
  const ctprvnLayer = seoulCtprvnGeoJson && filters.showMapBackground ? new GeoJsonLayer({
    id: 'seoul-ctprvn',
    data: seoulCtprvnGeoJson,
    pickable: false,
    stroked: true,
    filled: true,
    getFillColor: [255, 255, 255, 30],  // 더 투명하게
    getLineColor: [100, 100, 100, 150],  // 연한 회색 테두리
    getLineWidth: 100,
    lineWidthMinPixels: 2,
  }) : null;

  // 2단계: 구 경계 레이어 (25개 구)
  const sigLayer = seoulSigGeoJson && filters.showDistrictBoundaries ? new GeoJsonLayer({
    id: 'seoul-sig',
    data: seoulSigGeoJson,
    pickable: true,
    stroked: true,
    filled: true,
    getFillColor: (d: any) => {
      // 호버 상태일 때 하이라이트
      return hoveredStation === `district_${d.properties?.SIG_CD}` ? 
        [100, 150, 255, 80] : [255, 255, 255, 20];  // 더 투명하게
    },
    getLineColor: [80, 80, 80, 180],  // 진한 회색 구 경계
    getLineWidth: 30,
    lineWidthMinPixels: 1.5,
    onHover: ({ object }) => {
      if (object) {
        setHoveredStation(`district_${object.properties?.SIG_CD}`);
      } else {
        setHoveredStation(null);
      }
    },
    updateTriggers: {
      getFillColor: [hoveredStation]
    }
  }) : null;

  // 3단계: 동 경계 레이어 (467개 동)
  const emdLayer = seoulEmdGeoJson && filters.showDetailedBoundaries ? new GeoJsonLayer({
    id: 'seoul-emd',
    data: seoulEmdGeoJson,
    pickable: true,
    stroked: true,
    filled: false,
    getFillColor: [0, 0, 0, 0],
    getLineColor: (d: any) => {
      // 호버 상태일 때 하이라이트
      return hoveredStation === `emd_${d.properties?.EMD_CD}` ? 
        [255, 100, 100, 200] : [100, 100, 100, 100];  // 더 연한 회색
    },
    getLineWidth: (d: any) => {
      return hoveredStation === `emd_${d.properties?.EMD_CD}` ? 30 : 15;
    },
    lineWidthMinPixels: 0.3,
    onHover: ({ object }) => {
      if (object) {
        setHoveredStation(`emd_${object.properties?.EMD_CD}`);
      } else if (!hoveredStation?.startsWith('district_')) {
        // 구 호버 중이 아닐 때만 null로 설정
        setHoveredStation(null);
      }
    },
    updateTriggers: {
      getLineColor: [hoveredStation],
      getLineWidth: [hoveredStation]
    }
  }) : null;

  // CartoDB 지도 타일 레이어 (Leaflet과 동일한 스타일)
  const tileLayer = new TileLayer({
    id: 'carto-tiles',
    data: [
      // CartoDB Positron 타일 (밝은 스타일)
      'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
    ],
    minZoom: 0,
    maxZoom: 20,
    tileSize: 256,
    renderSubLayers: (props: any) => {
      const bbox = props.tile?.bbox;
      if (!bbox) return null;

      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [bbox.west, bbox.south, bbox.east, bbox.north]
      });
    }
  });

  // 레이어 순서: 타일(맨 아래) → 시도배경 → 구경계 → 동경계 → 스테이션 → 플로우
  const layers = [
    tileLayer,  // CartoDB 타일을 가장 아래에
    ...(ctprvnLayer ? [ctprvnLayer] : []),
    ...(sigLayer ? [sigLayer] : []),
    ...(emdLayer ? [emdLayer] : []),
    stationLayer,
    flowLayer
  ].filter(Boolean);

  // 로딩 중일 때
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">OD 데이터를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* 메인 지도 영역 */}
      <div className="flex-1 relative" onContextMenu={(e) => e.preventDefault()}>
        <DeckGL
          viewState={viewState}
          onViewStateChange={({ viewState }: any) => setViewState(viewState)}
          controller={true}
          layers={layers}
          getTooltip={({ object }: any) => {
            if (!object) return null;
            
            if (object.name) {
              // 정류장 툴팁
              return {
                html: `
                  <div class="bg-white p-2 rounded shadow-lg">
                    <div class="font-bold">${object.name}</div>
                    <div class="text-sm">구역: ${object.district || 'N/A'}</div>
                    <div class="text-sm">정류장 번호: ${object.station_num || 'N/A'}</div>
                    <div class="text-xs text-gray-500 mt-1">클릭하여 OD 플로우 보기</div>
                  </div>
                `
              };
            } else if (object.od_pair) {
              // OD 플로우 툴팁
              const priorityLabel = getPriorityLabel(object.priority_category);
              return {
                html: `
                  <div class="bg-white p-3 rounded shadow-lg border-l-4 ${
                    object.priority_category.includes('P1_고수요') ? 'border-red-500' :
                    object.priority_category.includes('P1_저수요') ? 'border-orange-500' :
                    object.priority_category.includes('P2') ? 'border-blue-500' :
                    object.priority_category.includes('P3') ? 'border-purple-500' : 'border-gray-500'
                  }">
                    <div class="font-bold text-sm">${object.od_pair.from_station_name}</div>
                    <div class="text-center text-xs text-gray-500 my-1">↓</div>
                    <div class="font-bold text-sm">${object.od_pair.to_station_name}</div>
                    <div class="mt-2 space-y-1">
                      <div class="text-sm">📊 일일 수요: <span class="font-bold">${object.daily_demand.toLocaleString()}명</span></div>
                      <div class="text-sm">📏 거리: <span class="font-bold">${object.od_pair.distance_km}km</span></div>
                      <div class="text-sm">🔄 환승: <span class="font-bold">${object.transfer_required ? '필요' : '불필요'}</span></div>
                      <div class="text-sm">🏢 구간: ${object.od_pair.from_district} → ${object.od_pair.to_district}</div>
                      <div class="text-xs mt-2 px-2 py-1 rounded" style="background: ${
                        object.priority_category.includes('P1_고수요') ? '#fee2e2' :
                        object.priority_category.includes('P1_저수요') ? '#fed7aa' :
                        object.priority_category.includes('P2') ? '#dbeafe' :
                        object.priority_category.includes('P3') ? '#e9d5ff' : '#f3f4f6'
                      }">${priorityLabel}</div>
                    </div>
                  </div>
                `
              };
            } else if (object.properties && (object.properties.SIG_KOR_NM || object.properties.SIG_ENG_NM)) {
              // 구 경계 툴팁
              const korName = object.properties.SIG_KOR_NM || 'N/A';
              const engName = object.properties.SIG_ENG_NM || '';
              const sigCode = object.properties.SIG_CD || '';
              
              // 해당 구의 정류장 개수 계산
              const stationsInDistrict = stationData.filter(station => {
                // 간단한 좌표 범위 체크 (실제로는 point-in-polygon이 정확)
                return station.name.includes(korName.replace('구', '')) || 
                       korName.includes('강남') && (station.name.includes('강남') || station.name.includes('역삼') || station.name.includes('선릉')) ||
                       korName.includes('서초') && station.name.includes('교대') ||
                       korName.includes('송파') && station.name.includes('잠실');
              });
              
              // 해당 구의 OD 플로우 개수 계산
              const odFlowsInDistrict = odData.filter(od => 
                stationsInDistrict.some(s => s.id === od.origin?.id || s.id === od.destination?.id)
              );
              
              return {
                html: `
                  <div class="bg-white p-3 rounded shadow-lg border-l-4 border-blue-500">
                    <div class="font-bold text-lg text-gray-800">${korName}</div>
                    ${engName && `<div class="text-sm text-gray-500 mb-2">${engName}</div>`}
                    <div class="space-y-1">
                      <div class="text-sm">🏢 구 코드: <span class="font-mono">${sigCode}</span></div>
                      <div class="text-sm">🚇 관할 정류장: <span class="font-bold text-blue-600">${stationsInDistrict.length}개</span></div>
                      <div class="text-sm">🔄 OD 연결: <span class="font-bold text-orange-600">${odFlowsInDistrict.length}개</span></div>
                      ${odFlowsInDistrict.filter(od => od.priority_category.includes('P1') || od.priority_category.includes('P2')).length > 0 ? 
                        `<div class="text-xs text-orange-600 mt-1">🎯 DRT 우선구간 ${odFlowsInDistrict.filter(od => od.priority_category.includes('P1') || od.priority_category.includes('P2')).length}개</div>` : ''}
                    </div>
                  </div>
                `
              };
            } else if (object.properties && (object.properties.EMD_KOR_NM || object.properties.EMD_ENG_NM)) {
              // 동 경계 툴팁
              const korName = object.properties.EMD_KOR_NM || 'N/A';
              const engName = object.properties.EMD_ENG_NM || '';
              const emdCode = object.properties.EMD_CD || '';
              
              return {
                html: `
                  <div class="bg-white p-2 rounded shadow-lg border-l-2 border-gray-400">
                    <div class="font-bold">${korName}</div>
                    ${engName && `<div class="text-xs text-gray-500">${engName}</div>`}
                    <div class="text-xs text-gray-600 mt-1">동코드: ${emdCode}</div>
                  </div>
                `
              };
            }
            return null;
          }}
        />
        
        {/* 지도 백업 배경 (CartoDB 타일이 있으므로 필요없음) */}
        
        {/* 서울 지역 표시 */}
        <div className="absolute top-4 left-4 z-10 text-xs text-gray-600 bg-white/90 p-2 rounded shadow-sm">
          📍 서울특별시 강남권 (강남구, 서초구, 송파구)
          <br />
          <span className="text-gray-500">
            🗺️ CartoDB 지도 표시
            {ctprvnLayer && <span className="block">🏛️ 서울특별시 경계</span>}
            {sigLayer && <span className="block">🏢 구 경계 (25개 구)</span>}
            {emdLayer && <span className="block">📍 동 경계 (467개 동)</span>}
          </span>
        </div>

        {/* 필터 컨트롤 - 초컴팩트 */}
        <Card className="absolute top-4 right-4 z-10 p-1.5 w-52 bg-white/95 backdrop-blur-sm">
          <CardTitle className="text-xs mb-1 font-semibold">필터</CardTitle>
          <div className="space-y-0">
            <div className="flex items-center gap-1 py-0.5">
              <Switch
                checked={filters.showP1High}
                onCheckedChange={(checked) => 
                  setFilters(prev => ({ ...prev, showP1High: checked }))
                }
                className="scale-75"
              />
              <div className="w-2 h-2 bg-red-600 rounded" />
              <Label className="text-xs">P1 고수요</Label>
            </div>
            <div className="flex items-center gap-1 py-0.5">
              <Switch
                checked={filters.showP1Low}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showP1Low: checked }))
                }
                className="scale-75"
              />
              <div className="w-2 h-2 bg-orange-500 rounded" />
              <Label className="text-xs">P1 저수요</Label>
            </div>
            <div className="flex items-center gap-1 py-0.5">
              <Switch
                checked={filters.showP2}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showP2: checked }))
                }
                className="scale-75"
              />
              <div className="w-2 h-2 bg-blue-500 rounded" />
              <Label className="text-xs">P2 직행부족</Label>
            </div>
            <div className="flex items-center gap-1 py-0.5">
              <Switch
                checked={filters.showP3}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showP3: checked }))
                }
                className="scale-75"
              />
              <div className="w-2 h-2 bg-purple-600 rounded" />
              <Label className="text-xs">P3 장거리</Label>
            </div>
          </div>

          <Separator className="my-3" />

          <div>
            <Label className="text-xs">플로우 방향</Label>
            <div className="grid grid-cols-3 gap-1 mt-1">
              <Button
                variant={filters.flowDirection === 'outbound' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilters(prev => ({ ...prev, flowDirection: 'outbound' }))}
                className="text-xs"
              >
                출발
              </Button>
              <Button
                variant={filters.flowDirection === 'inbound' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilters(prev => ({ ...prev, flowDirection: 'inbound' }))}
                className="text-xs"
              >
                도착
              </Button>
              <Button
                variant={filters.flowDirection === 'both' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilters(prev => ({ ...prev, flowDirection: 'both' }))}
                className="text-xs"
              >
                전체
              </Button>
            </div>
          </div>

          <Separator className="my-3" />

          <div className="space-y-2">
            <div className="text-xs font-medium mb-2">지도 레이어</div>
            
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showMapBackground}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showMapBackground: checked }))
                }
                disabled={!seoulCtprvnGeoJson}
              />
              <div className="w-3 h-3 bg-gray-300 rounded border" />
              <Label className="text-xs">서울특별시 배경</Label>
            </div>
            
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showDistrictBoundaries}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showDistrictBoundaries: checked }))
                }
                disabled={!seoulSigGeoJson}
              />
              <div className="w-3 h-3 bg-gray-200 border border-gray-400" />
              <Label className="text-xs">구 경계선</Label>
              {seoulSigGeoJson && (
                <span className="text-xs text-gray-500">
                  (25개 구)
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showDetailedBoundaries}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showDetailedBoundaries: checked }))
                }
                disabled={!seoulEmdGeoJson}
              />
              <div className="w-3 h-3 border border-gray-400 bg-transparent" />
              <Label className="text-xs">동 경계선</Label>
              {seoulEmdGeoJson && (
                <span className="text-xs text-gray-500">
                  (467개 동)
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* 범례 - 컴팩트 */}
        <Card className="absolute bottom-4 left-4 z-10 p-2 w-48 bg-white/95 backdrop-blur-sm">
          <div className="space-y-2">
            <div className="text-xs font-semibold">범례</div>
            
            {/* 정류장 */}
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-blue-500 rounded-full border border-white" />
              <span className="text-xs">정류장</span>
            </div>
            
            {/* OD 플로우 */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-1.5 bg-red-600 rounded-sm" />
                <span className="text-xs">P1 고수요</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-1.5 bg-orange-500 rounded-sm" />
                <span className="text-xs">P1 저수요</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-1.5 bg-blue-500 rounded-sm" />
                <span className="text-xs">P2 직행부족</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-1.5 bg-purple-600 rounded-sm" />
                <span className="text-xs">P3 장거리</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* 우측 상세 패널 */}
      <div className="w-96 border-l bg-white p-4 overflow-y-auto">
        {selectedStation ? (
          <div className="space-y-4">
            {/* 선택된 정류장 정보 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="h-5 w-5" />
                  {stationData.find(s => s.id === selectedStation)?.name}
                </CardTitle>
                <CardDescription>
                  {selectedStationFlows.length}개 연결 경로
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="outbound">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="outbound">출발</TabsTrigger>
                    <TabsTrigger value="inbound">도착</TabsTrigger>
                  </TabsList>

                  <TabsContent value="outbound" className="space-y-2">
                    {selectedStationFlows
                      .filter(flow => flow.origin?.id === selectedStation)
                      .sort((a, b) => b.daily_demand - a.daily_demand)
                      .slice(0, 5)
                      .map((flow, idx) => (
                        <div key={idx} className="p-2 bg-gray-50 rounded border-l-2" style={{
                          borderLeftColor: flow.priority_category.includes('P1_고수요') ? '#dc2626' :
                                          flow.priority_category.includes('P1_저수요') ? '#f97316' :
                                          flow.priority_category.includes('P2') ? '#2563eb' :
                                          flow.priority_category.includes('P3') ? '#9333ea' : '#6b7280'
                        }}>
                          <div className="flex justify-between items-center">
                            <div>
                              <div className="font-medium text-sm">{flow.destination?.name}</div>
                              <div className="text-xs text-gray-500">
                                {getPriorityLabel(flow.priority_category)}
                              </div>
                              <div className="text-xs text-gray-600 mt-1">
                                {flow.od_pair.distance_km}km • {flow.transfer_required ? '환승필요' : '직행'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold">{flow.daily_demand}명/일</div>
                              <div className="text-xs text-gray-500">{flow.od_pair.to_district}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </TabsContent>

                  <TabsContent value="inbound" className="space-y-2">
                    {selectedStationFlows
                      .filter(flow => flow.destination?.id === selectedStation)
                      .sort((a, b) => b.daily_demand - a.daily_demand)
                      .slice(0, 5)
                      .map((flow, idx) => (
                        <div key={idx} className="p-2 bg-gray-50 rounded border-l-2" style={{
                          borderLeftColor: flow.priority_category.includes('P1_고수요') ? '#dc2626' :
                                          flow.priority_category.includes('P1_저수요') ? '#f97316' :
                                          flow.priority_category.includes('P2') ? '#2563eb' :
                                          flow.priority_category.includes('P3') ? '#9333ea' : '#6b7280'
                        }}>
                          <div className="flex justify-between items-center">
                            <div>
                              <div className="font-medium text-sm">{flow.origin?.name}</div>
                              <div className="text-xs text-gray-500">
                                {getPriorityLabel(flow.priority_category)}
                              </div>
                              <div className="text-xs text-gray-600 mt-1">
                                {flow.od_pair.distance_km}km • {flow.transfer_required ? '환승필요' : '직행'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold">{flow.daily_demand}명/일</div>
                              <div className="text-xs text-gray-500">{flow.od_pair.from_district}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* DRT 우선순위 분석 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">DRT 우선순위 분석</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-red-600 rounded"></div>
                      P1 고수요 환승
                    </span>
                    <span className="font-bold text-red-600">
                      {selectedStationFlows.filter(f => f.priority_category.includes('P1_고수요')).length}개
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-orange-500 rounded"></div>
                      P1 저수요 환승
                    </span>
                    <span className="font-bold text-orange-600">
                      {selectedStationFlows.filter(f => f.priority_category.includes('P1_저수요')).length}개
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-blue-500 rounded"></div>
                      P2 직행부족
                    </span>
                    <span className="font-bold text-blue-600">
                      {selectedStationFlows.filter(f => f.priority_category.includes('P2')).length}개
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-purple-600 rounded"></div>
                      P3 장거리
                    </span>
                    <span className="font-bold text-purple-600">
                      {selectedStationFlows.filter(f => f.priority_category.includes('P3')).length}개
                    </span>
                  </div>
                  <div className="border-t pt-2 mt-3">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">총 예상 수혜자</span>
                      <span className="font-bold text-green-600">
                        {selectedStationFlows
                          .reduce((sum, f) => sum + f.daily_demand, 0)
                          .toLocaleString()}명/일
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <MapPin className="h-12 w-12 mb-4" />
            <p className="text-center">정류장을 클릭하여<br />OD 플로우를 확인하세요</p>
          </div>
        )}
      </div>
    </div>
  );
};