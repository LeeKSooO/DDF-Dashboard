"""
DRT Score 분석 API 응답 스키마
출퇴근형, 관광특화형, 교통취약지형 3개 모델에 따른 DRT 점수 계산
"""

from typing import List
from pydantic import BaseModel, Field


# ==========================================
# 기본 구성 요소 스키마
# ==========================================

class StationInfoSchema(BaseModel):
    """정류장 상세 정보 (지리적 정보 포함)"""
    station_id: str = Field(..., description="정류장 ID (node_id)")
    station_name: str = Field(..., description="정류장명")
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    district_name: str = Field(..., description="구명")
    administrative_dong: str = Field(..., description="행정동명")
    
    class Config:
        schema_extra = {
            "example": {
                "station_id": "121000012",
                "station_name": "지하철2호선강남역",
                "latitude": 37.500785,
                "longitude": 127.02637,
                "district_name": "강남구",
                "administrative_dong": "역삼1동"
            }
        }


# ==========================================
# 1. 출퇴근형 DRT Score 스키마
# ==========================================

class CommuterDRTScoreSchema(BaseModel):
    """출퇴근형 DRT Score 분석"""
    
    hour: int = Field(..., description="시간대 (0-23)")
    tc_score: float = Field(..., description="시간 집중도 지수 (TC_t): 특정 시간 배차수 / 일일 최대 배차수")
    pdr_score: float = Field(..., description="피크 수요 비율 (PDR_t): 특정 시간 승하차수 / 일일 최대 승하차수")
    ru_score: float = Field(..., description="노선 활용도 (RU_t): 시간별 해당 정류장을 지나는 노선에 속한 구간별 승객수, min-max 정규화")
    pcw_score: float = Field(..., description="POI 카테고리 가중치 (PCW)")
    total_score: float = Field(..., description="출퇴근형 총 DRT 점수")


# ==========================================
# 2. 관광특화형 DRT Score 스키마
# ==========================================

class TourismDRTScoreSchema(BaseModel):
    """관광특화형 DRT Score 분석"""
    
    hour: int = Field(..., description="시간대 (0-23)")
    tc_score: float = Field(..., description="관광 집중도 (TC_t): 배차수 정규화 (10-16시 가중치 1.2)")
    tdr_score: float = Field(..., description="관광 수요 비율 (TDR_t): 승하차수 정규화 (10-16시 가중치 1.1)")
    ru_score: float = Field(..., description="구간 이용률 (RU_t): 구간별 승객 밀도")
    pcw_score: float = Field(..., description="POI 관광 가중치 (PCW): 관광특구>고궁>상권>공원")
    total_score: float = Field(..., description="관광특화형 총 DRT 점수")


# ==========================================
# 3. 교통취약지형 DRT Score 스키마
# ==========================================

class VulnerableDRTScoreSchema(BaseModel):
    """교통취약지형 DRT Score 분석"""
    
    hour: int = Field(..., description="시간대 (0-23)")
    var_score: float = Field(..., description="취약 접근성 비율 (VAR_t): 특정시간 배차수 / 취약시간대 총 배차수")
    sed_score: float = Field(..., description="사회 형평성 수요 (SED_t): 특정시간 승하차수 / 취약시간대 총 승하차수")
    mdi_score: float = Field(..., description="이동성 불리 지수 (MDI_t): (1000 - 구간별승객수) / 1000")
    avs_score: float = Field(..., description="지역 취약성 점수 (AVS): 취약성 카테고리별 점수")
    total_score: float = Field(..., description="교통취약지형 총 DRT 점수")


# ==========================================
# 4. 히트맵용 정류장별 DRT Score 스키마
# ==========================================

# 좌표 스키마 추가
class CoordinateSchema(BaseModel):
    """정류장 좌표 스키마"""
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")

class StationDRTScoreSummary(BaseModel):
    """히트맵 표시용 정류장별 DRT 요약 점수"""
    station_id: str = Field(..., description="정류장 ID")
    station_name: str = Field(..., description="정류장명")
    coordinate: CoordinateSchema = Field(..., description="정류장 좌표")
    drt_score: float = Field(..., description="DRT 종합 점수 (0-100)")
    peak_hour: int = Field(..., description="최고 점수 시간대")
    
    class Config:
        schema_extra = {
            "example": {
                "station_id": "121000012",
                "station_name": "지하철2호선강남역",
                "coordinate": {"lat": 37.500785, "lng": 127.02637},
                "drt_score": 87.5,
                "peak_hour": 8
            }
        }


class DistrictDRTScoreResponse(BaseModel):
    """구별 DRT Score 히트맵 응답 (모델별)"""
    district_name: str = Field(..., description="구명")
    model_type: str = Field(..., description="DRT 모델 타입 (commuter/tourism/vulnerable)")
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)")
    stations: List[StationDRTScoreSummary] = Field(..., description="정류장별 DRT 점수 요약 (점수 높은 순 정렬)")
    top_stations: List[StationDRTScoreSummary] = Field(..., description="상위 5개 정류장 (대시보드 Top 5 리스트용)", max_items=5)
    
    class Config:
        schema_extra = {
            "example": {
                "district_name": "강남구",
                "model_type": "commuter",
                "analysis_month": "2025-07",
                "stations": [],
                "top_stations": []
            }
        }


# ==========================================
# 5. 정류장 상세 DRT Score 응답 스키마 (클릭 시)
# ==========================================

class StationDRTDetailResponse(BaseModel):
    """정류장 클릭 시 피처 패널 업데이트용 DRT Score 응답"""
    
    # 정류장 정보
    station: StationInfoSchema = Field(..., description="정류장 정보")
    
    # 분석 정보
    model_type: str = Field(..., description="DRT 모델 타입")
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)")
    
    # 현재 선택된 시간대 정보 (기본값: peak_hour)
    current_hour: int = Field(..., description="현재 조회 중인 시간대 (defalut: peak)")
    current_score: float = Field(..., description="현재 시간대 DRT 점수")
    
    # 월간 최고 점수 정보
    peak_score: float = Field(..., description="월간 최고 DRT 점수")
    peak_hour: int = Field(..., description="최고 점수 시간대")
    monthly_average: float = Field(..., description="월간 평균 DRT 점수")
    
    # 세부 지표 (모델에 따라 다름)
    feature_scores: dict = Field(..., description="세부 지표 점수 (tc_score, pdr_score 등)")
    
    # 시간대별 전체 점수 (차트용)
    hourly_scores: List[dict] = Field(..., description="24시간별 월 집계 점수 데이터")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {},
                "model_type": "commuter",
                "analysis_month": "2025-07",
                "current_hour": 8,
                "current_score": 87.5,
                "peak_score": 87.5,
                "peak_hour": 8,
                "monthly_average": 65.2,
                "feature_scores": {
                    "tc_score": 0.95,
                    "pdr_score": 0.87,
                    "ru_score": 0.75,
                    "pcw_score": 1.0
                },
                "hourly_scores": [
                    {"hour": 0, "score": 45.2},
                    {"hour": 8, "score": 87.5},
                    {"hour": 18, "score": 82.1},
                    { ... }
                ]
            }
        }


