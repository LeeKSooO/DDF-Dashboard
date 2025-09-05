/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/exhaustive-deps */
"use client"

import { useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { apiService, DRTModelType, DRTStationData, utils } from '@/lib/api'

// District analysis 타입 정의
interface DistrictAnalysis {
  total_stations: number;
  avg_score: number;
  high_score_stations: number;
  stations: DRTStationData[];
  stationName?: string | null;
  stationData?: DRTStationData | null;
  districtName?: string;
  selectedModelScore?: number | null;
  allModelScores?: Record<string, number>;
  bestModel?: string;
  bestScore?: number;
  suitabilityLevel?: string;
  suitabilityColor?: string;
  peakHour?: string | number;
}

// Import leaflet
import L from 'leaflet';

// Fix for default markers in Leaflet - only on client side
if (typeof window !== 'undefined' && L) {
  delete (L.Icon.Default.prototype as any)._getIconUrl
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  })
}

// 모델 매핑
const modelTypeMapping: Record<string, DRTModelType> = {
  "교통취약지": "vulnerable",
  "출퇴근": "commuter", 
  "관광형": "tourism"
}

// 적합성 점수별 색상
const getSuitabilityColor = (score: number): string => {
  if (score >= 80) return '#22C55E' // Green - Very Suitable
  if (score >= 60) return '#EAB308' // Yellow - Suitable
  if (score >= 40) return '#F97316' // Orange - Fair
  return '#EF4444' // Red - Unsuitable
}

// 적합성 레벨 텍스트
const getSuitabilityLevel = (score: number): string => {
  if (score >= 80) return '매우 적합'
  if (score >= 60) return '적합'
  if (score >= 40) return '보통'
  return '부적합'
}

interface ModelSuitabilityMapProps {
  selectedModel: string
  selectedMonth?: string
  initialDistrictName?: string
  onDistrictAnalysis?: (districtName: string, analysis: DistrictAnalysis) => void
  height?: string
  focusStation?: { lat: number; lng: number; stationName: string } | null
}

interface StationAnalysis {
  stationId: string
  stationName: string
  coordinate: { lat: number; lng: number }
  drtScore: number
  suitabilityLevel: string
  suitabilityColor: string
  peakHour: number
}


