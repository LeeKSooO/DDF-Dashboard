"use client";

import { useState, lazy, Suspense, useRef, useEffect } from "react";
import { apiService, RAGQueryResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import {
  BarChart3,
  ChevronRight,
  ChevronDown,
  MapPin,
  Link2,
  Network,
} from "lucide-react";
import Image from "next/image";

// Lazy load components for better performance
const DashboardContent = lazy(() =>
  import("./dashboard/dashboard-content").then((m) => ({
    default: m.DashboardContent,
  }))
);
const DashboardOverviewContent = lazy(() =>
  import("./pages/dashboard-overview-content").then((m) => ({
    default: m.DashboardOverviewContent,
  }))
);
const TrafficContent = lazy(() =>
  import("./dashboard/traffic-content").then((m) => ({
    default: m.TrafficContent,
  }))
);
const HeatmapContent = lazy(() =>
  import("./pages/heatmap-content").then((m) => ({ default: m.HeatmapContent }))
);
const TrafficAnalysisContent = lazy(() =>
  import("./pages/traffic-analysis-content").then((m) => ({
    default: m.TrafficAnalysisContent,
  }))
);
const DRTAnalysisContent = lazy(() =>
  import("./pages/drt-analysis-content").then((m) => ({
    default: m.DRTAnalysisContent,
  }))
);
const ODAnalysisContent = lazy(() =>
  import("./pages/od-analysis-content").then((m) => ({
    default: m.ODAnalysisContent,
  }))
);

type ActivePage =
  | "dashboard"
  | "traffic"
  | "heatmap"
  | "traffic-analysis"
  | "drt-analysis"
  | "od-analysis"
  | "chatbot";

// 채팅 메시지 타입 정의
interface ChatMessage {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  confidence?: number;
}

// Month names in Korean
const monthNames = [
  "1월",
  "2월",
  "3월",
  "4월",
  "5월",
  "6월",
  "7월",
  "8월",
  "9월",
  "10월",
  "11월",
  "12월",
];

// Seoul Districts Data
const seoulDistricts = [
  "강남구",
  "강동구",
  "강북구",
  "강서구",
  "관악구",
  "광진구",
  "구로구",
  "금천구",
  "노원구",
  "도봉구",
  "동대문구",
  "동작구",
  "마포구",
  "서대문구",
  "서초구",
  "성동구",
  "성북구",
  "송파구",
  "양천구",
  "영등포구",
  "용산구",
  "은평구",
  "종로구",
  "중구",
  "중랑구",
];


// Loading component
const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-64">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
  </div>
);

