// 색상 관련 유틸리티 함수들
import { COLORS } from './constants';

// DRT 점수에 따른 파스텔 색상 반환
export const getDRTScoreColor = (score: number): string => {
  if (score >= 80) return COLORS.pastel.red;     // 파스텔 레드
  if (score >= 60) return COLORS.pastel.orange;  // 파스텔 오렌지  
  if (score >= 40) return COLORS.pastel.yellow;  // 파스텔 노랑
  if (score >= 20) return COLORS.pastel.green;   // 파스텔 그린
  return COLORS.pastel.gray;                     // 파스텔 그레이
};

// DRT 모델별 색상 반환
export const getModelColor = (model: string): string => {
  switch (model) {
    case '교통취약지':
      return COLORS.vulnerable;
    case '출퇴근':
      return COLORS.commute;
    case '관광':
      return COLORS.tourist;
    default:
      return COLORS.secondary;
  }
};

// DRT 모델별 파스텔 색상 반환
export const getModelPastelColor = (model: string): string => {
  switch (model) {
    case '교통취약지':
      return COLORS.pastel.purple;
    case '출퇴근':
      return COLORS.pastel.blue;
    case '관광':
      return COLORS.pastel.green;
    default:
      return COLORS.pastel.gray;
  }
};

// 교통량에 따른 색상 반환
export const getTrafficColor = (traffic: number): string => {
  if (traffic > 500000) return '#FF5722'; // Red - Heavy traffic
  if (traffic > 300000) return '#FF9800'; // Orange 
  if (traffic > 200000) return '#FFC107'; // Yellow
  if (traffic > 100000) return '#4CAF50'; // Green
  if (traffic > 50000) return '#2196F3';  // Blue
  if (traffic > 20000) return '#9C27B0';  // Purple
  return '#607D8B'; // Gray - Low traffic
};

// 적합도에 따른 색상 반환
export const getSuitabilityColor = (score: number): string => {
  if (score >= 80) return COLORS.success;
  if (score >= 60) return COLORS.info;
  if (score >= 40) return COLORS.warning;
  if (score >= 20) return COLORS.error;
  return COLORS.secondary;
};

// TOP 5 정류장 색상 (금색 그라데이션)
export const getTopStationColor = (rank: number): string => {
  const goldColors = [
    '#FFD700', // 1등 - 골드
    '#FFA500', // 2등 - 오렌지골드
    '#FF8C00', // 3등 - 다크오렌지
    '#DAA520', // 4등 - 골든로드
    '#B8860B'  // 5등 - 다크골든로드
  ];
  return goldColors[rank - 1] || COLORS.secondary;
};