function ModelSuitabilityMapComponent({ 
  selectedModel,
  selectedMonth = "7",
  initialDistrictName,
  onDistrictAnalysis,
  height = "600px",
  focusStation
}: ModelSuitabilityMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const [isClient, setIsClient] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null)
  const [districtScores] = useState<Record<string, Record<string, number>>>({})
  const [stationData, setStationData] = useState<DRTStationData[]>([])
  const [selectedStation, setSelectedStation] = useState<StationAnalysis | null>(null)
  const [stationMarkersLayer, setStationMarkersLayer] = useState<any>(null)

  // Seoul bounds for initial view and constraints
  const seoulBounds: [number, number] = [37.5665, 126.9780]
  const seoulBoundingBox: [[number, number], [number, number]] = [
    [37.413, 126.734], // Southwest corner 
    [37.715, 127.269]  // Northeast corner
  ]

  // Check if we're on client side
  useEffect(() => {
    setIsClient(true)
  }, [])

  // 선택된 모델에 따른 구별 색상 계산

  // Style function for districts with pastel colors
  const getFeatureStyle = (feature: any) => {
    const districtName = feature.properties.sggnm
    const isSelected = selectedDistrict === districtName

    return {
      fillColor: isSelected ? '#ddd6fe' : '#f3f4f6', // 파스텔 보라색 선택시, 연한 회색 기본
      weight: isSelected ? 3 : 1,
      opacity: 0.7, // 경계선 투명도
      color: isSelected ? '#8b5cf6' : '#d1d5db', // 파스텔 보라 경계선
      dashArray: '',
      fillOpacity: isSelected ? 0.4 : 0.2 // 더 투명하게
    }
  }

  // Load station data for selected district
  const loadStationData = async (districtName: string) => {
    try {
      console.log('🚏 Loading station data for:', districtName, 'with model:', selectedModel)
      console.log('🚏 Current model mapping:', { selectedModel, mappedType: modelTypeMapping[selectedModel] })
      setIsLoading(true)
      
      const apiModelType = modelTypeMapping[selectedModel] || "vulnerable"
      console.log('🔄 API call with params:', { districtName, selectedModel, apiModelType })
      
      const response = await apiService.getDRTScores(districtName, apiModelType, utils.formatSelectedMonth(selectedMonth))
      
      console.log('📊 Map Station DRT response:', response)
      console.log('📊 Stations count:', response.stations?.length || 0)
      setStationData(response.stations || [])
      
      // Clear previous station selection
      setSelectedStation(null)
      
      // Add station markers to map
      if (mapInstanceRef.current && L) {
        addStationMarkers(response.stations || [])
      }
      
    } catch (err) {
      console.error('🚨 Failed to load station data:', err)
      setStationData([])
    } finally {
      setIsLoading(false)
    }
  }

  // Add station markers to map
  const addStationMarkers = (stations: DRTStationData[]) => {
    if (!mapInstanceRef.current || !L) return
    
    // Remove existing station markers more thoroughly
    if (stationMarkersLayer) {
      mapInstanceRef.current.removeLayer(stationMarkersLayer)
      setStationMarkersLayer(null)
    }
    
    // Clear all existing markers by class name as backup
    mapInstanceRef.current.eachLayer((layer: any) => {
      if (layer.options && layer.options.icon && layer.options.icon.options.className === 'custom-drt-marker') {
        mapInstanceRef.current?.removeLayer(layer)
      }
    })
    
    const markers = stations.map(station => {
      const color = getSuitabilityColor(station.drt_score) // DRT score is already 0-100
      
      // Create custom marker icon based on DRT score
      const markerIcon = L.divIcon({
        html: `<div style="
          background-color: ${color};
          border: 2px solid white;
          border-radius: 50%;
          width: 12px;
          height: 12px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        "></div>`,
        className: 'custom-drt-marker',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
      })
      
      const marker = L.marker([station.coordinate.lat, station.coordinate.lng], {
        icon: markerIcon
      })
      
      // Station click handler
      marker.on('click', () => {
        analyzeStation(station)
      })
      
      // Station tooltip
      marker.bindTooltip(
        `<div>
          <strong>${station.station_name}</strong><br/>
          <small style="color: #666; font-size: 11px;">(ID: ${station.station_id})</small><br/>
          DRT 점수: ${station.drt_score.toFixed(1)}점<br/>
          적합성: ${getSuitabilityLevel(station.drt_score)}
        </div>`,
        {
          permanent: false,
          direction: 'top',
          offset: [0, -10]
        }
      )
      
      return marker
    })
    
    // Create layer group and add to map
    const layerGroup = L.layerGroup(markers).addTo(mapInstanceRef.current)
    setStationMarkersLayer(layerGroup)
  }
  
  // Analyze selected station
  const analyzeStation = (station: DRTStationData) => {
    console.log('🚏 Analyzing station:', station)
    
    const analysis: StationAnalysis = {
      stationId: station.station_id,
      stationName: station.station_name,
      coordinate: station.coordinate,
      drtScore: station.drt_score, // DRT score is already 0-100
      suitabilityLevel: getSuitabilityLevel(station.drt_score),
      suitabilityColor: getSuitabilityColor(station.drt_score),
      peakHour: station.peak_hour
    }
    
    setSelectedStation(analysis)
    
    // Zoom to station
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([station.coordinate.lat, station.coordinate.lng], 16)
    }
    
    // Call district analysis callback with station data
    if (onDistrictAnalysis) {
      onDistrictAnalysis(selectedDistrict || "강남구", {
        total_stations: 0,
        avg_score: 0,
        high_score_stations: 0,
        stations: [],
        districtName: selectedDistrict || undefined,
        stationName: station.station_name,
        selectedModelScore: station.drt_score,
        allModelScores: { [selectedModel]: station.drt_score },
        bestModel: selectedModel,
        bestScore: station.drt_score,
        suitabilityLevel: getSuitabilityLevel(station.drt_score),
        suitabilityColor: getSuitabilityColor(station.drt_score),
        peakHour: station.peak_hour,
        stationData: station // 정류장 데이터 직접 전달
      })
    }
  }

  // 구 클릭 시 정류장 데이터 로드
  const analyzeDistrict = async (districtName: string) => {
    try {
      console.log('🔍 Analyzing district:', districtName, 'with current model:', selectedModel)
      
      // Clear existing station selection first
      setSelectedStation(null)
      
      // Remove existing station markers immediately
      if (stationMarkersLayer && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(stationMarkersLayer)
        setStationMarkersLayer(null)
      }
      
      setSelectedDistrict(districtName)
      
      // Load station data for this district with current model
      await loadStationData(districtName)
      
      // Notify parent component about district change
      if (onDistrictAnalysis) {
        console.log('📤 Notifying parent about district change:', districtName);
        onDistrictAnalysis(districtName, {
          total_stations: 0,
          avg_score: 0,
          high_score_stations: 0,
          stations: [],
          districtName,
          stationName: null, // No specific station selected
          selectedModelScore: null,
          allModelScores: {},
          bestModel: selectedModel,
          stationData: null
        });
      }
      
    } catch (err) {
      console.error('🚨 District analysis error:', err)
    }
  }

  useEffect(() => {
    if (!isClient || !L || !mapRef.current || mapInstanceRef.current) return

    console.log('🗺️ Initializing model suitability map...')

    // Initialize map with CartoDB Positron style and Seoul bounds constraints
    const map = L.map(mapRef.current, {
      center: seoulBounds,
      zoom: 11,
      minZoom: 10,        // 최소 줌 레벨 설정
      maxZoom: 16,        // 최대 줌 레벨 설정
      maxBounds: seoulBoundingBox, // 서울시 경계로 이동 제한
      maxBoundsViscosity: 1.0,     // 경계 제한 강도 (1.0 = 완전 제한)
      zoomControl: false,  // 기본 줌 컨트롤 비활성화
      attributionControl: true
    })
    
    // Add zoom control to bottom-right to avoid overlap with other controls
    L.control.zoom({
      position: 'bottomright'
    }).addTo(map)

    // CartoDB Positron tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map)

    mapInstanceRef.current = map

    // Load GeoJSON data
    const loadGeoJSON = async () => {
      try {
        setIsLoading(true)
        setError(null)

        const response = await fetch('/seoul-districts-simple.geojson')
        if (!response.ok) {
          throw new Error(`Failed to load GeoJSON: ${response.status}`)
        }

        const geoJsonData = await response.json()
        
        // Add all district features to map
        L.geoJSON(geoJsonData, {
          style: getFeatureStyle,
          onEachFeature: (feature: any, layer: any) => {
            const districtName = feature.properties.sggnm

            // Mouse events
            layer.on({
              mouseover: (e: any) => {
                const layer = e.target
                layer.setStyle({
                  weight: 3,
                  color: '#2563EB',
                  fillOpacity: 0.25
                })
                layer.bringToFront()
              },
              mouseout: (e: any) => {
                const layer = e.target
                layer.setStyle(getFeatureStyle(feature))
              },
              click: () => {
                const districtName = feature.properties.sggnm
                
                // Zoom to district
                map.fitBounds(layer.getBounds())
                
                // Load station data for this district
                analyzeDistrict(districtName)
              }
            })

            // Initial tooltip
            layer.bindTooltip(
              `<div>
                <strong>${districtName}</strong><br/>
                클릭하여 정류장별 DRT 적합도 보기
              </div>`,
              {
                permanent: false,
                direction: 'center',
                className: 'district-tooltip'
              }
            )
          }
        }).addTo(map)

        setIsLoading(false)
      } catch (err) {
        console.error('Failed to load GeoJSON:', err)
        setError(err instanceof Error ? err.message : 'Failed to load map data')
        setIsLoading(false)
      }
    }

    loadGeoJSON()

    // Cleanup function
    return () => {
      if (stationMarkersLayer && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(stationMarkersLayer)
      }
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [isClient])

  // 초기 구 로드
  useEffect(() => {
    if (!isClient || !initialDistrictName || selectedDistrict === initialDistrictName) return
    
    console.log('🗺️ Loading initial district:', initialDistrictName)
    analyzeDistrict(initialDistrictName)
  }, [initialDistrictName, isClient])

  // Update station markers when model changes (only if district is already selected)
  useEffect(() => {
    if (!isClient || !selectedDistrict) return
    
    console.log('🔄 Updating station data for model change:', selectedModel, 'in district:', selectedDistrict)
    loadStationData(selectedDistrict)
  }, [selectedModel, isClient, selectedDistrict])

  // Focus on specific station when requested
  useEffect(() => {
    if (!isClient || !L || !mapInstanceRef.current || !focusStation) return

    console.log('🎯 Focusing map on station:', focusStation.stationName, 'at coordinates:', focusStation.lat, focusStation.lng)
    
    // Smoothly pan and zoom to the station (줌 레벨 17로 더 가깝게)
    mapInstanceRef.current.setView([focusStation.lat, focusStation.lng], 17, {
      animate: true,
      duration: 1.0, // 1 second animation
      easeLinearity: 0.25
    })
    
    // Add a temporary pulsing marker for better visual feedback
    const pulsingIcon = L.divIcon({
      html: `<div style="
        background-color: #3B82F6;
        border: 3px solid white;
        border-radius: 50%;
        width: 30px;
        height: 30px;
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.8);
        animation: pulse 1.5s infinite;
      "></div>
      <style>
        @keyframes pulse {
          0% { transform: scale(1); opacity: 1; box-shadow: 0 0 30px rgba(59, 130, 246, 0.8); }
          50% { transform: scale(1.3); opacity: 0.9; box-shadow: 0 0 50px rgba(59, 130, 246, 1); }
          100% { transform: scale(1); opacity: 1; box-shadow: 0 0 30px rgba(59, 130, 246, 0.8); }
        }
      </style>`,
      className: 'pulsing-marker',
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    })
    
    const tempMarker = L.marker([focusStation.lat, focusStation.lng], { icon: pulsingIcon })
      .addTo(mapInstanceRef.current)
      .bindPopup(`
        <div style="text-align: center; padding: 5px;">
          <strong style="font-size: 16px;">🎯 ${focusStation.stationName}</strong><br/>
          <small style="color: #666;">검색에서 선택된 정류장</small>
        </div>
      `, { offset: [0, -15] })
      .openPopup()
    
    // Remove temporary marker after 6 seconds (더 오래 표시)
    setTimeout(() => {
      if (mapInstanceRef.current && tempMarker) {
        mapInstanceRef.current.removeLayer(tempMarker)
      }
    }, 6000)
    
  }, [focusStation, isClient])
  
  // Update district styles when needed
  useEffect(() => {
    if (!isClient || !L || !mapInstanceRef.current) return

    mapInstanceRef.current.eachLayer((layer: any) => {
      if (layer instanceof L.GeoJSON) {
        layer.eachLayer((featureLayer: any) => {
          if (featureLayer instanceof L.Path) {
            const feature = (featureLayer as any).feature
            if (feature) {
              // Update style
              featureLayer.setStyle(getFeatureStyle(feature))
              
              // Update tooltip
              const districtName = feature.properties.sggnm
              featureLayer.setTooltipContent(
                `<div>
                  <strong>${districtName}</strong><br/>
                  클릭하여 정류장별 DRT 적합도 보기
                </div>`
              )
            }
          }
        })
      }
    })
  }, [districtScores, selectedDistrict, isClient])

  if (error) {
    return (
      <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center text-red-500">
          <p className="font-medium">지도 로딩 실패</p>
          <p className="text-base">{error}</p>
        </div>
      </div>
    )
  }

  // Don't render anything on server side
  if (!isClient) {
    return (
      <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-600">지도 로딩 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <div 
        ref={mapRef} 
        className="rounded-lg border"
        style={{ height: height, zIndex: 1 }}
      />
      
      {isLoading && (
        <div className="absolute inset-0 bg-gray-100 rounded-lg flex items-center justify-center z-10">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">지도 로딩 중...</p>
          </div>
        </div>
      )}

      {/* Station DRT Legend */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg text-base z-20">
        <div className="font-medium mb-2">🚏 정류장 DRT 적합성</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-[#22C55E] rounded-full border border-white shadow-sm"></div>
            <span>매우 적합 (80점 이상)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-[#EAB308] rounded-full border border-white shadow-sm"></div>
            <span>적합 (60-80점)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-[#F97316] rounded-full border border-white shadow-sm"></div>
            <span>보통 (40-60점)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-[#EF4444] rounded-full border border-white shadow-sm"></div>
            <span>부적합 (40점 미만)</span>
          </div>
        </div>
        {stationData.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200">
            <div className="text-blue-600 font-medium">
              {selectedDistrict}: {stationData.length}개 정류장
            </div>
            <div className="text-gray-500">
              평균 DRT: {(stationData.reduce((sum, s) => sum + s.drt_score, 0) / stationData.length).toFixed(1)}점
            </div>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm z-20">
        <div className="text-base">
          <div className="font-medium text-blue-600">💡 사용법</div>
          <div className="text-gray-600">1. 구를 클릭하여 정류장 표시</div>
          <div className="text-gray-600">2. 정류장을 클릭하여 상세 분석</div>
        </div>
      </div>

      {/* Selected Station Info */}
      {selectedStation ? (
        <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm z-20">
          <div className="text-base">
            <div className="font-medium">🚏 선택된 정류장</div>
            <div className="text-blue-600 font-bold">{selectedStation.stationName}</div>
            <div className="flex items-center gap-2 mt-1">
              <div 
                className="w-3 h-3 rounded-full border border-white shadow-sm"
                style={{ backgroundColor: selectedStation.suitabilityColor }}
              ></div>
              <span className="text-gray-700">{selectedStation.drtScore.toFixed(1)}점 ({selectedStation.suitabilityLevel})</span>
            </div>
            <div className="text-gray-500">피크: {selectedStation.peakHour}시</div>
          </div>
        </div>
      ) : selectedDistrict && (
        <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm z-20">
          <div className="text-base">
            <div className="font-medium">📍 선택된 구</div>
            <div className="text-blue-600 font-bold">{selectedDistrict}</div>
            <div className="text-gray-500">{stationData.length}개 정류장 표시됨</div>
          </div>
        </div>
      )}
    </div>
  )
}

// Export as dynamic component to prevent SSR issues
export const ModelSuitabilityMap = dynamic(() => Promise.resolve(ModelSuitabilityMapComponent), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
        <p className="text-gray-600">모델 적합성 지도 로딩 중...</p>
      </div>
    </div>
  )
})