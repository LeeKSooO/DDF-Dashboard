"use client"

import { useEffect, useRef, useState, useMemo } from 'react'
import dynamic from 'next/dynamic'

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

interface TrafficData {
  district_name: string
  total_traffic: number
}

interface SeoulMapProps {
  onDistrictClick?: (districtName: string, districtCode: string) => void
  selectedDistrict?: string
  trafficData?: TrafficData[] // API에서 받은 교통량 데이터 배열
}

function SeoulMapComponent({ onDistrictClick, selectedDistrict, trafficData = [] }: SeoulMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isClient, setIsClient] = useState(false)

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

  // Convert API traffic data array to lookup map for performance
  const trafficLookup = useMemo(() => {
    const lookup: Record<string, number> = {}
    console.log('🗺️ Map trafficData received:', trafficData.length, 'districts')
    trafficData.forEach(item => {
      console.log('🗺️ Adding to lookup:', item.district_name, '=', item.total_traffic)
      lookup[item.district_name] = item.total_traffic
    })
    console.log('🗺️ Final trafficLookup:', Object.keys(lookup).length, 'entries')
    return lookup
  }, [trafficData])

  // Traffic colors based on volume (similar to reference image)
  const getTrafficColor = (traffic: number): string => {
    if (traffic > 500000) return '#FF5722' // Red - Heavy traffic
    if (traffic > 300000) return '#FF9800' // Orange 
    if (traffic > 200000) return '#FFC107' // Yellow
    if (traffic > 100000) return '#4CAF50' // Green
    if (traffic > 50000) return '#2196F3'  // Blue
    if (traffic > 20000) return '#9C27B0'  // Purple
    return '#607D8B' // Gray - Low traffic
  }

  // Style function for districts
  const getFeatureStyle = (feature: any) => {
    const districtName = feature.properties.sggnm
    const traffic = trafficLookup[districtName] || 0
    const isSelected = selectedDistrict === districtName
    
    // Debug logging for traffic lookup
    if (traffic === 0) {
      console.log('🚨 Zero traffic found for district:', {
        districtName,
        availableInLookup: Object.keys(trafficLookup).includes(districtName),
        lookupKeys: Object.keys(trafficLookup).slice(0, 5),
        traffic
      })
    }

    return {
      fillColor: getTrafficColor(traffic),
      weight: isSelected ? 3 : 2,
      opacity: 1,
      color: isSelected ? '#2196F3' : '#ffffff',
      dashArray: '',
      fillOpacity: 0.7
    }
  }

  useEffect(() => {
    if (!isClient || !L || !mapRef.current || mapInstanceRef.current) return

    // Initialize map with CartoDB Positron style and Seoul bounds constraints
    const map = L.map(mapRef.current, {
      center: seoulBounds,
      zoom: 11,
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
        
        // Add all district features to map (already simplified)
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
                  color: '#2196F3',
                  fillOpacity: 0.9
                })
                layer.bringToFront()
              },
              mouseout: (e: any) => {
                const layer = e.target
                layer.setStyle(getFeatureStyle(feature))
              },
              click: (_e: any) => {
                const districtName = feature.properties.sggnm
                const districtCode = feature.properties.sgg
                
                // Zoom to district
                map.fitBounds(layer.getBounds())
                
                // Call callback
                if (onDistrictClick) {
                  onDistrictClick(districtName, districtCode)
                }
              }
            })

            // Tooltip - will be updated dynamically when traffic data changes
            layer.bindTooltip(
              `<div>
                <strong>${districtName}</strong><br/>
                교통량: 로딩 중...
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
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [isClient])

  // Update styles and tooltips when traffic data changes
  useEffect(() => {
    if (!isClient || !L || !mapInstanceRef.current) return

    console.log('🔄 Updating map styles and tooltips with traffic data')

    mapInstanceRef.current.eachLayer((layer: any) => {
      if (layer instanceof L.GeoJSON) {
        layer.eachLayer((featureLayer: any) => {
          if (featureLayer instanceof L.Path) {
            const feature = featureLayer.feature
            if (feature) {
              // Update style
              featureLayer.setStyle(getFeatureStyle(feature))
              
              // Update tooltip content with current traffic data
              const districtName = feature.properties.sggnm
              const trafficValue = trafficLookup[districtName] || 0
              
              console.log('🏷️ Updating tooltip for', districtName, '- traffic value:', trafficValue)
              
              featureLayer.setTooltipContent(
                `<div>
                  <strong>${districtName}</strong><br/>
                  교통량: ${trafficValue.toLocaleString()}명
                </div>`
              )
            }
          }
        })
      }
    })
  }, [trafficLookup, selectedDistrict, isClient, getFeatureStyle])

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
        className="h-[400px] rounded-lg border"
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

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg text-base z-20">
        <div className="font-medium mb-2">교통량 범례</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#FF5722] rounded-sm"></div>
            <span>50만명 이상</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#FF9800] rounded-sm"></div>
            <span>30-50만명</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#FFC107] rounded-sm"></div>
            <span>20-30만명</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#4CAF50] rounded-sm"></div>
            <span>10-20만명</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#2196F3] rounded-sm"></div>
            <span>5-10만명</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#9C27B0] rounded-sm"></div>
            <span>2-5만명</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 bg-[#607D8B] rounded-sm"></div>
            <span>2만명 미만</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Export as dynamic component to prevent SSR issues
export const SeoulMap = dynamic(() => Promise.resolve(SeoulMapComponent), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] bg-gray-100 rounded-lg flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
        <p className="text-gray-600">지도 로딩 중...</p>
      </div>
    </div>
  )
})