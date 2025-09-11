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
import { Search, HelpCircle, Filter, X, ChevronDown } from "lucide-react";
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
import { memo, useState, useEffect, useRef, useMemo } from "react";
import { apiService, DRTScoreResponse, DRTModelType, DRTStationData, DRTStationDetailResponse, VulnerableFeatureScores, CommuterFeatureScores, TourismFeatureScores, utils } from "@/lib/api";
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
  const [loadingDrtData, setLoadingDrtData] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<DRTStationData[]>([]);
  const [focusStation, setFocusStation] = useState<{ lat: number; lng: number; stationName: string } | null>(null);
  
  // 필터링 상태 추가
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [filterSettings, setFilterSettings] = useState({
    scoreRank: 'all',
    scoreRange: 'all'
  });
  
  
  // 현재 선택된 모델의 색상 테마
  const currentTheme = modelColorThemes[selectedModel as keyof typeof modelColorThemes] || modelColorThemes["출퇴근"];
  
  // 필터링된 정류장 데이터 계산
  const filteredStations = useMemo(() => {
    if (!drtData?.stations) return [];
    
    let filtered = [...drtData.stations];
    
    // 점수 구간 필터링
    if (filterSettings.scoreRange !== 'all') {
      filtered = filtered.filter(station => {
        const score = station.drt_score;
        switch (filterSettings.scoreRange) {
          case '90+': return score >= 90;
          case '80-89': return score >= 80 && score < 90;
          case '70-79': return score >= 70 && score < 80;
          case '60-69': return score >= 60 && score < 70;
          case 'below60': return score < 60;
          default: return true;
        }
      });
    }
    
    // 점수 순위 필터링
    if (filterSettings.scoreRank !== 'all') {
      filtered.sort((a, b) => b.drt_score - a.drt_score);
      const rankLimit = parseInt(filterSettings.scoreRank.replace('top', ''));
      filtered = filtered.slice(0, rankLimit);
    }
    
    return filtered;
  }, [drtData?.stations, filterSettings]);
  
  // AbortController를 useRef로 관리하여 이전 요청 취소
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // 구별 DRT 데이터 로드
  useEffect(() => {
    const loadDRTData = async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      abortControllerRef.current = new AbortController();
      const currentAbortController = abortControllerRef.current;
      
      try {
        setLoadingDrtData(true);
        
        const apiModelType = modelTypeMapping[selectedModel as keyof typeof modelTypeMapping] || "vulnerable";
        let targetRegion = selectedDistrictName || selectedRegion;
        let response;
        let didFallback = false;
        
        if (selectedRegion === "전체") {
          try {
            response = await apiService.getDRTScores(
              "전체",
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
          } catch {
            targetRegion = "강남구";
            didFallback = true;
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
          }
        } else {
          if (selectedDistrictName) {
            targetRegion = selectedDistrictName;
          }
          
          try {
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
          } catch (regionError) {
            targetRegion = "강남구";
            didFallback = true;
            response = await apiService.getDRTScores(
              targetRegion,
              apiModelType,
              utils.formatSelectedMonth(selectedMonth)
            );
          }
        }
        
        if (currentAbortController.signal.aborted) {
          return;
        }
        
        setDrtData(response);
        
        if (didFallback && selectedDistrictName !== targetRegion) {
          setSelectedDistrictName(targetRegion);
        } else if ((!selectedDistrictName || selectedDistrictName === "") && selectedDistrictName !== targetRegion) {
          setSelectedDistrictName(targetRegion);
        }
        
        if (response.stations && response.stations.length > 0) {
          const sortedStations = [...response.stations].sort((a, b) => b.drt_score - a.drt_score);
          
          if (didFallback) {
            const defaultStation = sortedStations[0];
            setSelectedStation(defaultStation);
            console.log("Setting fallback default station:", defaultStation.station_name);
          } else {
            const currentSelectedInNewData = selectedStation && response.stations.find(
              s => s.station_id === selectedStation.station_id
            );
            
            if (currentSelectedInNewData && (!selectedStation || selectedStation.drt_score !== currentSelectedInNewData.drt_score)) {
              setSelectedStation(currentSelectedInNewData);
              console.log("Updating existing selected station:", currentSelectedInNewData.station_name);
            } else if (isInitialLoad || !selectedStation) {
              const defaultStation = sortedStations[0];
              setSelectedStation(defaultStation);
              console.log("Setting initial default station:", defaultStation.station_name);
            } else {
              const sameNameStation = response.stations.find(s => s.station_name === selectedStation.station_name);
              if (sameNameStation) {
                setSelectedStation(sameNameStation);
                console.log("Setting same name station:", sameNameStation.station_name);
              } else {
                // 기존 선택된 정류장이 없을 경우 첫 번째 정류장 선택
                const defaultStation = sortedStations[0];
                setSelectedStation(defaultStation);
                console.log("Fallback to first station:", defaultStation.station_name);
              }
            }
          }
          
          if (isInitialLoad) {
            setIsInitialLoad(false);
          }
        } else {
          setSelectedStation(null);
          setStationDetail(null);
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.error("DRT API error:", err);
        }
      } finally {
        setLoadingDrtData(false);
      }
    };

    loadDRTData();
    
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [selectedModel, selectedRegion, selectedMonth, selectedDistrictName, isInitialLoad]);

  // 상단 헤더에 현재 선택된 구 알리기
  useEffect(() => {
    if (onDistrictChange && selectedDistrictName && selectedDistrictName !== "") {
      onDistrictChange(selectedDistrictName);
    }
  }, [selectedDistrictName, onDistrictChange]);

  // 정류장 상세 정보 로드
  useEffect(() => {
    if (!selectedStation) {
      console.log("No selected station, clearing station detail");
      setStationDetail(null);
      return;
    }
    
    console.log("Loading station detail for:", selectedStation.station_name, selectedStation.station_id);
    
    const loadStationDetail = async () => {
      const apiModelType = modelTypeMapping[selectedModel as keyof typeof modelTypeMapping] || "vulnerable";
      try {
        setLoadingStationDetail(true);
        console.log("Loading station detail with params:", {
          station_id: selectedStation.station_id,
          model_type: apiModelType,
          month: utils.formatSelectedMonth(selectedMonth)
        });
        
        const detail = await apiService.getStationDetail(
          selectedStation.station_id,
          apiModelType,
          utils.formatSelectedMonth(selectedMonth)
        );
        
        if (!detail || !detail.feature_scores) {
          throw new Error("Invalid station detail response - missing feature_scores");
        }
        
        const requiredFields = ['current_score', 'peak_hour', 'monthly_average'] as const;
        type RequiredField = typeof requiredFields[number];
        
        const missingFields = requiredFields.filter((field: RequiredField) => {
          const value = (detail as any)[field];
          return value == null;
        });
        
        if (missingFields.length > 0) {
          throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
        }
        
        setStationDetail(detail);
        console.log("Successfully loaded station detail:", {
          station_name: selectedStation.station_name,
          hourly_scores_count: detail.hourly_scores?.length || 0,
          monthly_average: detail.monthly_average
        });
      } catch (err) {
        console.error("Failed to load station detail:", err);
        setStationDetail(null);
      } finally {
        setLoadingStationDetail(false);
      }
    };
    
    loadStationDetail();
  }, [selectedStation, selectedModel, selectedMonth]);

  // 검색 기능
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

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
    
    setSearchResults(filtered.slice(0, 5));
  }, [searchQuery, drtData?.stations, selectedDistrictName]);

  // 구 변경 시 검색 상태 초기화
  useEffect(() => {
    setSearchQuery("");
    setSearchResults([]);
  }, [selectedDistrictName]);

  // 검색 결과에서 정류장 선택
  const handleSearchResultSelect = (station: DRTStationData) => {
    setSelectedStation(station);
    setStationDetail(null);
    
    setFocusStation({
      lat: station.coordinate.lat,
      lng: station.coordinate.lng,
      stationName: station.station_name
    });
    
    setSearchQuery("");
    setSearchResults([]);
  };

  // 정류장별 특성 점수 계산
  const getStationCharacteristics = () => {
    if (!stationDetail) return null;
    
    const feature_scores = stationDetail.feature_scores;
    
    if (selectedModel === "교통취약지") {
      const isVulnerableScores = (scores: unknown): scores is VulnerableFeatureScores => {
        return scores !== null && typeof scores === 'object' && 'var_t_score' in scores && 'sed_t_score' in scores && 'mdi_t_score' in scores;
      };
      
      if (!isVulnerableScores(feature_scores)) {
        return null;
      }
      
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
      const isCommuterScores = (scores: unknown): scores is CommuterFeatureScores => {
        return scores !== null && typeof scores === 'object' && 'tc_score' in scores && 'pdr_score' in scores && 'ru_score' in scores;
      };
      
      if (!isCommuterScores(feature_scores)) {
        return null;
      }
      
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
      const isTourismScores = (scores: unknown): scores is TourismFeatureScores => {
        return scores !== null && typeof scores === 'object' && 'tc_t_score' in scores && 'tdr_t_score' in scores && 'ru_t_score' in scores;
      };
      
      if (!isTourismScores(feature_scores)) {
        return null;
      }
      
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
    if (!stationDetail?.hourly_scores || !Array.isArray(stationDetail.hourly_scores)) {
      console.log("No hourly scores data available:", {
        stationDetail_exists: !!stationDetail,
        hourly_scores_exists: !!stationDetail?.hourly_scores,
        hourly_scores_is_array: Array.isArray(stationDetail?.hourly_scores)
      });
      return [];
    }
    
    const chartData = stationDetail.hourly_scores.map(item => ({
      hour: `${item.hour}시`,
      score: typeof item.score === 'number' ? item.score : 0,
      평균: typeof stationDetail.monthly_average === 'number' ? stationDetail.monthly_average : 0,
    }));
    
    console.log("Formatted hourly chart data:", {
      data_length: chartData.length,
      sample_data: chartData.slice(0, 3),
      monthly_average: stationDetail.monthly_average
    });
    
    return chartData;
  };

  const stationCharacteristics = getStationCharacteristics();

  return (
    <div className="space-y-6">
      {/* 2x2 그리드 레이아웃 */}
      <div className="grid grid-cols-12 auto-rows-max gap-4 min-h-[1250px]">
        {/* 좌상: 지도 (9/12) - 2행 확장 */}
        <div className="col-span-9 row-span-2">
          <Card className="h-[1250px]">
            <CardHeader>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <CardTitle className="text-2xl font-bold">정류장별 DRT 적합성 지도</CardTitle>
                  <CardDescription>
                    구를 클릭하여 정류장을 표시하고, 정류장을 클릭하여 상세 분석을 확인하세요
                  </CardDescription>
                </div>
                
                {/* 지도 헤더에 배치된 모델 선택 버튼들 */}
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 mr-3">
                    <Image 
                      src="/sidebar_icon/DRT분석_사이드바.png" 
                      alt="DRT 분석" 
                      width={16}
                      height={16}
                      className="h-4 w-4"
                    />
                    <span className="text-sm font-semibold text-gray-700">DRT 모델</span>
                  </div>
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
                              className={`px-3 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                                isSelected
                                  ? `${colors.bg} text-white shadow-lg`
                                  : `bg-white text-gray-700 ${colors.hover} border ${colors.border}`
                              }`}
                            >
                              <span className="text-base">{model.icon}</span>
                              <span>{model.model}</span>
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom">
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
              </div>
              
              <div className="flex items-center justify-end">
                {/* 검색 및 필터 기능 */}
                <div className="flex items-center gap-2">
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
                  
                  {/* 필터 버튼 */}
                  <div className="relative">
                    <button
                      onClick={() => setShowFilters(!showFilters)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
                        showFilters 
                          ? 'bg-blue-50 border-blue-300 text-blue-700' 
                          : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      <Filter className="h-4 w-4" />
                      <span className="text-sm">필터</span>
                      <ChevronDown className={`h-3 w-3 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {/* 필터 드롭다운 */}
                    {showFilters && (
                      <div className="absolute top-full right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 w-80">
                        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="font-semibold text-sm">정류장 필터</h3>
                              <div className="text-xs text-gray-600 mt-1">
                                {drtData?.stations ? (
                                  <>
                                    <span className="text-blue-600 font-medium">{filteredStations.length}개</span>
                                    <span> / </span>
                                    <span>{drtData.stations.length}개 정류장</span>
                                  </>
                                ) : (
                                  <span>데이터를 불러오는 중...</span>
                                )}
                              </div>
                            </div>
                            <button 
                              onClick={() => setShowFilters(false)}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                        
                        <div className="p-4 space-y-4">
                          {/* 점수 순위 필터 */}
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">점수 순위</label>
                            <select
                              value={filterSettings.scoreRank}
                              onChange={(e) => setFilterSettings(prev => ({ ...prev, scoreRank: e.target.value }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                              <option value="all">전체 보기</option>
                              <option value="top10">상위 10개</option>
                              <option value="top20">상위 20개</option>
                              <option value="top50">상위 50개</option>
                            </select>
                          </div>
                          
                          {/* 점수 구간 필터 */}
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">점수 구간</label>
                            <select
                              value={filterSettings.scoreRange}
                              onChange={(e) => setFilterSettings(prev => ({ ...prev, scoreRange: e.target.value }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                              <option value="all">전체 점수</option>
                              <option value="90+">90점 이상 (최우수)</option>
                              <option value="80-89">80-89점 (우수)</option>
                              <option value="70-79">70-79점 (양호)</option>
                              <option value="60-69">60-69점 (보통)</option>
                              <option value="below60">60점 미만 (개선필요)</option>
                            </select>
                          </div>
                          
                          {/* 필터 적용/초기화 버튼 */}
                          <div className="flex gap-2 pt-2 border-t border-gray-200">
                            <button
                              onClick={() => {
                                setFilterSettings({
                                  scoreRank: 'all',
                                  scoreRange: 'all'
                                });
                              }}
                              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                            >
                              초기화
                            </button>
                            <button
                              onClick={() => setShowFilters(false)}
                              className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                            >
                              적용
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="h-[1050px] min-h-[1050px] max-h-[1050px] p-6">
              <div className="w-full h-full flex items-center justify-center">
                <div className="w-full" style={{ height: '880px' }}>
                  <ModelSuitabilityMap
                    selectedModel={selectedModel}
                    selectedMonth={selectedMonth}
                    initialDistrictName={selectedDistrictName}
                    height="880px"
                  focusStation={focusStation}
                  filteredStations={filteredStations}
                  onDistrictAnalysis={async (districtName, analysis) => {
                    if (selectedDistrictName !== districtName) {
                      setDrtData(null);
                      setSelectedStation(null);
                      setStationDetail(null);
                      setSearchQuery("");
                      setSearchResults([]);
                      setFocusStation(null);
                      setLoadingDrtData(true);
                      setSelectedDistrictName(districtName);
                    }
                    
                    if (analysis.stationName && analysis.stationData) {
                      const newStation = analysis.stationData;
                      
                      if (!selectedStation || selectedStation.station_id !== newStation.station_id) {
                        setSelectedStation(newStation);
                        setStationDetail(null);
                        
                        if (drtData && drtData.top_stations) {
                          console.log("Keeping TOP5 data for district:", selectedDistrictName);
                        }
                      }
                    } else if (analysis.stationName) {
                      const station = drtData?.stations.find(
                        s => s.station_name === analysis.stationName
                      );
                      if (station && (!selectedStation || selectedStation.station_id !== station.station_id)) {
                        setSelectedStation(station);
                        setStationDetail(null);
                        
                        if (drtData && drtData.top_stations) {
                          console.log("Keeping TOP5 data for district:", selectedDistrictName);
                        }
                      }
                    } else {
                      setSelectedStation(null);
                      setStationDetail(null);
                    }
                  }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 우상: 시간대별 DRT 점수 카드 (3/12) */}
        <div className="col-span-3 row-span-1">
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl font-bold">
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
TOP 5 DRT 적합 정류장 순위
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedStation ? (
                loadingStationDetail ? (
                  <div className="flex items-center justify-center h-32">
                    <div className="text-center">
                      <div className={`animate-spin rounded-full h-12 w-12 border-b-2 ${currentTheme.spinner} mx-auto mb-4`}></div>
                      <div className="text-gray-500">
                        <div className="font-semibold text-lg">{selectedStation.station_name}</div>
                        <div className="text-base">시간대별 데이터 로딩 중...</div>
                      </div>
                    </div>
                  </div>
                ) : stationDetail ? (
                  <div className="space-y-2">
                    <ResponsiveContainer width="100%" height={300}>
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

                    <div className="grid grid-cols-1 gap-2">
                      <div className={`text-center p-2 rounded ${currentTheme.background.replace('from-', 'bg-').replace(' to-pink-50', '').replace(' to-indigo-50', '').replace(' to-emerald-50', '')}`}>
                        <div className={`text-sm ${currentTheme.secondary}`}>현재: {stationDetail.current_score.toFixed(1)}점</div>
                        <div className={`text-sm ${currentTheme.secondary}`}>피크: {stationDetail.peak_hour}시 | 평균: {stationDetail.monthly_average.toFixed(1)}점</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-32 text-gray-400">
                    <div className="text-center">
                      <div className="text-2xl mb-2">⚠️</div>
                      <div className="font-semibold text-sm">{selectedStation.station_name}</div>
                      <div className="text-xs mt-1">데이터를 불러올 수 없습니다</div>
                      <button 
                        onClick={() => {
                          setStationDetail(null);
                        }}
                        className={`mt-2 px-2 py-1 ${currentTheme.button} rounded text-xs`}
                      >
                        🔄 다시 시도
                      </button>
                    </div>
                  </div>
                )
              ) : (
                <div className="flex items-center justify-center h-32 text-gray-400">
                  <div className="text-center">
                    <Image 
                      src="/drt_icon/시간대별DRT점수_drt분석.png" 
                      alt="시간대별 DRT 점수" 
                      width={32}
                      height={32}
                      className="h-8 w-8 mx-auto mb-2 opacity-60"
                    />
                    <div className="text-sm">정류장을 클릭하면</div>
                    <div className="text-sm">시간대별 점수를 확인할 수 있습니다</div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>


        {/* 우하: 정류장 피크 특성 분석 카드 (3/12) */}
        <div className="col-span-3 row-span-1">
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl font-bold">
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
                  <div className={`text-center py-3 px-4 bg-gradient-to-r ${currentTheme.background} rounded-lg border ${currentTheme.border}`}>
                    <div className={`text-2xl font-bold ${currentTheme.primary} mb-1`}>
                      🚏 {selectedStation.station_name}
                    </div>
                    <div className={`text-sm ${currentTheme.secondary} font-medium`}>
                      {selectedModel} 모델 피크 특성 분석
                    </div>
                  </div>
                  {loadingStationDetail ? (
                    <div className="flex items-center justify-center h-32">
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
                    <div className="flex items-center justify-center h-32 text-gray-400">
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
                            setStationDetail(null);
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
                <div className="flex items-center justify-center h-32 text-gray-400">
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
        </div>
      </div>
    </div>
  );
});