"use client"

import { useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { DRTScoreResponse } from '@/lib/api'

// Dynamically import Leaflet to avoid SSR issues
const L = typeof window !== 'undefined' ? require('leaflet') : null

// Fix for default markers in Leaflet - only on client side
if (typeof window !== 'undefined' && L) {
  delete (L.Icon.Default.prototype as any)._getIconUrl
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  })
}

interface DRTScoreMapProps {
  drtData: DRTScoreResponse | null
  selectedModel: string
  loading?: boolean
  error?: string | null
}

function DRTScoreMapComponent({ drtData, selectedModel, loading = false, error = null }: DRTScoreMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const [isClient, setIsClient] = useState(false)

  // Check if we're on client side
  useEffect(() => {
    setIsClient(true)
  }, [])

  // Pastel DRT Score colors based on score value
  const getDRTScoreColor = (score: number): string => {
    if (score >= 80) return '#fca5a5' // 파스텔 레드
    if (score >= 60) return '#fed7aa' // 파스텔 오렌지  
    if (score >= 40) return '#fde68a' // 파스텔 노랑
    if (score >= 20) return '#bbf7d0' // 파스텔 그린
    return '#d1d5db' // 파스텔 그레이
  }

  // Initialize map
  useEffect(() => {
    if (!isClient || !L || !mapRef.current || mapInstanceRef.current) return

    console.log('🗺️ Initializing DRT Score map...')

    // Set initial center based on district or default Seoul
    const defaultCenter: [number, number] = [37.5665, 126.9780] // Seoul center
    const seoulBoundingBox: [[number, number], [number, number]] = [
      [37.413, 126.734], // Southwest corner 
      [37.715, 127.269]  // Northeast corner
    ]
    
    const map = L.map(mapRef.current, {
      center: defaultCenter,
      zoom: 12,
      minZoom: 10,        // 최소 줌 레벨 설정
      maxZoom: 16,        // 최대 줌 레벨 설정
      maxBounds: seoulBoundingBox, // 서울시 경계로 이동 제한
      maxBoundsViscosity: 1.0,     // 경계 제한 강도 (1.0 = 완전 제한)
      zoomControl: true,
      attributionControl: true
    })

    // CartoDB Positron tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map)

    mapInstanceRef.current = map

    // Cleanup function
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [isClient])

  // Update markers when DRT data changes
  useEffect(() => {
    if (!isClient || !L || !mapInstanceRef.current || !drtData) return

    console.log('🎯 Updating DRT score markers:', drtData.stations.length, 'stations')

    // Clear existing markers
    markersRef.current.forEach(marker => {
      if (mapInstanceRef.current && marker) {
        mapInstanceRef.current.removeLayer(marker)
      }
    })
    markersRef.current = []

    // Add station markers with DRT scores
    drtData.stations.forEach(station => {
      const lat = station.coordinate?.lat
      const lng = station.coordinate?.lng
      
      if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
        // Create marker size based on DRT score
        const markerSize = Math.min(Math.max(station.drt_score / 10, 4), 20)
        
        const marker = L.circleMarker([lat, lng], {
          radius: markerSize,
          fillColor: getDRTScoreColor(station.drt_score),
          color: getDRTScoreColor(station.drt_score),
          weight: 1,
          opacity: 0.7,
          fillOpacity: 0.5
        })
        
        // Add popup with station details
        marker.bindPopup(`
          <div class="text-base">
            <strong>${station.station_name}</strong><br/>
            DRT 점수: <span class="font-bold" style="color: ${getDRTScoreColor(station.drt_score)}">${station.drt_score.toFixed(1)}</span><br/>
            피크시간: ${station.peak_hour}시<br/>
            모델: ${selectedModel}
          </div>
        `)
        
        marker.addTo(mapInstanceRef.current)
        markersRef.current.push(marker)
      }
    })

    // Fit map to show all markers if we have data
    if (markersRef.current.length > 0) {
      const group = new L.featureGroup(markersRef.current)
      mapInstanceRef.current.fitBounds(group.getBounds().pad(0.1))
    }

  }, [drtData, selectedModel, isClient])

  if (loading) {
    return (
      <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-600">DRT 데이터 로딩 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center text-red-500">
          <p className="font-medium">DRT 데이터 로드 실패</p>
          <p className="text-base mt-2">{error}</p>
        </div>
      </div>
    )
  }

  if (!drtData || drtData.stations.length === 0) {
    return (
      <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center text-gray-500">
          <p className="font-medium">DRT 데이터 없음</p>
          <p className="text-base mt-2">선택된 지역/모델의 데이터가 없습니다</p>
        </div>
      </div>
    )
  }

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
        className="h-[400px] rounded-lg border"
        style={{ zIndex: 1 }}
      />

      {/* DRT Score Legend */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg text-base z-20">
        <div className="font-medium mb-2">DRT 점수 범례</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#DC2626] rounded-sm"></div>
            <span>우수 (80점 이상)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#EA580C] rounded-sm"></div>
            <span>양호 (60-80점)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#EAB308] rounded-sm"></div>
            <span>보통 (40-60점)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#16A34A] rounded-sm"></div>
            <span>미흡 (20-40점)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#6B7280] rounded-sm"></div>
            <span>부족 (20점 미만)</span>
          </div>
        </div>
      </div>

      {/* Model Info */}
      <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-2 shadow-sm z-20">
        <div className="text-base">
          <div className="font-medium">{selectedModel} 모델</div>
          <div className="text-gray-600">{drtData?.stations.length}개 정류장</div>
        </div>
      </div>

      {/* Top Stations Info */}
      {drtData.top_stations.length > 0 && (
        <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm z-20">
          <div className="font-medium mb-2 text-base">🏆 TOP 3 정류장</div>
          <div className="space-y-1 text-base">
            {drtData.top_stations.slice(0, 3).map((station, idx) => (
              <div key={station.station_id} className="flex justify-between items-center">
                <span className="truncate max-w-24">{station.station_name}</span>
                <span 
                  className="font-bold ml-2"
                  style={{ color: getDRTScoreColor(station.drt_score) }}
                >
                  {station.drt_score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Export as dynamic component to prevent SSR issues
export const DRTScoreMap = dynamic(() => Promise.resolve(DRTScoreMapComponent), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
        <p className="text-gray-600">DRT 지도 로딩 중...</p>
      </div>
    </div>
  )
})