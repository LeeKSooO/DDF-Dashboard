// 상수 정의
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// 지역 목록
export const REGIONS = [
  "전체", "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", 
  "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", 
  "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", 
  "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
] as const;

// 월 목록
export const MONTHS = [
  "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
  "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"
] as const;

// 월 이름 한국어
export const MONTH_NAMES = [
  "1월", "2월", "3월", "4월", "5월", "6월",
  "7월", "8월", "9월", "10월", "11월", "12월"
] as const;

// DRT 모델 타입
export const DRT_MODELS = ["교통취약지", "출퇴근", "관광"] as const;

// 모델 타입 매핑
export const MODEL_TYPE_MAPPING = {
  "교통취약지": "vulnerable",
  "출퇴근": "commute", 
  "관광": "tourist"
} as const;

// 색상 팔레트
export const COLORS = {
  // 메인 색상
  primary: '#3B82F6',
  secondary: '#6B7280',
  
  // 상태 색상
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#0EA5E9',
  
  // DRT 모델별 색상
  vulnerable: '#8B5CF6', // 보라색
  commute: '#3B82F6',    // 파란색
  tourist: '#10B981',    // 초록색
  
  // 파스텔 색상
  pastel: {
    red: '#fca5a5',
    orange: '#fed7aa',
    yellow: '#fde68a',
    green: '#bbf7d0',
    blue: '#bfdbfe',
    purple: '#ddd6fe',
    gray: '#d1d5db'
  }
} as const;

// 서울시 경계 좌표
export const SEOUL_BOUNDS = {
  center: [37.5665, 126.9780] as [number, number],
  boundingBox: [
    [37.413, 126.734], // Southwest corner 
    [37.715, 127.269]  // Northeast corner
  ] as [[number, number], [number, number]]
} as const;

// 지도 설정
export const MAP_CONFIG = {
  defaultZoom: 12,
  minZoom: 10,
  maxZoom: 16,
  tileUrl: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
} as const;