export function DDFDashboard() {
  const [activePage, setActivePage] = useState<ActivePage>("dashboard");
  const [selectedModel, setSelectedModel] = useState("교통취약지");
  const [selectedMonth, setSelectedMonth] = useState<string>("7");
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  
  // 채팅 관련 상태
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // 탭별 기본 지역 설정
  const getDefaultRegionForPage = (pageId: ActivePage): string => {
    switch (pageId) {
      case "dashboard":
        return "전체"; // 대시보드 개요는 전체로 시작
      case "heatmap":
        return "전체"; // 히트맵도 전체로 시작
      case "traffic-analysis":
        return "전체"; // 교통 패턴 분석도 전체로 시작
      case "traffic":
        return "전체"; // 교통 분석도 전체로 시작
      case "drt-analysis":
      default:
        return "강남구"; // 나머지는 강남구로 시작
    }
  };

  // 현재 페이지에 맞는 지역 상태
  const [selectedRegion, setSelectedRegion] = useState(
    getDefaultRegionForPage(activePage)
  );
  const [showRegionSelector, setShowRegionSelector] = useState(false);
  
  // DRT 분석 탭에서 지도가 선택한 구를 헤더에 반영하기 위한 상태
  const [drtSelectedDistrict, setDrtSelectedDistrict] = useState<string | null>(null);
  const regionSelectorRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (regionSelectorRef.current && !regionSelectorRef.current.contains(event.target as Node)) {
        setShowRegionSelector(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 채팅 메시지 스크롤 자동 이동
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // RAG API 호출 함수
  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isProcessing) return;

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now().toString() + '-user',
      type: 'user',
      content: message.trim(),
      timestamp: new Date(),
    };

    setChatMessages(prev => [...prev, userMessage]);
    setInputMessage("");
    setIsProcessing(true);

    // 로딩 메시지 추가
    const loadingMessage: ChatMessage = {
      id: Date.now().toString() + '-ai-loading',
      type: 'ai',
      content: '답변을 생성 중입니다...',
      timestamp: new Date(),
      isLoading: true,
    };

    setChatMessages(prev => [...prev, loadingMessage]);

    try {
      const response: RAGQueryResponse = await apiService.queryRAG({
        query: message.trim(),
        use_multi_query: true,
        include_sources: true,
        backend_data: true,
        summary_only: false,
      });

      // 로딩 메시지 제거하고 실제 응답 추가
      setChatMessages(prev => {
        const filteredMessages = prev.filter(msg => msg.id !== loadingMessage.id);
        const aiResponse: ChatMessage = {
          id: Date.now().toString() + '-ai',
          type: 'ai',
          content: response.answer,
          timestamp: new Date(),
          confidence: response.confidence,
        };
        return [...filteredMessages, aiResponse];
      });

    } catch (error) {
      // 에러 처리
      setChatMessages(prev => {
        const filteredMessages = prev.filter(msg => msg.id !== loadingMessage.id);
        const errorMessage: ChatMessage = {
          id: Date.now().toString() + '-ai-error',
          type: 'ai',
          content: '죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
          timestamp: new Date(),
        };
        return [...filteredMessages, errorMessage];
      });
      
      console.error('RAG API Error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  // 예시 질문 클릭 핸들러
  const handleExampleClick = (example: string) => {
    handleSendMessage(example);
  };

  // Enter 키 처리
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputMessage);
    }
  };

  const handleRegionSelect = (region: string) => {
    setSelectedRegion(region);
    setShowRegionSelector(false);
  };

  // 페이지 변경시 해당 페이지의 기본 지역으로 리셋
  const handlePageChange = (pageId: ActivePage) => {
    if (pageId === "chatbot") {
      setChatOpen(!chatOpen);
      return;
    }
    setActivePage(pageId);
    setSelectedRegion(getDefaultRegionForPage(pageId));
    
    // DRT 분석 탭이 아닌 곳으로 이동할 때 DRT 구 선택 상태 초기화
    if (pageId !== "drt-analysis") {
      setDrtSelectedDistrict(null);
    }
    // 챗봇은 다른 탭으로 이동해도 유지됨
  };

  // Navigation items with custom icons - 정책담당자 의사결정 스토리보드 순서
  const navigationItems = [
    { id: "dashboard", label: "대시보드 개요", iconPath: "/sidebar_icon/대시보드개요_사이드바.png" },
    { id: "od-analysis", label: "OD 분석", iconPath: "/sidebar_icon/OD분석_사이드바.png" },
    { id: "drt-analysis", label: "DRT 분석", iconPath: "/sidebar_icon/DRT분석_사이드바.png" },
    { id: "traffic-analysis", label: "이상 패턴 분석", iconPath: "/sidebar_icon/이상패턴분석_사이드바.png" },
    { id: "traffic", label: "교통 패턴 분석", iconPath: "/sidebar_icon/교통패턴분석_사이드바.png" },
    { id: "heatmap", label: "교통량 분석", iconPath: "/sidebar_icon/교통량분석_사이드바.png" },
    { id: "chatbot", label: "AI 교통 상담", iconPath: "/sidebar_icon/RAG채팅_사이드바.png" },
  ];

  // Render different page content based on active page
  const renderPageContent = () => {
    switch (activePage) {
      case "dashboard":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DashboardOverviewContent
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
              onNavigateToTab={(tabId: string) => handlePageChange(tabId as ActivePage)}
            />
          </Suspense>
        );
      case "traffic":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TrafficContent
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
            />
          </Suspense>
        );
      case "heatmap":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <HeatmapContent
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
            />
          </Suspense>
        );
      case "traffic-analysis":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TrafficAnalysisContent
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
            />
          </Suspense>
        );
      case "drt-analysis":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DRTAnalysisContent
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
              onDistrictChange={(district: string) => {
                console.log("📥 Received district change from DRT analysis:", district);
                setDrtSelectedDistrict(district);
              }}
            />
          </Suspense>
        );
      case "od-analysis":
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ODAnalysisContent
              selectedMonth={selectedMonth}
              selectedRegion={selectedRegion}
            />
          </Suspense>
        );
      default:
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DashboardContent selectedMonth={selectedMonth} />
          </Suspense>
        );
    }
  };

  return (
    <SidebarProvider>
      <Sidebar className="border-r">
        <SidebarHeader className="border-b px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <BarChart3 className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-bold truncate text-gray-900">DDF 대시보드</h2>
              <p className="text-sm text-gray-700 truncate font-semibold">
                DRT 적합성 분석 시스템
              </p>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent className="px-3 py-6">
          {/* Navigation Menu */}
          <SidebarGroup>
            <SidebarGroupLabel className="text-lg font-bold mb-4 text-gray-900">메뉴</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-3">
                {navigationItems.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      onClick={() => handlePageChange(item.id as ActivePage)}
                      isActive={item.id === "chatbot" ? chatOpen : activePage === item.id}
                      className="w-full justify-start py-4 px-4 text-base font-bold h-auto min-h-[3.5rem] whitespace-normal text-gray-800"
                    >
                      <Image 
                        src={item.iconPath} 
                        alt={item.label}
                        width={24}
                        height={24}
                        className="w-6 h-6 flex-shrink-0"
                      />
                      <span className="text-base flex-1 leading-relaxed font-bold">{item.label}</span>
                      {(item.id === "chatbot" ? chatOpen : activePage === item.id) && (
                        <ChevronRight className="ml-auto h-5 w-5 flex-shrink-0" />
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

        </SidebarContent>

        <SidebarRail />
      </Sidebar>

      {/* 확장 가능한 챗봇 패널 - Fixed Position */}
      <div className={`
        fixed top-0 right-0 h-screen bg-gradient-to-br from-blue-50 to-indigo-100 border-l shadow-lg z-50 transition-all duration-300 overflow-hidden
        ${chatOpen ? 'w-80 translate-x-0' : 'w-80 translate-x-full'}
      `}>
        {chatOpen && (
          <div className="flex flex-col h-full">
            {/* 채팅 헤더 */}
            <div className="flex-shrink-0 bg-white shadow-sm border-b p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Image 
                    src="/sidebar_icon/RAG채팅_사이드바.png" 
                    alt="AI 교통 상담"
                    width={24}
                    height={24}
                    className="w-6 h-6"
                  />
                  <div>
                    <h3 className="font-semibold text-gray-900">AI 교통 상담</h3>
                    <p className="text-xs text-gray-600">
                      서울시 교통 데이터 분석
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => setChatOpen(false)}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            {/* 채팅 영역 */}
            <div className="flex-1 flex flex-col overflow-hidden">
              <div 
                ref={chatContainerRef}
                className="flex-1 overflow-y-auto p-4 space-y-3"
              >
                {/* 초기 메시지 또는 채팅 메시지들 */}
                {chatMessages.length === 0 ? (
                  // 시작 메시지
                  <div className="flex justify-start">
                    <div className="max-w-xs px-3 py-2 rounded-lg bg-white shadow-sm">
                      <div className="flex items-start gap-2">
                        <Image 
                          src="/sidebar_icon/RAG채팅_사이드바.png" 
                          alt="AI"
                          width={16}
                          height={16}
                          className="w-4 h-4 mt-0.5 flex-shrink-0"
                        />
                        <div>
                          <p className="text-xs text-gray-800">
                            안녕하세요! 서울시 교통 분석 AI입니다. 
                            궁금한 점을 자유롭게 질문해보세요.
                          </p>
                          <div className="mt-2 space-y-1">
                            <div className="text-xs text-gray-500">💡 예시:</div>
                            <div className="space-y-1 text-xs">
                              <div 
                                className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors"
                                onClick={() => handleExampleClick("DRT 시스템이란 뭐야?")}
                              >
                                DRT 시스템이란 뭐야?
                              </div>
                              <div 
                                className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors"
                                onClick={() => handleExampleClick("수요응답형 교통의 장점은?")}
                              >
                                수요응답형 교통의 장점은?
                              </div>
                              <div 
                                className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors"
                                onClick={() => handleExampleClick("교통 데이터 분석 방법을 알려줘")}
                              >
                                교통 데이터 분석 방법을 알려줘
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  // 채팅 메시지들
                  chatMessages.map((message) => (
                    <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xs px-3 py-2 rounded-lg ${
                        message.type === 'user' 
                          ? 'bg-blue-500 text-white' 
                          : 'bg-white shadow-sm'
                      }`}>
                        {message.type === 'ai' && (
                          <div className="flex items-start gap-2">
                            <Image 
                              src="/sidebar_icon/RAG채팅_사이드바.png" 
                              alt="AI"
                              width={16}
                              height={16}
                              className="w-4 h-4 mt-0.5 flex-shrink-0"
                            />
                            <div className="flex-1">
                              <p className={`text-xs ${message.isLoading ? 'text-gray-500' : 'text-gray-800'}`}>
                                {message.isLoading && (
                                  <span className="inline-flex items-center gap-1">
                                    <span className="animate-pulse">●</span>
                                    <span className="animate-pulse delay-100">●</span>
                                    <span className="animate-pulse delay-200">●</span>
                                  </span>
                                )}
                                {message.content}
                              </p>
                              {message.confidence && !message.isLoading && (
                                <div className="mt-1 text-xs text-gray-400">
                                  신뢰도: {Math.round(message.confidence * 100)}%
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                        {message.type === 'user' && (
                          <p className="text-xs">{message.content}</p>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
              
              {/* 입력 영역 */}
              <div className="flex-shrink-0 bg-white border-t p-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="질문을 입력하세요..."
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isProcessing}
                  />
                  <button 
                    onClick={() => handleSendMessage(inputMessage)}
                    className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                    disabled={isProcessing || !inputMessage.trim()}
                  >
                    {isProcessing ? (
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    ) : (
                      '전송'
                    )}
                  </button>
                </div>
                {isProcessing && (
                  <div className="mt-1 text-xs text-blue-500 text-center animate-pulse">
                    AI가 답변을 생성하고 있습니다...
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <SidebarInset className={`${chatOpen ? 'mr-80' : ''} transition-all duration-300`}>
        {/* Header */}
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-6">
          <SidebarTrigger className="-ml-1" />
          <div className="flex flex-1 items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold">
                {navigationItems.find((item) => item.id === activePage)
                  ?.label || "대시보드"}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              {/* 지역 선택 버튼 그리드 */}
              <div className="relative" ref={regionSelectorRef}>
                <Button
                  variant="outline"
                  onClick={() => {
                    // DRT 분석 탭에서는 읽기 전용
                    if (activePage !== "drt-analysis") {
                      setShowRegionSelector(!showRegionSelector);
                    }
                  }}
                  className={`w-[140px] justify-between ${
                    activePage === "drt-analysis" ? 'cursor-default opacity-75' : 'cursor-pointer'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    <span>
                      {activePage === "drt-analysis" && drtSelectedDistrict
                        ? drtSelectedDistrict
                        : (selectedRegion === "전체" ? "전체 지역" : selectedRegion)
                      }
                    </span>
                  </div>
                  {activePage !== "drt-analysis" && (
                    <ChevronDown className={`h-4 w-4 transition-transform ${
                      showRegionSelector ? 'rotate-180' : ''
                    }`} />
                  )}
                  {activePage === "drt-analysis" && (
                    <div className="relative group">
                      <Link2 className="h-3 w-3 text-blue-400" />
                      <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                        지도에서 선택된 구역
                      </div>
                    </div>
                  )}
                </Button>
                
                {showRegionSelector && (
                  <div className="absolute top-full left-0 mt-2 p-4 bg-white border rounded-lg shadow-xl z-50 min-w-[400px]">
                    <div className="mb-3">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">지역 선택</h3>
                      <div className="grid grid-cols-1 gap-2">
                        <Button
                          variant={selectedRegion === "전체" ? "default" : "outline"}
                          size="sm"
                          onClick={() => handleRegionSelect("전체")}
                          className="justify-start"
                        >
                          <MapPin className="h-3 w-3 mr-2" />
                          전체 지역
                        </Button>
                      </div>
                    </div>
                    
                    <div className="border-t pt-3">
                      <h4 className="text-xs font-medium text-gray-500 mb-2">서울시 25개 자치구</h4>
                      <div className="grid grid-cols-5 gap-1">
                        {seoulDistricts.map((district) => (
                          <Button
                            key={district}
                            variant={selectedRegion === district ? "default" : "outline"}
                            size="sm"
                            onClick={() => handleRegionSelect(district)}
                            className="text-xs h-8 px-2"
                          >
                            {district}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {monthNames.map((month, index) => (
                    <SelectItem key={index + 1} value={(index + 1).toString()}>
                      {month}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-2">
                <span className="text-base">최신업데이트 (07-31)</span>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6">{renderPageContent()}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
