"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MapPin, HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { memo } from "react";

interface AreaTypeAnalysisSectionProps {
  areaTypeData: any;
  animatedNumbers: Record<string, number>;
}

export const AreaTypeAnalysisSection = memo(({ areaTypeData, animatedNumbers }: AreaTypeAnalysisSectionProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MapPin className="h-5 w-5 text-purple-500" />
          지역 특성별 정류장 분석
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <HelpCircle className="h-4 w-4 text-purple-500 cursor-help" />
              </TooltipTrigger>
              <TooltipContent>
                <div className="max-w-sm">
                  <p className="font-medium mb-2">🏠 주거지역 vs 🏢 업무지역 구분 분석</p>
                  <ul className="text-sm space-y-1">
                    <li>• 출퇴근 승하차 패턴으로 지역 특성 파악</li>
                    <li>• 주거지역: 오전 승차↑, 오후 하차↑</li>
                    <li>• 업무지역: 오전 하차↑, 오후 승차↑</li>
                    <li>• 도시계획 및 교통정책 수립에 활용</li>
                  </ul>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </CardTitle>
        <CardDescription>출퇴근 승하차 패턴으로 주거지역과 업무지역 구분</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 주거지역 특성 정류장 */}
          <div className="p-4 bg-blue-50 rounded-lg">
            <h5 className="font-semibold text-lg text-blue-800 mb-3 flex items-center gap-2">
              🏠 주거지역 특성
            </h5>
            <div className="space-y-3 scrollable-list">
              {areaTypeData?.data?.residential_stations?.map((item: any, index: number) => (
                <div
                  key={item.station.station_id}
                  className="flex flex-col p-3 bg-white rounded-lg shadow-sm animate-slide-in border-l-4 border-l-blue-400"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-semibold text-base">{item.station.station_name}</div>
                      <div className="text-blue-600 font-semibold text-sm mt-1">
                        주거지 특성도: {item.imbalance_ratio?.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">오전 승차</span>
                      <span className="font-medium animate-count-up">
                        {(animatedNumbers[`residential-morning-${item.station.station_id}`] || 0).toLocaleString()}명
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-blue-400 to-blue-600 h-2 rounded-full animate-progress"
                        style={{ 
                          width: `${Math.min(100, (item.morning_ride || 0) / Math.max(...(areaTypeData?.data?.residential_stations?.map((s: any) => s.morning_ride) || [1])) * 100)}%`,
                          animationDelay: `${index * 100 + 200}ms`
                        }}
                      ></div>
                    </div>
                    
                    <div className="flex items-center justify-between mt-3">
                      <span className="text-sm text-gray-600">오후 하차</span>
                      <span className="font-medium animate-count-up">
                        {(animatedNumbers[`residential-evening-${item.station.station_id}`] || 0).toLocaleString()}명
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-blue-500 to-blue-700 h-2 rounded-full animate-progress"
                        style={{ 
                          width: `${Math.min(100, (item.evening_alight || 0) / Math.max(...(areaTypeData?.data?.residential_stations?.map((s: any) => s.evening_alight) || [1])) * 100)}%`,
                          animationDelay: `${index * 100 + 300}ms`
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              )) || (
                <div className="text-center text-gray-500 py-4">데이터를 불러오는 중...</div>
              )}
            </div>
          </div>

          {/* 업무지역 특성 정류장 */}
          <div className="p-4 bg-green-50 rounded-lg">
            <h5 className="font-semibold text-lg text-green-800 mb-3 flex items-center gap-2">
              🏢 업무지역 특성
            </h5>
            <div className="space-y-3 scrollable-list">
              {areaTypeData?.data?.business_stations?.map((item: any, index: number) => (
                <div
                  key={item.station.station_id}
                  className="flex flex-col p-3 bg-white rounded-lg shadow-sm animate-slide-in border-l-4 border-l-green-400"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-semibold text-base">{item.station.station_name}</div>
                      <div className="text-green-600 font-semibold text-sm mt-1">
                        업무지 특성도: {item.imbalance_ratio?.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">오전 하차</span>
                      <span className="font-medium animate-count-up">
                        {(animatedNumbers[`business-morning-${item.station.station_id}`] || 0).toLocaleString()}명
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-green-400 to-green-600 h-2 rounded-full animate-progress"
                        style={{ 
                          width: `${Math.min(100, (item.morning_alight || 0) / Math.max(...(areaTypeData?.data?.business_stations?.map((s: any) => s.morning_alight) || [1])) * 100)}%`,
                          animationDelay: `${index * 100 + 200}ms`
                        }}
                      ></div>
                    </div>
                    
                    <div className="flex items-center justify-between mt-3">
                      <span className="text-sm text-gray-600">오후 승차</span>
                      <span className="font-medium animate-count-up">
                        {(animatedNumbers[`business-evening-${item.station.station_id}`] || 0).toLocaleString()}명
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-green-500 to-green-700 h-2 rounded-full animate-progress"
                        style={{ 
                          width: `${Math.min(100, (item.evening_ride || 0) / Math.max(...(areaTypeData?.data?.business_stations?.map((s: any) => s.evening_ride) || [1])) * 100)}%`,
                          animationDelay: `${index * 100 + 300}ms`
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              )) || (
                <div className="text-center text-gray-500 py-4">데이터를 불러오는 중...</div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
});

AreaTypeAnalysisSection.displayName = "AreaTypeAnalysisSection";