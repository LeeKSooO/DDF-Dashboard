"use client";

import { useState, lazy, Suspense } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
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
  RefreshCw,
  BarChart3,
  ChevronRight,
  Bell,
  Target,
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

type ActivePage =
  | "dashboard"
  | "traffic"
  | "heatmap"
  | "traffic-analysis"
  | "drt-analysis"
  | "chatbot";

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

const vulnerableAreas = [
  {
    rank: 1,
    area: "금천구 시흥동",
    score: 92,
    population: 15000,
    accessibility: "매우낮음",
    priority: "최우선",
  },
  {
    rank: 2,
    area: "강서구 가양동",
    score: 88,
    population: 22000,
    accessibility: "낮음",
    priority: "최우선",
  },
  {
    rank: 3,
    area: "구로구 항동",
    score: 85,
    population: 18000,
    accessibility: "낮음",
    priority: "우선",
  },
  {
    rank: 4,
    area: "영등포구 신길동",
    score: 82,
    population: 25000,
    accessibility: "보통",
    priority: "우선",
  },
  {
    rank: 5,
    area: "동작구 상도동",
    score: 78,
    population: 20000,
    accessibility: "보통",
    priority: "검토",
  },
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
  const [isRealTimeMode, setIsRealTimeMode] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState<string>("7");
  const [chatOpen, setChatOpen] = useState<boolean>(false);

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

  // 페이지 변경시 해당 페이지의 기본 지역으로 리셋
  const handlePageChange = (pageId: ActivePage) => {
    if (pageId === "chatbot") {
      setChatOpen(!chatOpen);
      return;
    }
    setActivePage(pageId);
    setSelectedRegion(getDefaultRegionForPage(pageId));
    // 챗봇은 다른 탭으로 이동해도 유지됨
  };

  // Navigation items with custom icons
  const navigationItems = [
    { id: "dashboard", label: "대시보드 개요", iconPath: "/sidebar_icon/대시보드개요_사이드바.png" },
    { id: "traffic", label: "교통 패턴 분석", iconPath: "/sidebar_icon/교통패턴분석_사이드바.png" },
    { id: "heatmap", label: "교통량 분석", iconPath: "/sidebar_icon/교통량분석_사이드바.png" },
    { id: "traffic-analysis", label: "이상 패턴 분석", iconPath: "/sidebar_icon/이상패턴분석_사이드바.png" },
    { id: "drt-analysis", label: "DRT 분석", iconPath: "/sidebar_icon/DRT분석_사이드바.png" },
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
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {/* 시작 메시지 */}
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
                            <div className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors">
                              강남구 7월 교통량?
                            </div>
                            <div className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors">
                              DRT 필요 지역은?
                            </div>
                            <div className="bg-blue-50 px-2 py-1 rounded cursor-pointer hover:bg-blue-100 transition-colors">
                              이상 패턴 특징?
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* 입력 영역 */}
              <div className="flex-shrink-0 bg-white border-t p-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="질문을 입력하세요..."
                    className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled
                  />
                  <button 
                    className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                    disabled
                  >
                    전송
                  </button>
                </div>
                <div className="mt-1 text-xs text-gray-500 text-center">
                  🚧 구현 중입니다
                </div>
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
              <Select value={selectedRegion} onValueChange={setSelectedRegion}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="전체">전체 지역</SelectItem>
                  {seoulDistricts.map((district) => (
                    <SelectItem key={district} value={district}>
                      {district}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                <Switch
                  checked={isRealTimeMode}
                  onCheckedChange={setIsRealTimeMode}
                />
                <span className="text-base">자동 업데이트</span>
              </div>
              <Button variant="outline" size="icon">
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon">
                <Bell className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6">{renderPageContent()}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
