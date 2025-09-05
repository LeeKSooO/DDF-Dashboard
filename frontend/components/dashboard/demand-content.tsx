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
import { Search, Brain } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { memo, useState, useEffect } from "react";
import { apiService, DRTScoreResponse, DRTModelType, DRTStationData, DRTStationDetailResponse, utils } from "@/lib/api";
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
  onDistrictChange?: (district: string) => void;
}

export const DemandContent = memo(function DemandContent({
  selectedModel,
  setSelectedModel,
  selectedMonth,
  selectedRegion,
  onDistrictChange,
}: DemandContentProps) {
  const [drtData, setDrtData] = useState<DRTScoreResponse | null>(null);
  const [selectedDistrictName, setSelectedDistrictName] = useState<string>("");
  const [selectedStation, setSelectedStation] = useState<DRTStationData | null>(null);
  const [stationDetail, setStationDetail] = useState<DRTStationDetailResponse | null>(null);
  const [loadingStationDetail, setLoadingStationDetail] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<DRTStationData[]>([]);
  const [allStationsData, setAllStationsData] = useState<DRTStationData[]>([]);

  // 구별 DRT 데이터 로드
  useEffect(() => {
    const loadDRTData = async () => {
      try {
        const apiModelType = modelTypeMapping[selectedModel] || "vulnerable";
        let targetRegion = selectedRegion;
        let response;
        let didFallback = false; // fallback 발생 여부 추적
        
        console.log("🔄 Loading DRT data:", { selectedModel, apiModelType, selectedRegion, targetRegion });
        
        if (selectedRegion === "전체") {
          // "전체" 선택 시 - API가 "전체"를 지원하는지 먼저 시도
          try {
            response = await apiService.getDRTScores(
              "전체",
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
            console.log("✅ API supports '전체' region");
          } catch (error) {
            // "전체"를 지원하지 않으면 강남구를 기본값으로 사용
            console.log("⚠️ API doesn't support '전체', falling back to 강남구");
            targetRegion = "강남구";
            didFallback = true;
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
          }
        } else {
          console.log("🌍 Requesting DRT data for specific region:", targetRegion);
          try {
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
            console.log("✅ Successfully got DRT data for", targetRegion, "- stations count:", response?.stations?.length || 0);
          } catch (regionError) {
            console.error("🚨 Failed to get DRT data for", targetRegion, "Error:", regionError);
            console.log("🔄 Falling back to 강남구 for DRT data");
            
            // 해당 구의 데이터가 없으면 강남구로 fallback
            targetRegion = "강남구";
            didFallback = true;
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
            console.log("✅ Fallback successful - using 강남구 data");
          }
        }
        
        console.log("📊 Final DRT API response:", {
          selectedRegion,
          targetRegion, 
          stationCount: response?.stations?.length || 0,
          firstStation: response?.stations?.[0]?.station_name || "None"
        });
        setDrtData(response);
        
        // 구 이름 업데이트 로직 개선
        if (didFallback) {
          // Fallback이 발생한 경우에만 구 이름을 변경 (사용자가 요청한 구가 없는 경우)
          console.log("🏢 Fallback occurred, updating district name to:", targetRegion);
          setSelectedDistrictName(targetRegion);
        } else if (!selectedDistrictName || selectedDistrictName === "") {
          // 초기 로드인 경우에만 구 이름 설정
          console.log("🏢 Initial load, setting district name to:", targetRegion);
          setSelectedDistrictName(targetRegion);
        } else {
          // 사용자가 이미 구를 선택한 상태에서 모델만 변경하는 경우 구 이름 유지
          console.log("🔒 Preserving current district selection:", selectedDistrictName, "for model:", selectedModel);
        }
        
        // 정류장 선택 처리 - fallback 발생 여부에 따라 다르게 처리
        if (response.stations && response.stations.length > 0) {
          const sortedStations = [...response.stations].sort((a, b) => b.drt_score - a.drt_score);
          
          if (didFallback) {
            // Fallback이 발생한 경우 - 사용자가 선택한 구가 아니므로 무조건 기본값으로 설정
            const defaultStation = sortedStations[0];
            console.log("🔄 District fallback occurred - setting default station:", defaultStation.station_name, "Score:", defaultStation.drt_score);
            setSelectedStation(defaultStation);
          } else {
            // 정상적으로 요청한 구 데이터인 경우 - 기존 로직 유지
            const currentSelectedInNewData = selectedStation && response.stations.find(
              s => s.station_id === selectedStation.station_id
            );
            
            if (currentSelectedInNewData) {
              // 현재 선택된 정류장이 새 데이터에 있으면 유지 (새로운 DRT 점수로 업데이트)
              console.log("🔄 Keeping current station:", currentSelectedInNewData.station_name, "New Score:", currentSelectedInNewData.drt_score);
              setSelectedStation(currentSelectedInNewData);
            } else if (isInitialLoad || !selectedStation) {
              // 초기 로드이거나 선택된 정류장이 없으면 기본값 설정
              const defaultStation = sortedStations[0];
              console.log("🚏 Setting default station:", defaultStation.station_name, "Score:", defaultStation.drt_score, "Model:", selectedModel);
              setSelectedStation(defaultStation);
            } else {
              // 현재 선택된 정류장이 새 데이터에 없는 경우
              // 1. 같은 이름의 정류장을 찾아서 업데이트
              const sameNameStation = response.stations.find(s => s.station_name === selectedStation.station_name);
              if (sameNameStation) {
                console.log("🔄 Found same name station with new model data:", sameNameStation.station_name, "New Score:", sameNameStation.drt_score);
                setSelectedStation(sameNameStation);
              } else {
                // 2. 같은 이름도 없으면 사용자 선택을 유지 (모델 변경으로 인한 자동 변경 방지)
                console.log("🔒 Preserving user-selected station despite model change:", selectedStation.station_name, "Model:", selectedModel);
                // 기존 선택된 정류장 객체는 유지하고, 상세 데이터만 새로 로드하도록 함
                // 이렇게 하면 사용자가 선택한 정류장이 모델 변경으로 인해 바뀌지 않음
              }
            }
          }
          
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
        // Loading state removed
      }
    };

    loadDRTData();
  }, [selectedModel, selectedRegion, selectedMonth]);

  // 전체 정류장 데이터 로드 (검색용)
  useEffect(() => {
    const loadAllStationsData = async () => {
      try {
        console.log("🔍 Loading all stations data for search");
        const apiModelType = modelTypeMapping[selectedModel] || "vulnerable";
        
        // "전체" 구역으로 API 호출 시도
        const response = await apiService.getDRTScores(
          "전체", 
          apiModelType, 
          utils.formatSelectedMonth(selectedMonth)
        );
        
        console.log("📊 All stations loaded for search:", response.stations?.length || 0);
        setAllStationsData(response.stations || []);
      } catch (err) {
        console.log("⚠️ Failed to load all stations data, using current district data for search");
        // 전체 데이터를 가져올 수 없으면 현재 구 데이터 사용
        setAllStationsData(drtData?.stations || []);
      }
    };

    loadAllStationsData();
  }, [selectedModel, selectedMonth]);

  // 상단 헤더에 현재 선택된 구 알리기 (DRT 분석 탭 전용)
  useEffect(() => {
    if (onDistrictChange && selectedDistrictName && selectedDistrictName !== "") {
      console.log("📤 Notifying header about district change:", selectedDistrictName);
      onDistrictChange(selectedDistrictName);
    }
  }, [selectedDistrictName, onDistrictChange]);

  // 정류장 상세 정보 로드
  useEffect(() => {
    if (!selectedStation) {
      console.log("🔍 No selected station, clearing detail");
      setStationDetail(null);
      return;
    }
    
    console.log("🔄 Loading station detail for:", selectedStation.station_name, "ID:", selectedStation.station_id);
    
    const loadStationDetail = async () => {
      try {
        setLoadingStationDetail(true);
        const apiModelType = modelTypeMapping[selectedModel] || "vulnerable";
        
        console.log("📡 Calling API with:", {
          station_id: selectedStation.station_id,
          model: apiModelType,
          month: utils.formatSelectedMonth(selectedMonth)
        });
        
        const detail = await apiService.getStationDetail(
          selectedStation.station_id,
          apiModelType,
          utils.formatSelectedMonth(selectedMonth)
        );
        
        console.log("✅ Station detail loaded:", detail);
        setStationDetail(detail);
      } catch (err) {
        console.error("🚨 Failed to load station detail:", err);
        setStationDetail(null);
      } finally {
        setLoadingStationDetail(false);
      }
    };
    
    loadStationDetail();
  }, [selectedStation?.station_id, selectedModel, selectedMonth]); // station_id로 변경하여 더 정확한 추적

  // 검색 기능
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    // 전체 데이터가 있으면 사용, 없으면 현재 구 데이터 사용
    const searchData = allStationsData.length > 0 ? allStationsData : (drtData?.stations || []);
    
    if (searchData.length === 0) {
      setSearchResults([]);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = searchData.filter(station => 
      station.station_name.toLowerCase().includes(query) ||
      station.station_id.toLowerCase().includes(query)
    );
    
    console.log("🔍 Search results for:", searchQuery, "Found:", filtered.length, "Search scope:", allStationsData.length > 0 ? "전체" : "현재 구");
    setSearchResults(filtered.slice(0, 8)); // 전체 검색이므로 최대 8개까지 표시
  }, [searchQuery, allStationsData, drtData?.stations]);

  // 검색 결과에서 정류장 선택
  const handleSearchResultSelect = (station: DRTStationData) => {
    console.log("🚏 Selected station from search:", station.station_name);
    setSelectedStation(station);
    setStationDetail(null); // 상세 정보 새로 로드
    setSearchQuery(""); // 검색창 초기화
    setSearchResults([]); // 검색 결과 닫기
  };

  // 정류장별 특성 점수 계산 (실제 API feature_scores 기반)
  const getStationCharacteristics = () => {
    if (!stationDetail) return null;
    
    const { feature_scores } = stationDetail;
    
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
      <div className="grid grid-cols-12 gap-4">
        {/* 모델 선택 (1/12) */}
        <div className="col-span-1">
          <Card className="h-fit shadow-lg border-0 bg-gradient-to-br from-gray-50 to-slate-100">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base font-bold text-gray-800">
                <Brain className="h-5 w-5 text-blue-600" />
                DRT 모델
              </CardTitle>
              <CardDescription className="text-sm text-gray-600">
                수요응답형 교통 모델
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                <TooltipProvider>
                  {mstGcnModels.map((model) => {
                    const isSelected = selectedModel === model.model;
                    const modelColors: Record<string, { bg: string; hover: string; border: string }> = {
                      "교통취약지": { bg: "bg-red-600", hover: "hover:bg-red-50", border: "border-red-200" },
                      "출퇴근": { bg: "bg-blue-600", hover: "hover:bg-blue-50", border: "border-blue-200" },
                      "관광형": { bg: "bg-green-600", hover: "hover:bg-green-50", border: "border-green-200" }
                    };
                    const colors = modelColors[model.model] || { bg: "bg-gray-600", hover: "hover:bg-gray-50", border: "border-gray-200" };
                    
                    return (
                      <Tooltip key={model.model}>
                        <TooltipTrigger asChild>
                          <button
                            onClick={() => setSelectedModel(model.model)}
                            className={`w-full py-3 px-4 text-base font-bold rounded transition-all ${
                              isSelected
                                ? `${colors.bg} text-white`
                                : `bg-white text-gray-700 ${colors.hover} border ${colors.border}`
                            }`}
                          >
                            <div className="flex flex-col items-center gap-1">
                              <span className="text-lg">{model.icon}</span>
                              <span className="text-sm">{model.model}</span>
                            </div>
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                          <div className="text-xs">
                            <p className="font-semibold">{model.model} DRT 모델</p>
                            <p className="text-gray-400">AI 예측 정확도: {model.accuracy}%</p>
                            <p className="mt-1">
                              {model.model === "교통취약지" && "교통 사각지대 해소용"}
                              {model.model === "출퇴근" && "출퇴근 시간 최적화용"}
                              {model.model === "관광형" && "관광지 접근성 향상용"}
                            </p>
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    );
                  })}
                </TooltipProvider>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 지도 (11/12) */}
        <div className="col-span-11">
          <Card className="h-[800px]">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>정류장별 DRT 적합성 지도</CardTitle>
                  <CardDescription>
                    구를 클릭하여 정류장을 표시하고, 정류장을 클릭하여 상세 분석을 확인하세요
                  </CardDescription>
                </div>
                
                {/* 검색 기능 */}
                <div className="relative">
                  <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 min-w-[280px]">
                    <Search className="h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="정류장 이름 또는 ID 검색..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="flex-1 bg-transparent border-none outline-none text-sm"
                    />
                  </div>
                  
                  {/* 검색 결과 드롭다운 */}
                  {searchResults.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
                      <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-600">
                        {searchResults.length}개 정류장 발견 
                        {allStationsData.length > 0 ? " (전체 검색)" : " (현재 구)"}
                      </div>
                      {searchResults.map((station) => (
                        <button
                          key={station.station_id}
                          onClick={() => handleSearchResultSelect(station)}
                          className="w-full px-3 py-2 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors"
                        >
                          <div className="font-medium text-sm">{station.station_name}</div>
                          <div className="text-xs text-gray-500 flex items-center gap-2">
                            <span>ID: {station.station_id}</span>
                            <span>•</span>
                            <span>DRT: {station.drt_score.toFixed(1)}점</span>
                            {allStationsData.length > 0 && (
                              <>
                                <span>•</span>
                                <span className="text-blue-600">{selectedDistrictName}</span>
                              </>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="h-[700px] p-2">
              <div className="w-full h-full">
                <ModelSuitabilityMap
                  selectedModel={selectedModel}
                  selectedMonth={selectedMonth}
                  initialDistrictName={selectedDistrictName}
                  height="680px"
                onDistrictAnalysis={(districtName, analysis) => {
                  console.log("🔄 DemandContent received analysis:", { districtName, analysis });
                  
                  // 구 이름 업데이트
                  setSelectedDistrictName(districtName);
                  
                  // 정류장 선택 처리
                  if (analysis.stationName && analysis.stationData) {
                    // 지도에서 직접 전달받은 정류장 데이터 사용
                    console.log("🚏 Using station data from map:", analysis.stationData);
                    const newStation = analysis.stationData;
                    
                    // 이전 선택과 다른 정류장인지 확인
                    if (!selectedStation || selectedStation.station_id !== newStation.station_id) {
                      console.log("📍 Selecting new station:", newStation.station_name, "ID:", newStation.station_id);
                      setSelectedStation(newStation);
                      // 상세 정보 즉시 초기화 (새로운 데이터 로딩 표시를 위해)
                      setStationDetail(null);
                    } else {
                      console.log("🔄 Same station selected, no update needed");
                    }
                  } else if (analysis.stationName) {
                    // 기존 로직: drtData에서 찾기
                    const station = drtData?.stations.find(
                      s => s.station_name === analysis.stationName
                    );
                    console.log("🚏 Found station in drtData:", station);
                    if (station && (!selectedStation || selectedStation.station_id !== station.station_id)) {
                      setSelectedStation(station);
                      setStationDetail(null);
                      console.log("✅ Station set:", station.station_name);
                    } else if (!station) {
                      console.log("❌ Station not found in current drtData");
                    }
                  } else {
                    // 정류장 선택 해제
                    console.log("🔄 No station selected, clearing selection");
                    setSelectedStation(null);
                    setStationDetail(null);
                  }
                }}
              />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 하단: 모델별 특성 분석 + 시계열 그래프 + TOP 5 정류장 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* 모델별 특성 분석 (정류장 기준) */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>정류장 특성 분석</CardTitle>
            <CardDescription>
              {selectedStation 
                ? `${selectedStation.station_name} 정류장의 ${selectedModel} 모델 특성`
                : "정류장을 선택하여 특성을 분석하세요"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedStation ? (
              <div className="space-y-4">
                {loadingStationDetail ? (
                  <div className="flex items-center justify-center h-64">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                      <div className="text-gray-500">
                        <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                        <div className="text-base">정류장 데이터 로딩 중...</div>
                      </div>
                    </div>
                  </div>
                ) : stationDetail && stationCharacteristics ? (
                  <>
                    <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                      <h4 className="font-semibold text-lg mb-3 flex items-center gap-2">
                        🎯 {stationCharacteristics.title}
                      </h4>
                      <div className="space-y-3">
                        {stationCharacteristics.items.map((item, idx) => (
                          <div key={idx} className="bg-white p-3 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <div>
                                <div className="font-semibold text-lg">{item.label}</div>
                                <div className="text-lg text-gray-600">{item.description}</div>
                              </div>
                              <div className="text-right">
                                <div className="text-xl font-bold text-blue-600">
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
                ) : (
                  <div className="flex items-center justify-center h-64 text-gray-400">
                    <div className="text-center">
                      <div className="text-4xl mb-3">⚠️</div>
                      <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                      <div className="text-base mt-2">정류장 데이터를 불러올 수 없습니다</div>
                      <div className="text-sm mt-1">다른 정류장을 선택해주세요</div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <div className="text-4xl mb-3">📊</div>
                  <div className="text-lg">지도에서 정류장을 클릭하면</div>
                  <div className="text-lg">해당 정류장의 특성을 분석합니다</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 시계열 그래프 */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>시간대별 DRT 점수</CardTitle>
            <CardDescription>
              {selectedStation && stationDetail
                ? `${selectedStation.station_name} 정류장의 24시간 DRT 점수 변화`
                : "정류장을 선택하여 시간대별 패턴을 확인하세요"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedStation ? (
              loadingStationDetail ? (
                <div className="flex items-center justify-center h-64">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <div className="text-gray-500">
                      <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                      <div className="text-base">시간대별 데이터 로딩 중...</div>
                    </div>
                  </div>
                </div>
              ) : stationDetail ? (
                <div className="space-y-4">
                  <ResponsiveContainer width="100%" height={600}>
                  <LineChart data={getHourlyChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="hour" 
                      tick={{ fontSize: 12 }}
                      interval={1}
                    />
                    <YAxis 
                      tick={{ fontSize: 12 }}
                      domain={[0, 100]}
                    />
                    <RechartsTooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="score" 
                      stroke="#3b82f6" 
                      strokeWidth={3}
                      name="DRT 점수"
                      dot={{ r: 4 }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="평균" 
                      stroke="#ef4444" 
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      name="일평균"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>

                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 bg-blue-50 rounded">
                    <div className="text-lg text-blue-600">현재 점수</div>
                    <div className="font-bold text-xl text-blue-700">
                      {stationDetail.current_score.toFixed(1)}점
                    </div>
                  </div>
                  <div className="text-center p-3 bg-green-50 rounded">
                    <div className="text-lg text-green-600">피크 시간</div>
                    <div className="font-bold text-xl text-green-700">
                      {stationDetail.peak_hour}시
                    </div>
                  </div>
                  <div className="text-center p-3 bg-purple-50 rounded">
                    <div className="text-lg text-purple-600">일평균</div>
                    <div className="font-bold text-xl text-purple-700">
                      {stationDetail.monthly_average.toFixed(1)}점
                    </div>
                  </div>
                </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-64 text-gray-400">
                  <div className="text-center">
                    <div className="text-4xl mb-3">⚠️</div>
                    <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                    <div className="text-base mt-2">시간대별 데이터를 불러올 수 없습니다</div>
                  </div>
                </div>
              )
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <div className="text-4xl mb-3">📈</div>
                  <div className="text-lg">지도에서 정류장을 클릭하면</div>
                  <div className="text-lg">24시간 DRT 점수 변화를 확인할 수 있습니다</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 모델별 TOP 5 정류장 */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-4">
            <CardTitle className="text-2xl flex items-center gap-2">
              🏆 {selectedModel} DRT TOP 5 정류장
            </CardTitle>
            <CardDescription className="text-lg">
              <div className="flex items-center justify-between">
                <span>{selectedModel} 모델 기준 상위 정류장 분석</span>
                {selectedRegion !== "전체" && selectedDistrictName !== selectedRegion && (
                  <span className="text-orange-600 text-base font-medium">
                    ({selectedDistrictName} 데이터)
                  </span>
                )}
              </div>
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              {drtData?.stations && drtData.stations.length > 0 ? (
                [...drtData.stations]
                  .sort((a, b) => (b.drt_score || 0) - (a.drt_score || 0))
                  .slice(0, 5)
                  .map((station, index) => (
                    <div key={station.station_id} className="p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <h4 className="font-semibold text-base">{station.station_name}</h4>
                          <p className="text-sm text-muted-foreground">{selectedDistrictName}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-base font-bold text-blue-600">{station.drt_score?.toFixed(1)}점</div>
                          <Badge variant={index === 0 ? "default" : index < 3 ? "secondary" : "outline"} className="text-sm">
                            #{index + 1}
                          </Badge>
                        </div>
                      </div>
                      <Progress value={station.drt_score || 0} max={100} className="h-1.5" />
                    </div>
                  ))
              ) : (
                <div className="text-center text-gray-500 py-6">
                  <div className="text-2xl mb-2">
                    {selectedModel === '교통취약지' ? '💜' : selectedModel === '출퇴근' ? '🏢' : '📸'}
                  </div>
                  <div className="text-base">{selectedModel} 데이터 로딩 중...</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
});