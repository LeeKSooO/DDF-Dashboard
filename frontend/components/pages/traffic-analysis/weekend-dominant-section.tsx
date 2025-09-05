"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { memo } from "react";

interface WeekendDominantSectionProps {
  weekendData: any;
  animatedNumbers: Record<string, number>;
}

export const WeekendDominantSection = memo(({ weekendData, animatedNumbers }: WeekendDominantSectionProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-blue-500" />
          주말 우세 정류장
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <HelpCircle className="h-4 w-4 text-blue-500 cursor-help" />
              </TooltipTrigger>
              <TooltipContent>
                <div className="max-w-sm">
                  <p className="font-medium mb-2">🎯 주말 특화 교통 수요 지역</p>
                  <ul className="text-sm space-y-1">
                    <li>• 토요일, 일요일 교통량이 평일 대비 높음</li>
                    <li>• 관광지, 레저시설, 대형 쇼핑몰 인근</li>
                    <li>• 주말 전용 노선 또는 증편 검토 대상</li>
                    <li>• 여가활동 중심의 교통패턴</li>
                    <li>• 구평균 대비 배수로 중요도 측정</li>
                  </ul>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </CardTitle>
        <CardDescription>주말 수요가 높은 관광/레저 지역</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4 scrollable-list">
          {weekendData?.data?.map((item: any, index: number) => (
            <div
              key={item.station.station_id}
              className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg animate-slide-in border-l-4 border-l-blue-500"
              style={{ animationDelay: `${index * 120}ms` }}
            >
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">#{item.rank}</div>
                </div>
                <div>
                  <h4 className="font-semibold text-base">{item.station.station_name}</h4>
                  <p className="text-base text-gray-600 mt-1">
                    주말 교통량:{" "}
                    <span className="font-medium animate-count-up">
                      {(animatedNumbers[`weekend-${item.station.station_id}`] || 0).toLocaleString()}명
                    </span>
                  </p>
                </div>
              </div>
              <div className="text-right">
                <Badge variant="secondary" className="text-base px-3 py-1">
                  {item.vs_district_avg?.toFixed(1)}X
                </Badge>
                <p className="text-sm text-gray-600 mt-1">구평균 대비</p>
              </div>
            </div>
          )) || (
            <div className="text-center text-gray-500 py-8">데이터를 불러오는 중...</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

WeekendDominantSection.displayName = "WeekendDominantSection";