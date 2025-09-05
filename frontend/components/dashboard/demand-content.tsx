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
import { Search, HelpCircle } from "lucide-react";
import Image from "next/image";
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

// 모델별 색상 테마
const modelColorThemes = {
  "교통취약지": {
    primary: "text-red-800",
    secondary: "text-red-600", 
    background: "from-red-50 to-pink-50",
    border: "border-red-200",
    spinner: "border-red-600",
    button: "bg-red-100 text-red-700 hover:bg-red-200",
    score: "text-red-600"
  },
  "출퇴근": {
    primary: "text-blue-800",
    secondary: "text-blue-600",
    background: "from-blue-50 to-indigo-50", 
    border: "border-blue-200",
    spinner: "border-blue-600",
    button: "bg-blue-100 text-blue-700 hover:bg-blue-200",
    score: "text-blue-600"
  },
  "관광형": {
    primary: "text-green-800",
    secondary: "text-green-600",
    background: "from-green-50 to-emerald-50",
    border: "border-green-200", 
    spinner: "border-green-600",
    button: "bg-green-100 text-green-700 hover:bg-green-200",
    score: "text-green-600"
  }
};

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
  const [focusStation, setFocusStation] = useState<{ lat: number; lng: number; stationName: string } | null>(null);
  
  // 현재 선택된 모델의 색상 테마
  const currentTheme = modelColorThemes[selectedModel as keyof typeof modelColorThemes] || modelColorThemes["출퇴근"];
  
  // 구별 DRT 데이터 로드
  useEffect(() => {
    const loadDRTData = async () => {
      try {
        const apiModelType = modelTypeMapping[selectedModel as keyof typeof modelTypeMapping] || "vulnerable";
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
          } catch {
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
          // 지도에서 선택된 구가 있으면 그것을 우선 사용
          if (selectedDistrictName) {
            targetRegion = selectedDistrictName;
          }
          
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
  }, [selectedModel, selectedRegion, selectedMonth, selectedDistrictName, isInitialLoad, selectedStation]);


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
      const apiModelType = modelTypeMapping[selectedModel as keyof typeof modelTypeMapping] || "vulnerable";
      try {
        setLoadingStationDetail(true);
        
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
        
        // 응답 데이터 유효성 검사
        if (!detail || !detail.feature_scores) {
          console.error("❌ Invalid station detail response:", detail);
          throw new Error("Invalid station detail response - missing feature_scores");
        }
        
        // 필수 필드 검사
        const requiredFields = ['current_score', 'peak_hour', 'monthly_average'];
        const missingFields = requiredFields.filter(field => (detail as any)[field] === undefined || (detail as any)[field] === null);
        
        if (missingFields.length > 0) {
          console.error("❌ Missing required fields:", missingFields);
          throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
        }
        
        setStationDetail(detail);
      } catch (err) {
        console.error("🚨 Failed to load station detail:", err);
        console.error("🚨 Station info:", {
          station_name: selectedStation.station_name,
          station_id: selectedStation.station_id,
          coordinate: selectedStation.coordinate,
          drt_score: selectedStation.drt_score
        });
        console.error("🚨 API parameters:", {
          model: apiModelType,
          month: utils.formatSelectedMonth(selectedMonth),
          original_selectedModel: selectedModel
        });
        setStationDetail(null);
      } finally {
        setLoadingStationDetail(false);
      }
    };
    
    loadStationDetail();
  }, [selectedStation, selectedModel, selectedMonth]);

  // 검색 기능 (선택된 구의 정류장만 검색)
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    // 현재 선택된 구의 정류장 데이터에서만 검색
    const searchData = drtData?.stations || [];
    
    if (searchData.length === 0) {
      setSearchResults([]);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = searchData.filter(station => 
      station.station_name.toLowerCase().includes(query) ||
      station.station_id.toLowerCase().includes(query)
    );
    
    console.log("🔍 Search results for:", searchQuery, "Found:", filtered.length, "Search scope:", selectedDistrictName || "현재 구");
    setSearchResults(filtered.slice(0, 5)); // 구 내 검색이므로 최대 5개까지 표시
  }, [searchQuery, drtData?.stations, selectedDistrictName]);

  // 검색 결과에서 정류장 선택
  const handleSearchResultSelect = (station: DRTStationData) => {
    console.log("🚏 Selected station from search:", station.station_name, "at coordinates:", station.coordinate);
    
    // 정류장 선택
    setSelectedStation(station);
    setStationDetail(null); // 상세 정보 새로 로드
    
    // 지도 이동 트리거
    setFocusStation({
      lat: station.coordinate.lat,
      lng: station.coordinate.lng,
      stationName: station.station_name
    });
    
    // 검색 UI 초기화
    setSearchQuery(""); // 검색창 초기화
    setSearchResults([]); // 검색 결과 닫기
    
    console.log("🎯 Triggering map focus to:", station.station_name);
  };

  // 정류장별 특성 점수 계산 (실제 API feature_scores 기반)
  const getStationCharacteristics = () => {
    if (!stationDetail) return null;
    
    const feature_scores = stationDetail.feature_scores as any;
    
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
                <Image 
                  src="/sidebar_icon/DRT분석_사이드바.png" 
                  alt="DRT 분석" 
                  width={20}
                  height={20}
                  className="h-5 w-5"
                />
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
                        ({selectedDistrictName || "현재 구"} 내 검색)
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
                            <span>•</span>
                            <span className={currentTheme.secondary}>{selectedDistrictName}</span>
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
                  focusStation={focusStation}
                onDistrictAnalysis={async (districtName, analysis) => {
                  console.log("🔄 DemandContent received analysis:", { districtName, analysis });
                  
                  // 구가 변경된 경우에만 새 데이터 로딩
                  if (selectedDistrictName !== districtName) {
                    console.log("🗺️ District changed from", selectedDistrictName, "to", districtName, "- loading new data");
                    
                    // 구 이름 먼저 업데이트
                    setSelectedDistrictName(districtName);
                    
                    // 새 구의 DRT 데이터 로딩
                    try {
                      const apiModelType = modelTypeMapping[selectedModel as keyof typeof modelTypeMapping] || "vulnerable";
                      console.log("📡 Loading DRT data for new district:", districtName);
                      
                      const response = await apiService.getDRTScores(
                        districtName,
                        apiModelType,
                        utils.formatSelectedMonth(selectedMonth)
                      );
                      
                      console.log("✅ New district data loaded:", districtName, "- stations:", response?.stations?.length || 0);
                      setDrtData(response);
                      
                      // 기존 정류장 선택 초기화 (다른 구의 정류장이므로)
                      setSelectedStation(null);
                      setStationDetail(null);
                      
                      // 검색 쿼리도 초기화 (다른 구로 변경되었으므로)
                      setSearchQuery("");
                      setSearchResults([]);
                      
                      // 지도 포커스도 초기화
                      setFocusStation(null);
                      
                    } catch (error) {
                      console.error("🚨 Failed to load data for district:", districtName, error);
                      // 실패 시 기존 로직 유지
                    }
                  } else {
                    console.log("🔄 Same district selected, no data reload needed");
                  }
                  
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
            <CardTitle className="flex items-center gap-2">
              정류장 피크 특성 분석
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-4 w-4 text-gray-400 hover:text-gray-600 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-sm p-4">
                    <div className="space-y-2">
                      <div className="font-semibold text-sm">정류장 피크 특성 분석</div>
                      <div className="text-xs text-gray-600 space-y-1">
                        <div><strong>출퇴근형:</strong> TC(시간 집중도), PDR(피크 수요 비율), RU(노선 활용도)</div>
                        <div><strong>관광특화형:</strong> TC(관광 집중도), TDR(관광 수요 비율), RU(구간 이용률)</div>
                        <div><strong>교통취약지형:</strong> VAR(취약 접근성), SED(사회 형평성), MDI(이동성 불리), AVS(지역 취약성)</div>
                      </div>
                      <div className="text-xs text-blue-600 mt-2">
                        💡 선택된 정류장의 모델별 세부 지표를 분석합니다
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selectedStation ? (
              <div className="space-y-4">
                {/* 선택된 정류장 이름 강조 표시 */}
                <div className={`text-center py-3 px-4 bg-gradient-to-r ${currentTheme.background} rounded-lg border ${currentTheme.border}`}>
                  <div className={`text-2xl font-bold ${currentTheme.primary} mb-1`}>
                    🚏 {selectedStation.station_name}
                  </div>
                  <div className={`text-sm ${currentTheme.secondary} font-medium`}>
                    {selectedModel} 모델 피크 특성 분석
                  </div>
                </div>
                {loadingStationDetail ? (
                  <div className="flex items-center justify-center h-64">
                    <div className="text-center">
                      <div className={`animate-spin rounded-full h-12 w-12 border-b-2 ${currentTheme.spinner} mx-auto mb-4`}></div>
                      <div className="text-gray-500">
                        <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                        <div className="text-base">정류장 데이터 로딩 중...</div>
                      </div>
                    </div>
                  </div>
                ) : stationDetail && stationCharacteristics ? (
                  <>
                    <div className={`p-4 bg-gradient-to-r ${currentTheme.background} rounded-lg`}>
                      <h4 className={`font-semibold text-lg mb-3 flex items-center gap-2 ${currentTheme.primary}`}>
                        🎯 {stationCharacteristics.title}
                      </h4>
                      <div className="space-y-3">
                        {stationCharacteristics.items.map((item, idx) => (
                          <div key={idx} className="bg-white p-3 rounded-lg">
                            <div className="flex items-start gap-3 mb-2">
                              <div className="flex-1 min-w-0">
                                <div className="font-semibold text-base">{item.label}</div>
                                <div className="text-xs text-gray-600">{item.description}</div>
                              </div>
                              <div className="flex-shrink-0 text-right">
                                <div className={`text-lg font-bold ${currentTheme.score}`}>
                                  {item.score}점
                                </div>
                                <Badge variant={
                                  item.level.includes("매우 높음") || item.level.includes("최우수") || item.level.includes("최대치") ? "default" : 
                                  item.level.includes("높음") || item.level.includes("우수") ? "secondary" : 
                                  item.level.includes("보통") ? "outline" : 
                                  "secondary"
                                } className="text-xs px-1.5 py-0.5">
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

                    <div className={`p-3 rounded-lg ${currentTheme.background.replace('from-', 'bg-').replace(' to-pink-50', '').replace(' to-indigo-50', '').replace(' to-emerald-50', '')}`}>
                      <div className={`text-base font-medium ${currentTheme.primary} mb-1`}>
                        종합 DRT 적합도
                      </div>
                      <div className="flex items-center justify-between">
                        <div className={`text-2xl font-bold ${currentTheme.secondary}`}>
                          {stationDetail.current_score.toFixed(1)}점
                        </div>
                        <div className={`text-base ${currentTheme.primary}`}>
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
                      <div className="text-sm mt-2 text-gray-500">
                        ID: {selectedStation.station_id} | 모델: {selectedModel}
                      </div>
                      <div className="text-sm mt-1">다른 정류장을 선택해주세요</div>
                      <button 
                        onClick={() => {
                          console.log("🔄 Retry button clicked for station:", selectedStation.station_name);
                          setStationDetail(null);
                          // useEffect will automatically trigger reload
                        }}
                        className={`mt-3 px-4 py-2 ${currentTheme.button} rounded-lg transition-colors text-sm`}
                      >
                        🔄 다시 시도
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <Image 
                    src="/drt_icon/정류장피크특성분석_drt분석.png" 
                    alt="정류장 피크 특성 분석" 
                    width={64}
                    height={64}
                    className="h-16 w-16 mx-auto mb-3 opacity-60"
                  />
                  <div className="text-lg">지도에서 정류장을 클릭하면</div>
                  <div className="text-lg">해당 정류장의 피크 특성을 분석합니다</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 시계열 그래프 */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              시간대별 DRT 점수
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-4 w-4 text-gray-400 hover:text-gray-600 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-md p-4">
                    <div className="space-y-2">
                      <div className="font-semibold text-sm">시간대별 DRT 점수</div>
                      <div className="text-xs text-gray-600 space-y-1">
                        <div>📈 <strong>24시간 DRT 점수:</strong> 0시부터 23시까지 시간대별 점수 변화</div>
                        <div>🎯 <strong>현재 점수:</strong> 선택된 시간대의 DRT 적합도 점수</div>
                        <div>⏰ <strong>피크 시간:</strong> 가장 높은 점수를 기록한 시간대</div>
                        <div>📊 <strong>일평균:</strong> 해당 정류장의 월별 평균 점수</div>
                      </div>
                      <div className="text-xs text-blue-600 mt-2">
                        💡 정류장별 수요 패턴과 최적 운행 시간대를 분석합니다
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
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
                    <div className={`animate-spin rounded-full h-12 w-12 border-b-2 ${currentTheme.spinner} mx-auto mb-4`}></div>
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
                  <div className={`text-center p-3 rounded ${currentTheme.background.replace('from-', 'bg-').replace(' to-pink-50', '').replace(' to-indigo-50', '').replace(' to-emerald-50', '')}`}>
                    <div className={`text-lg ${currentTheme.secondary}`}>현재 점수</div>
                    <div className={`font-bold text-xl ${currentTheme.primary}`}>
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
                    <div className="text-sm mt-2 text-gray-500">
                      ID: {selectedStation.station_id} | 모델: {selectedModel}
                    </div>
                    <button 
                      onClick={() => {
                        console.log("🔄 Retry button clicked for station time data:", selectedStation.station_name);
                        setStationDetail(null);
                      }}
                      className={`mt-3 px-4 py-2 ${currentTheme.button} rounded-lg transition-colors text-sm`}
                    >
                      🔄 다시 시도
                    </button>
                  </div>
                </div>
              )
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <div className="text-center">
                  <Image 
                    src="/drt_icon/시간대별DRT점수_drt분석.png" 
                    alt="시간대별 DRT 점수" 
                    width={64}
                    height={64}
                    className="h-16 w-16 mx-auto mb-3 opacity-60"
                  />
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
            <CardTitle className="text-3xl">
              <div className="flex items-center justify-center gap-2">
                <Image 
                  src="/icon/인기정류장.png" 
                  alt="인기정류장" 
                  width={28}
                  height={28}
                  className="h-7 w-7"
                />
                <span>TOP 5</span>
              </div>
              <div className="text-xl text-center mt-1">
                {selectedDistrictName ? `${selectedDistrictName} ` : ""}{selectedModel} DRT
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-4 w-4 text-gray-400 hover:text-gray-600 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-sm p-4">
                    <div className="space-y-2">
                      <div className="font-semibold text-sm">TOP 5 DRT 적합 정류장</div>
                      <div className="text-xs text-gray-600 space-y-1">
                        <div>🥇 <strong>최고점수 기준:</strong> 각 정류장의 24시간 중 최고 DRT 점수</div>
                        <div>📍 <strong>지역별 순위:</strong> 선택된 구/지역 내 상위 5개 정류장</div>
                        <div>📊 <strong>진행률 바:</strong> 100점 만점 기준 상대적 점수 표시</div>
                        <div>🏅 <strong>순위 배지:</strong> 1위(금), 2-3위(은), 4-5위(동)</div>
                      </div>
                      <div className="text-xs text-blue-600 mt-2">
                        💡 DRT 서비스 도입 시 우선 검토 대상 정류장입니다
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
            <CardDescription className="text-sm text-center">
              <div className="flex items-center justify-center gap-1 flex-wrap">
                <span>{selectedDistrictName ? `${selectedDistrictName} ` : ""}{selectedModel} 상위 정류장</span>
                {selectedDistrictName && (
                  <span className={`${currentTheme.secondary} text-xs font-medium`}>
                    ({drtData?.stations?.length || 0}개 중)
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
                      <div className="flex items-start gap-2 mb-2">
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-sm">{station.station_name}</h4>
                          <p className="text-xs text-muted-foreground">{selectedDistrictName}</p>
                        </div>
                        <div className="flex-shrink-0 text-right">
                          <div className={`text-lg font-bold ${currentTheme.secondary}`}>{station.drt_score?.toFixed(1)}점</div>
                          <Badge variant={index === 0 ? "default" : index < 3 ? "secondary" : "outline"} className="text-xs px-2 py-1 font-medium">
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
                  <div className="text-base">{selectedDistrictName ? `${selectedDistrictName} ` : ""}{selectedModel} 데이터 로딩 중...</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
});