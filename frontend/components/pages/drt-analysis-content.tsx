"use client"

import { DemandContent } from "../dashboard/demand-content"
import { Brain } from "lucide-react"

interface DRTAnalysisContentProps {
  selectedMonth: string
  selectedRegion: string
  selectedModel: string
  setSelectedModel: (model: string) => void
}

export function DRTAnalysisContent({ 
  selectedMonth, 
  selectedRegion,
  selectedModel,
  setSelectedModel
}: DRTAnalysisContentProps) {
  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Brain className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold">DRT 분석</h1>
          <p className="text-gray-600">수요응답형 교통 서비스 종합 분석</p>
        </div>
      </div>

      {/* DRT 적합도 분석 */}
      <DemandContent
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        selectedMonth={selectedMonth}
        selectedRegion={selectedRegion}
      />
    </div>
  )
}