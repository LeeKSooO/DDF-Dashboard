"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { memo, useState, useEffect } from "react";
import { apiService, DRTScoreResponse, DRTModelType, DRTStationData, DRTStationDetailResponse } from "@/lib/api";
import { ModelSuitabilityMap } from "@/components/map/model-suitability-map";

// 모델 타입 매핑
const modelTypeMapping: Record<string, DRTModelType> = {
  교통취약지: "vulnerable",
  출퇴근: "commuter",
  관광형: "tourism",
};

// 모델 정보
const mstGcnModels = [
  { model: "교통취약지", icon: "🏘️", accuracy: 97.2 },
  { model: "출퇴근", icon: "🏢", accuracy: 94.8 },
  { model: "관광형", icon: "🗽", accuracy: 91.5 },
];

interface DemandContentProps {
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  selectedMonth: string;
  selectedRegion: string;
}

export const DemandContent = memo(function DemandContent({
  selectedModel,
  setSelectedModel,
  selectedMonth,
  selectedRegion,
}: DemandContentProps) {
  const [drtData, setDrtData] = useState<DRTScoreResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDistrictName, setSelectedDistrictName] = useState<string>("");
  const [selectedStation, setSelectedStation] = useState<DRTStationData | null>(null);
  const [stationDetail, setStationDetail] = useState<DRTStationDetailResponse | null>(null);
  const [loadingStationDetail, setLoadingStationDetail] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // 구별 DRT 데이터 로드
  useEffect(() => {
    const loadDRTData = async () => {
      try {
        setLoading(true);
        const apiModelType = modelTypeMapping[selectedModel] || "vulnerable";
        const targetRegion = selectedRegion === "전체" ? "강남구" : selectedRegion;
        
        console.log("🔄 Loading DRT data:", { selectedModel, apiModelType, targetRegion });
        
        const response = await apiService.getDRTScores(
          targetRegion,
          apiModelType,
          "2025-07-01"
        );
        
        console.log("📊 DRT API response:", response);
        setDrtData(response);
        setSelectedDistrictName(targetRegion);
        
        // 모델 변경이든 초기 로드든, 정류장이 있으면 default 설정
        if (response.stations && response.stations.length > 0) {
          const sortedStations = [...response.stations].sort((a, b) => b.drt_score - a.drt_score);
          const defaultStation = sortedStations[0];
          console.log("🚏 Setting default station:", defaultStation.station_name, "Score:", defaultStation.drt_score, "Model:", selectedModel);
          setSelectedStation(defaultStation);
          
          if (isInitialLoad) {
            setIsInitialLoad(false);
          }
        } else {
          // 정류장이 없으면 선택 초기화
          setSelectedStation(null);
          setStationDetail(null);
        }
      } catch (err) {
        console.error("🚨 DRT API error:", err);
      } finally {
        setLoading(false);
      }
    };

    loadDRTData();
  }, [selectedModel, selectedRegion]);

  // 정류장 상세 정보 로드
  useEffect(() => {
    if (!selectedStation) {
      setStationDetail(null);
      return;
    }
    
    const loadStationDetail = async () => {
      try {
        setLoadingStationDetail(true);
        const apiModelType = modelTypeMapping[selectedModel] || "vulnerable";
        const detail = await apiService.getStationDetail(
          selectedStation.station_id,
          apiModelType,
          "2025-07-01"
        );
        setStationDetail(detail);
      } catch (err) {
        console.error("🚨 Failed to load station detail:", err);
        setStationDetail(null);
      } finally {
        setLoadingStationDetail(false);
      }
    };
    
    loadStationDetail();
  }, [selectedStation, selectedModel]);

  // 정류장별 특성 점수 계산 (실제 API feature_scores 기반)
  const getStationCharacteristics = () => {
    if (!stationDetail) return null;
    
    const { feature_scores, peak_score, monthly_average } = stationDetail;
    
    if (selectedModel === "교통취약지") {
      return {
        title: "교통취약지 특성 분석",
        items: [
          { 
            label: "취약 접근성 비율 (VAR)", 
            score: (feature_scores.var_t_score * 100).toFixed(1),
            description: "특정 시간 배차수/취약시간대 총 배차수",
            level: feature_scores.var_t_score > 0.3 ? "높음" : feature_scores.var_t_score > 0.15 ? "보통" : "낮음"
          },
          { 
            label: "사회 형평성 수요 (SED)", 
            score: (feature_scores.sed_t_score * 100).toFixed(1),
            description: "취약시간대 승하차 수요 비율",
            level: feature_scores.sed_t_score > 0.25 ? "높음" : feature_scores.sed_t_score > 0.12 ? "보통" : "낮음"
          },
          { 
            label: "이동성 불리 지수 (MDI)", 
            score: (feature_scores.mdi_t_score * 100).toFixed(1),
            description: "구간별 승하차수 부족도 (역전 지수)",
            level: feature_scores.mdi_t_score > 0.7 ? "높음" : feature_scores.mdi_t_score > 0.5 ? "보통" : "낮음"
          },
          { 
            label: "지역 취약성 점수 (AVS)", 
            score: (feature_scores.avs_score * 100).toFixed(1),
            description: "POI 카테고리별 취약성 점수",
            level: feature_scores.avs_score > 0.8 ? "높음" : feature_scores.avs_score > 0.6 ? "보통" : "낮음"
          },
        ]
      };
    } else if (selectedModel === "출퇴근") {
      return {
        title: "출퇴근형 특성 분석",
        items: [
          { 
            label: "시간 집중도 지수 (TC)", 
            score: (feature_scores.tc_score * 100).toFixed(1),
            description: "t시 배차수/일일 최대 배차수",
            level: feature_scores.tc_score > 0.8 ? "매우 높음" : feature_scores.tc_score > 0.6 ? "높음" : "보통"
          },
          { 
            label: "피크 수요 비율 (PDR)", 
            score: (feature_scores.pdr_score * 100).toFixed(1),
            description: "t시 승하차수/일일 최대 승하차수",
            level: feature_scores.pdr_score >= 1.0 ? "최대치" : feature_scores.pdr_score > 0.8 ? "매우 높음" : feature_scores.pdr_score > 0.6 ? "높음" : "보통"
          },
          { 
            label: "노선 활용도 (RU)", 
            score: (feature_scores.ru_score * 100).toFixed(1),
            description: "시간별 구간 승하차수/1000",
            level: feature_scores.ru_score > 0.05 ? "높음" : feature_scores.ru_score > 0.02 ? "보통" : "낮음"
          },
          { 
            label: "POI 카테고리 가중치 (PCW)", 
            score: (feature_scores.pcw_score * 100).toFixed(1),
            description: "인구밀집지역·발달상권 가중치",
            level: feature_scores.pcw_score >= 1.0 ? "최우수" : feature_scores.pcw_score >= 0.8 ? "우수" : "보통"
          },
        ]
      };
    } else {
      return {
        title: "관광특화형 특성 분석",
        items: [
          { 
            label: "관광 집중도 (TC)", 
            score: (feature_scores.tc_t_score * 100).toFixed(1),
            description: "t시 배차수/일일 최대 (10-16시 가중치 1.2)",
            level: feature_scores.tc_t_score > 0.9 ? "매우 높음" : feature_scores.tc_t_score > 0.7 ? "높음" : "보통"
          },
          { 
            label: "관광 수요 비율 (TDR)", 
            score: (feature_scores.tdr_t_score * 100).toFixed(1),
            description: "t시 승하차수/일일 최대 (10-16시 가중치 1.1)",
            level: feature_scores.tdr_t_score >= 1.0 ? "최대치" : feature_scores.tdr_t_score > 0.8 ? "매우 높음" : feature_scores.tdr_t_score > 0.6 ? "높음" : "보통"
          },
          { 
            label: "구간 이용률 (RU)", 
            score: (feature_scores.ru_t_score * 100).toFixed(1),
            description: "t시 구간별 승객 밀도 (관광시간 60%)",
            level: feature_scores.ru_t_score > 0.15 ? "높음" : feature_scores.ru_t_score > 0.1 ? "보통" : "낮음"
          },
          { 
            label: "POI 관광 가중치 (PCW)", 
            score: (feature_scores.pcw_score * 100).toFixed(1),
            description: "관광특구>고궁>상권>공원 가중치",
            level: feature_scores.pcw_score >= 1.0 ? "관광특구급" : feature_scores.pcw_score >= 0.8 ? "문화유적급" : "일반급"
          },
        ]
      };
    }
  };

  // 시간대별 데이터 포맷팅
  const getHourlyChartData = () => {
    if (!stationDetail?.hourly_scores) return [];
    
    return stationDetail.hourly_scores.map(item => ({
      hour: `${item.hour}시`,
      score: item.score,
      평균: stationDetail.monthly_average,
    }));
  };

  const stationCharacteristics = getStationCharacteristics();

  return (
    <div className="space-y-6">
      {/* 상단: 모델 선택 + 지도 */}
      <div className="grid grid-cols-6 gap-6">
        {/* 모델 선택 (1/6) */}
        <div className="col-span-1">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">모델 선택</CardTitle>
              <CardDescription className="text-base">
                DRT 운영 모델
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {mstGcnModels.map((model) => {
                  const isSelected = selectedModel === model.model;
                  return (
                    <button
                      key={model.model}
                      onClick={() => setSelectedModel(model.model)}
                      className={`w-full p-3 text-base font-medium rounded-lg transition-all ${
                        isSelected
                          ? "bg-blue-600 text-white shadow-md"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span className="text-lg">{model.icon}</span>
                        <span>{model.model}</span>
                        <span className="text-base opacity-75">
                          정확도 {model.accuracy}%
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 지도 (5/6) */}
        <div className="col-span-5">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>정류장별 DRT 적합성 지도</CardTitle>
              <CardDescription>
                구를 클릭하여 정류장을 표시하고, 정류장을 클릭하여 상세 분석을 확인하세요
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModelSuitabilityMap
                selectedModel={selectedModel}
                initialDistrictName={selectedDistrictName}
                onDistrictAnalysis={(districtName, analysis) => {
                  console.log("🔄 DemandContent received analysis:", { districtName, analysis });
                  
                  if (analysis.stationName && analysis.stationData) {
                    // 지도에서 직접 전달받은 정류장 데이터 사용
                    console.log("🚏 Using station data from map:", analysis.stationData);
                    setSelectedStation(analysis.stationData);
                    console.log("✅ Station set:", analysis.stationData.station_name);
                  } else if (analysis.stationName) {
                    // 기존 로직: drtData에서 찾기
                    const station = drtData?.stations.find(
                      s => s.station_name === analysis.stationName
                    );
                    console.log("🚏 Found station in drtData:", station);
                    if (station) {
                      setSelectedStation(station);
                      console.log("✅ Station set:", station.station_name);
                    } else {
                      console.log("❌ Station not found in current drtData");
                    }
                  }
                  setSelectedDistrictName(districtName);
                }}
              />
              {drtData && (
                <CardDescription className="mt-4">
                  {drtData.stations.length}개 정류장 표시 중
                </CardDescription>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 하단: 모델별 특성 분석 + 시계열 그래프 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 모델별 특성 분석 (정류장 기준) */}
        <Card>
          <CardHeader>
            <CardTitle>정류장 특성 분석</CardTitle>
            <CardDescription>
              {selectedStation 
                ? `${selectedStation.station_name} 정류장의 ${selectedModel} 모델 특성`
                : "정류장을 선택하여 특성을 분석하세요"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedStation && stationDetail ? (
              <div className="space-y-4">
                {loadingStationDetail ? (
                  <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  </div>
                ) : stationCharacteristics ? (
                  <>
                    <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                      <h4 className="font-medium mb-3 flex items-center gap-2">
                        🎯 {stationCharacteristics.title}
                      </h4>
                      <div className="space-y-3">
                        {stationCharacteristics.items.map((item, idx) => (
                          <div key={idx} className="bg-white p-3 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <div>
                                <div className="font-medium text-base">{item.label}</div>
                                <div className="text-base text-gray-500">{item.description}</div>
                              </div>
                              <div className="text-right">
                                <div className="text-lg font-bold text-blue-600">
                                  {item.score}점
                                </div>
                                <Badge variant={
                                  item.level.includes("매우 높음") || item.level.includes("최우수") || item.level.includes("관광특구급") ? "default" : 
                                  item.level.includes("높음") || item.level.includes("우수") || item.level.includes("문화유적급") ? "secondary" : 
                                  item.level.includes("보통") || item.level.includes("일반급") ? "outline" : 
                                  "secondary"
                                }>
                                  {item.level}
                                </Badge>
                              </div>
                            </div>
                            <Progress 
                              value={parseFloat(item.score)} 
                              className={`h-2 ${
                                selectedModel === "교통취약지" ? "progress-purple" : 
                                selectedModel === "출퇴근" ? "progress-blue" : 
                                "progress-green"
                              }`}
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-3 bg-green-50 rounded-lg">
                      <div className="text-base font-medium text-green-800 mb-1">
                        종합 DRT 적합도
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="text-2xl font-bold text-green-600">
                          {stationDetail.current_score.toFixed(1)}점
                        </div>
                        <div className="text-base text-green-700">
                          피크: {stationDetail.peak_hour}시 ({stationDetail.peak_score.toFixed(1)}점)
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <div className="text-4xl mb-3">📊</div>
                  <div>지도에서 정류장을 클릭하면</div>
                  <div>해당 정류장의 특성을 분석합니다</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 시계열 그래프 */}
        <Card>
          <CardHeader>
            <CardTitle>시간대별 DRT 점수</CardTitle>
            <CardDescription>
              {selectedStation && stationDetail
                ? `${selectedStation.station_name} 정류장의 24시간 DRT 점수 변화`
                : "정류장을 선택하여 시간대별 패턴을 확인하세요"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedStation && stationDetail ? (
              <div className="space-y-4">
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={getHourlyChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="hour" 
                      tick={{ fontSize: 11 }}
                      interval={2}
                    />
                    <YAxis 
                      tick={{ fontSize: 11 }}
                      domain={[0, 100]}
                    />
                    <Tooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="score" 
                      stroke="#3b82f6" 
                      strokeWidth={2}
                      name="DRT 점수"
                      dot={{ r: 3 }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="평균" 
                      stroke="#ef4444" 
                      strokeDasharray="5 5"
                      strokeWidth={1}
                      name="일평균"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>

                <div className="grid grid-cols-3 gap-3 text-base">
                  <div className="text-center p-2 bg-blue-50 rounded">
                    <div className="text-base text-blue-600">현재 점수</div>
                    <div className="font-bold text-blue-700">
                      {stationDetail.current_score.toFixed(1)}점
                    </div>
                  </div>
                  <div className="text-center p-2 bg-green-50 rounded">
                    <div className="text-base text-green-600">피크 시간</div>
                    <div className="font-bold text-green-700">
                      {stationDetail.peak_hour}시
                    </div>
                  </div>
                  <div className="text-center p-2 bg-purple-50 rounded">
                    <div className="text-base text-purple-600">일평균</div>
                    <div className="font-bold text-purple-700">
                      {stationDetail.monthly_average.toFixed(1)}점
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <div className="text-4xl mb-3">📈</div>
                  <div>지도에서 정류장을 클릭하면</div>
                  <div>24시간 DRT 점수 변화를 확인할 수 있습니다</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
});