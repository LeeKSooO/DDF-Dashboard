"use client"

import { DemandContent } from "../dashboard/demand-content"
import { Brain, HelpCircle, TrendingUp } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface DRTAnalysisContentProps {
  selectedMonth: string
  selectedRegion: string
  selectedModel: string
  setSelectedModel: (model: string) => void
  onDistrictChange?: (district: string) => void
}

export function DRTAnalysisContent({ 
  selectedMonth, 
  selectedRegion,
  selectedModel,
  setSelectedModel,
  onDistrictChange
}: DRTAnalysisContentProps) {
  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="h-6 w-6 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold">DRT 분석</h1>
            <p className="text-gray-600">수요응답형 교통 서비스 종합 분석</p>
          </div>
        </div>
        
        {/* DRT 필요성 진단 지표 - 간단 표시 */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg border border-blue-200 hover:bg-blue-100 transition-colors cursor-help">
                <TrendingUp className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-700">진단 지표</span>
                <HelpCircle className="h-4 w-4 text-blue-500" />
              </div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-md p-4">
              <div className="space-y-2">
                <div className="font-semibold text-sm">DRT 필요성 진단 지표</div>
                <div className="text-xs text-gray-600 space-y-1">
                  <div>🎯 <strong>점수 집중도:</strong> 상위 정류장들의 점수 비중</div>
                  <div>⚖️ <strong>점수 편차:</strong> 정류장 간 DRT 점수 표준편차</div>
                  <div>🔴🟢 <strong>고-저점수 비율:</strong> 평균 이상/이하 정류장 비율</div>
                </div>
                <div className="text-xs text-blue-600 mt-2">
                  💡 지역의 DRT 도입 효과성 및 필요성을 분석합니다
                </div>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* DRT 적합도 분석 */}
      <DemandContent
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        selectedMonth={selectedMonth}
        selectedRegion={selectedRegion}
        onDistrictChange={onDistrictChange}
      />
    </div>
  )
}