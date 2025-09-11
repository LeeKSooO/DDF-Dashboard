"use client";

import { useState, useEffect, useMemo } from "react";
import DeckGL from '@deck.gl/react';
import { ArcLayer, ScatterplotLayer, GeoJsonLayer, BitmapLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { MapPin, TrendingUp, AlertCircle, Clock, ArrowRight } from "lucide-react";
import { apiService } from "@/lib/api";
import { ensureFeatureCollection } from "@/lib/geojson-utils";

// TypeScript interfaces
interface Station {
  id: string;
  name: string;
  lat: number;
  lng: number;
  totalVolume?: number;
}

interface ODData {
  origin: Station;
  destination: Station;
  volume: number;
  rank: number;
  hour?: number;
  currentService?: {
    transferCount: number;
    travelTime: number;
    headway: number;
  };
  drtMetrics?: {
    opportunityScore: number;
    category: 'high' | 'medium' | 'low';
  };
}

interface ODAnalysisContentProps {
  selectedMonth?: string;
  selectedRegion?: string;
}

// 색상 매핑 함수
const getColorByRank = (rank: number): [number, number, number, number] => {
  if (rank <= 100) return [59, 130, 246, 200];      // 파랑 - 이미 충분한 서비스
  if (rank <= 10000) return [249, 115, 22, 220];    // 주황 - DRT 타겟
  return [156, 163, 175, 150];                       // 회색 - 낮은 우선순위
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

  // 필터 상태
  const [filters, setFilters] = useState({
    showTop100: true,
    showTop10000: true,
    showTop20000: false,
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
        
        // TODO: 실제 API 호출로 교체
        // const response = await apiService.getODAnalysis({ month: selectedMonth, region: selectedRegion });
        
        // 더 많은 임시 더미 데이터
        const dummyStations: Station[] = [
          // 강남구 주요 역
          { id: "121000012", name: "강남역", lat: 37.4979, lng: 127.0276, totalVolume: 45000 },
          { id: "121000045", name: "청담역", lat: 37.5194, lng: 127.0538, totalVolume: 23000 },
          { id: "121000078", name: "역삼역", lat: 37.5006, lng: 127.0365, totalVolume: 38000 },
          { id: "121000091", name: "삼성역", lat: 37.5089, lng: 127.0631, totalVolume: 31000 },
          { id: "121000102", name: "선릉역", lat: 37.5045, lng: 127.0486, totalVolume: 29000 },
          { id: "121000103", name: "논현역", lat: 37.5110, lng: 127.0214, totalVolume: 21000 },
          { id: "121000104", name: "신논현역", lat: 37.5048, lng: 127.0247, totalVolume: 19000 },
          { id: "121000105", name: "양재역", lat: 37.4845, lng: 127.0342, totalVolume: 25000 },
          
          // 서초구 주요 역
          { id: "121000201", name: "교대역", lat: 37.4930, lng: 127.0139, totalVolume: 27000 },
          { id: "121000202", name: "방배역", lat: 37.4818, lng: 126.9975, totalVolume: 18000 },
          { id: "121000203", name: "서초역", lat: 37.4918, lng: 127.0078, totalVolume: 22000 },
          { id: "121000204", name: "남부터미널역", lat: 37.4850, lng: 127.0166, totalVolume: 24000 },
          
          // 송파구 주요 역
          { id: "121000301", name: "잠실역", lat: 37.5132, lng: 127.1001, totalVolume: 42000 },
          { id: "121000302", name: "석촌역", lat: 37.5056, lng: 127.1067, totalVolume: 20000 },
          { id: "121000303", name: "송파역", lat: 37.4997, lng: 127.1120, totalVolume: 17000 },
          { id: "121000304", name: "가락시장역", lat: 37.4923, lng: 127.1184, totalVolume: 19000 },
        ];

        // 더 많은 OD 데이터 생성
        const dummyOD: ODData[] = [
          // Top 100 구간 (서비스 충분)
          {
            origin: dummyStations[0], // 강남역
            destination: dummyStations[2], // 역삼역
            volume: 4500,
            rank: 23,
            currentService: { transferCount: 0, travelTime: 8, headway: 3 }
          },
          {
            origin: dummyStations[0], // 강남역
            destination: dummyStations[4], // 선릉역
            volume: 3800,
            rank: 45,
            currentService: { transferCount: 0, travelTime: 10, headway: 3 }
          },
          {
            origin: dummyStations[12], // 잠실역
            destination: dummyStations[0], // 강남역
            volume: 3200,
            rank: 67,
            currentService: { transferCount: 0, travelTime: 15, headway: 5 }
          },
          
          // Top 10000 구간 (DRT 타겟)
          {
            origin: dummyStations[0], // 강남역
            destination: dummyStations[1], // 청담역
            volume: 2450,
            rank: 1520,
            currentService: { transferCount: 2, travelTime: 35, headway: 20 }
          },
          {
            origin: dummyStations[2], // 역삼역
            destination: dummyStations[9], // 방배역
            volume: 1850,
            rank: 3234,
            currentService: { transferCount: 2, travelTime: 28, headway: 15 }
          },
          {
            origin: dummyStations[3], // 삼성역
            destination: dummyStations[10], // 서초역
            volume: 1650,
            rank: 4567,
            currentService: { transferCount: 1, travelTime: 25, headway: 18 }
          },
          {
            origin: dummyStations[5], // 논현역
            destination: dummyStations[14], // 석촌역
            volume: 1450,
            rank: 6789,
            currentService: { transferCount: 3, travelTime: 45, headway: 25 }
          },
          {
            origin: dummyStations[7], // 양재역
            destination: dummyStations[13], // 잠실역
            volume: 1250,
            rank: 8901,
            currentService: { transferCount: 2, travelTime: 38, headway: 20 }
          },
          
          // Top 20000 구간 (통합 가능)
          {
            origin: dummyStations[6], // 신논현역
            destination: dummyStations[15], // 송파역
            volume: 950,
            rank: 12450,
            currentService: { transferCount: 3, travelTime: 50, headway: 30 }
          },
          {
            origin: dummyStations[8], // 교대역
            destination: dummyStations[1], // 청담역
            volume: 850,
            rank: 14567,
            currentService: { transferCount: 3, travelTime: 42, headway: 25 }
          },
          {
            origin: dummyStations[11], // 남부터미널역
            destination: dummyStations[15], // 송파역
            volume: 750,
            rank: 17890,
            currentService: { transferCount: 4, travelTime: 55, headway: 35 }
          },
          
          // 역방향 추가 (더 풍부한 네트워크)
          {
            origin: dummyStations[1], // 청담역
            destination: dummyStations[0], // 강남역
            volume: 2100,
            rank: 2345,
            currentService: { transferCount: 2, travelTime: 35, headway: 20 }
          },
          {
            origin: dummyStations[4], // 선릉역
            destination: dummyStations[2], // 역삼역
            volume: 1900,
            rank: 3456,
            currentService: { transferCount: 0, travelTime: 8, headway: 5 }
          },
          {
            origin: dummyStations[12], // 잠실역
            destination: dummyStations[3], // 삼성역
            volume: 1750,
            rank: 4789,
            currentService: { transferCount: 1, travelTime: 22, headway: 12 }
          },
          {
            origin: dummyStations[10], // 서초역
            destination: dummyStations[0], // 강남역
            volume: 1550,
            rank: 5678,
            currentService: { transferCount: 1, travelTime: 18, headway: 10 }
          }
        ];

        setStationData(dummyStations);
        setOdData(dummyOD);
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
        return od.origin.id === selectedStation;
      } else if (filters.flowDirection === 'inbound') {
        return od.destination.id === selectedStation;
      } else {
        return od.origin.id === selectedStation || od.destination.id === selectedStation;
      }
    });

    // 순위별 필터링
    flows = flows.filter(od => {
      if (od.rank <= 100 && filters.showTop100) return true;
      if (od.rank > 100 && od.rank <= 10000 && filters.showTop10000) return true;
      if (od.rank > 10000 && filters.showTop20000) return true;
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

  // OD 플로우 레이어 - 선택 안 했을 때는 모든 OD 표시
  const flowData = selectedStation ? selectedStationFlows : odData;
  const flowLayer = new ArcLayer({
    id: 'od-flows',
    data: flowData,
    getSourcePosition: (d: ODData) => [d.origin.lng, d.origin.lat],
    getTargetPosition: (d: ODData) => [d.destination.lng, d.destination.lat],
    getHeight: (d: ODData) => {
      const volumeHeight = Math.log(d.volume) * 0.08;
      const rankMultiplier = d.rank <= 100 ? 1.5 : d.rank <= 10000 ? 1.2 : 0.8;
      return volumeHeight * rankMultiplier;
    },
    getSourceColor: (d: ODData) => getColorByRank(d.rank),
    getTargetColor: (d: ODData) => getColorByRank(d.rank),
    getWidth: (d: ODData) => Math.max(4, Math.log(d.volume) * 1.5),
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
    onHover: ({ object, x, y }) => {
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
    onHover: ({ object, x, y }) => {
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
    renderSubLayers: props => {
      const {
        bbox: {west, south, east, north}
      } = props.tile;

      return new BitmapLayer(props, {
        data: null,
        image: props.data,
        bounds: [west, south, east, north]
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
      <div className="flex-1 relative">
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
                    <div class="text-sm">일일 이용객: ${object.totalVolume?.toLocaleString() || 'N/A'}명</div>
                    <div class="text-xs text-gray-500 mt-1">클릭하여 OD 플로우 보기</div>
                  </div>
                `
              };
            } else if (object.origin && object.destination) {
              // OD 플로우 툴팁
              return {
                html: `
                  <div class="bg-white p-2 rounded shadow-lg">
                    <div class="font-bold text-sm">${object.origin.name} → ${object.destination.name}</div>
                    <div class="text-sm">일일 이동량: ${object.volume.toLocaleString()}명</div>
                    <div class="text-sm">순위: ${object.rank}위</div>
                    ${object.rank > 100 && object.rank <= 10000 ? 
                      '<div class="text-xs text-orange-600 mt-1">🎯 DRT 적합 구간</div>' : ''}
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
                stationsInDistrict.some(s => s.id === od.origin.id || s.id === od.destination.id)
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
                      ${odFlowsInDistrict.filter(od => od.rank <= 10000).length > 0 ? 
                        `<div class="text-xs text-orange-600 mt-1">🎯 DRT 적합 구간 ${odFlowsInDistrict.filter(od => od.rank <= 10000).length}개</div>` : ''}
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

        {/* 필터 컨트롤 */}
        <Card className="absolute top-4 right-4 z-10 p-3 w-64">
          <CardTitle className="text-sm mb-3">OD 순위별 필터</CardTitle>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showTop100}
                onCheckedChange={(checked) => 
                  setFilters(prev => ({ ...prev, showTop100: checked }))
                }
              />
              <div className="w-3 h-3 bg-blue-500 rounded" />
              <Label className="text-xs">Top 100 (서비스 충분)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showTop10000}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showTop10000: checked }))
                }
              />
              <div className="w-3 h-3 bg-orange-500 rounded" />
              <Label className="text-xs">Top 10,000 (DRT 타겟)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={filters.showTop20000}
                onCheckedChange={(checked) =>
                  setFilters(prev => ({ ...prev, showTop20000: checked }))
                }
              />
              <div className="w-3 h-3 bg-gray-400 rounded" />
              <Label className="text-xs">Top 20,000 (통합 가능)</Label>
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

        {/* 범례 */}
        <Card className="absolute bottom-4 left-4 z-10 p-3 max-w-xs">
          <div className="space-y-3">
            <div className="text-sm font-semibold">시각화 범례</div>
            
            {/* 정류장 */}
            <div>
              <div className="text-xs font-medium mb-1">정류장</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded-full border border-white" />
                <span className="text-xs">클릭하여 OD 플로우 확인</span>
              </div>
            </div>
            
            {/* OD 플로우 */}
            <div>
              <div className="text-xs font-medium mb-1">OD 플로우 (순위별)</div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-2 bg-blue-500 rounded-sm" />
                  <span className="text-xs">Top 100 - 서비스 충분</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-2 bg-orange-500 rounded-sm" />
                  <span className="text-xs">Top 10,000 - DRT 적합</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-2 bg-gray-400 rounded-sm" />
                  <span className="text-xs">Top 20,000+ - 통합 가능</span>
                </div>
              </div>
            </div>
            
            {/* 사용법 */}
            <div className="text-xs text-gray-500 border-t pt-2">
              💡 정류장을 클릭하면 해당 OD만 표시됩니다
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
                      .filter(flow => flow.origin.id === selectedStation)
                      .sort((a, b) => b.volume - a.volume)
                      .slice(0, 5)
                      .map((flow, idx) => (
                        <div key={idx} className="p-2 bg-gray-50 rounded">
                          <div className="flex justify-between items-center">
                            <div>
                              <div className="font-medium text-sm">{flow.destination.name}</div>
                              <div className="text-xs text-gray-500">
                                {flow.rank <= 10000 ? '🎯 DRT 적합' : '일반'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold">{flow.volume}명</div>
                              <div className="text-xs text-gray-500">{flow.rank}위</div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </TabsContent>

                  <TabsContent value="inbound" className="space-y-2">
                    {selectedStationFlows
                      .filter(flow => flow.destination.id === selectedStation)
                      .sort((a, b) => b.volume - a.volume)
                      .slice(0, 5)
                      .map((flow, idx) => (
                        <div key={idx} className="p-2 bg-gray-50 rounded">
                          <div className="flex justify-between items-center">
                            <div>
                              <div className="font-medium text-sm">{flow.origin.name}</div>
                              <div className="text-xs text-gray-500">
                                {flow.rank <= 10000 ? '🎯 DRT 적합' : '일반'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold">{flow.volume}명</div>
                              <div className="text-xs text-gray-500">{flow.rank}위</div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* DRT 기회 분석 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">DRT 기회 분석</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>DRT 적합 구간</span>
                    <span className="font-bold text-orange-600">
                      {selectedStationFlows.filter(f => f.rank > 100 && f.rank <= 10000).length}개
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>예상 수혜자</span>
                    <span className="font-bold">
                      {selectedStationFlows
                        .filter(f => f.rank > 100 && f.rank <= 10000)
                        .reduce((sum, f) => sum + f.volume, 0)
                        .toLocaleString()}명/일
                    </span>
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