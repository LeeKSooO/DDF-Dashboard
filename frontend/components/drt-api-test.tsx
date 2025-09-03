"use client"

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiService, DRTScoreResponse, DRTModelType } from '@/lib/api'

export function DRTApiTest() {
  const [selectedDistrict, setSelectedDistrict] = useState<string>('강남구')
  const [selectedModel, setSelectedModel] = useState<DRTModelType>('commuter')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DRTScoreResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const testAPI = async () => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      console.log('Testing API with:', { selectedDistrict, selectedModel })
      
      const response = await apiService.getDRTScores(
        selectedDistrict, 
        selectedModel, 
        '2025-09-01'
      )
      
      console.log('API Response:', response)
      setResult(response)
    } catch (err) {
      console.error('API Error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const districts = [
    '강남구', '강서구', '관악구', '광진구', '마포구', 
    '서초구', '성동구', '송파구', '영등포구', '용산구'
  ]

  return (
    <div className="space-y-4 p-6">
      <Card>
        <CardHeader>
          <CardTitle>DRT API 테스트</CardTitle>
          <CardDescription>
            실제 DRT Score API와의 연결을 테스트합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium">구 선택</label>
              <Select value={selectedDistrict} onValueChange={setSelectedDistrict}>
                <SelectTrigger>
                  <SelectValue placeholder="구를 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  {districts.map((district) => (
                    <SelectItem key={district} value={district}>
                      {district}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex-1">
              <label className="text-sm font-medium">모델 타입</label>
              <Select value={selectedModel} onValueChange={(value) => setSelectedModel(value as DRTModelType)}>
                <SelectTrigger>
                  <SelectValue placeholder="모델을 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="commuter">출퇴근형</SelectItem>
                  <SelectItem value="tourism">관광형</SelectItem>
                  <SelectItem value="vulnerable">취약계층형</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button 
            onClick={testAPI} 
            disabled={loading}
            className="w-full"
          >
            {loading ? '테스트 중...' : 'API 테스트 실행'}
          </Button>

          {error && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader>
                <CardTitle className="text-red-600">에러 발생</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-red-700 font-mono text-sm">{error}</p>
              </CardContent>
            </Card>
          )}

          {result && (
            <Card className="border-green-200 bg-green-50">
              <CardHeader>
                <CardTitle className="text-green-600">API 응답 성공</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <strong>구명:</strong> {result.district_name}
                  </div>
                  <div>
                    <strong>모델:</strong> {result.model_type}
                  </div>
                  <div>
                    <strong>분석월:</strong> {result.analysis_month}
                  </div>
                  <div>
                    <strong>정류장 수:</strong> {result.stations.length}개
                  </div>
                </div>

                {result.top_stations.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-medium mb-2">Top 정류장:</h4>
                    <div className="space-y-1">
                      {result.top_stations.slice(0, 3).map((station, idx) => (
                        <div key={station.station_id} className="text-sm bg-white p-2 rounded border">
                          <strong>{idx + 1}.</strong> {station.station_name} 
                          <span className="ml-2 text-blue-600">
                            점수: {station.drt_score.toFixed(1)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <details className="mt-4">
                  <summary className="cursor-pointer font-medium">전체 응답 데이터 보기</summary>
                  <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-40">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </details>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>
    </div>
  )
}