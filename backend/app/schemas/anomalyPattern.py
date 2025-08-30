"""
구별 교통 특이패턴 분석 API 응답 스키마
웹 대시보드에서 특정 구를 선택했을 때, 해당 구의 6가지 특이패턴 정류장을 제공
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import date


# ==========================================
# 1. 기본 구성 요소 스키마
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
                "station_id": "113000422",
                "station_name": "홍대입구역",
                "latitude": 37.556641,
                "longitude": 126.923466,
                "district_name": "마포구",
                "administrative_dong": "서교동"
            }
        }


class DistrictAverageSchema(BaseModel):
    """구 전체 평균 지표 (비교 기준)"""
    avg_weekend_traffic: float = Field(..., description="구 평균 주말 교통량 (%)")
    avg_night_ride_traffic: float = Field(..., description="구 평균 심야 승차인원수 (%)")
    avg_rush_hour_ride_traffic: float = Field(..., description="구 평균 러시아워 승차인원수")
    avg_rush_hour_alight_traffic: float = Field(..., description="구 평균 러시아워 하차인원수")
    avg_lunch_spike_pct: float = Field(..., description="구 평균 점심 하차인원수 (%)")
    avg_cv_coefficient: float = Field(..., description="구 평균 변동계수")
    
    total_stations: int = Field(..., description="구 전체 정류장 수")
    analysis_period_days: int = Field(..., description="분석 기간 (일)")
    
    class Config:
        schema_extra = {
            "example": {
                "avg_weekend_increase_pct": 15.2,
                "avg_night_traffic_ratio": 4.8,
                "avg_rush_hour_traffic": 2850.5,
                "avg_lunch_spike_pct": 25.7,
                "avg_cv_coefficient": 1.35,
                "total_stations": 547,
                "analysis_period_days": 16
            }
        }




# ==========================================
# 2. 6가지 특이패턴별 상세 스키마
# ==========================================

# 1. 주말 고수요 정류장
class WeekendDominantStationSchema(BaseModel):
    """주말 고수요 정류장 패턴
    
    비즈니스 로직:
    1. 주말 총 교통량 기준 상위 정류장 선별
    2. 각 정류장의 시간대별 교통량 분석으로 피크 시간대 추출
    """
    station: StationInfoSchema
    weekend_total_traffic: int = Field(..., description="주말 총 교통량")
    weekend_peak_hours: List[int] = Field(
        ..., 
        max_items=3,
        description="주말 피크 시간대 TOP 3 (교통량 순)"
    )
    weekend_peak_traffic: List[int] = Field(
        ...,
        max_items=3,
        description="피크 시간대별 교통량"
    )
    rank: int = Field(..., description="주말 교통량 순위")
    vs_district_avg: float = Field(..., description="구평균 대비 주말 수요 배수")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000422",
                    "station_name": "홍대입구역",
                    "latitude": 37.556641,
                    "longitude": 126.923466,
                    "district_name": "마포구",
                    "administrative_dong": "서교동"
                },
                "weekend_total_traffic": 67712,
                "weekend_daily_avg": 16928.0,
                "weekend_peak_hours": [16, 17, 18],
                "weekend_peak_traffic": [5223, 5212, 4969],
                "rank": 1
            }
        }


# 2. 심야시간 고수요 정류장
class NightDemandStationSchema(BaseModel):
    """심야시간 고수요 정류장 (23-03시)
    
    비즈니스 로직:
    1. 심야시간 총 승차인원 기준 상위 정류장 선별
    2. 시간대별 세부 승차량 분석 (23,0,1,2,3시)
    3. 구평균 대비 수요 배수 계산
    """
    station: StationInfoSchema
    total_night_ride: int = Field(..., description="심야시간 총 승차인원 (23-03시)")
    night_hours_traffic: List[int] = Field(
        ...,
        min_items=5,
        max_items=5,
        description="시간대별 승차량 [23시, 0시, 1시, 2시, 3시]"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 심야수요 배수")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000422",
                    "station_name": "홍대입구역",
                    "latitude": 37.556641,
                    "longitude": 126.923466,
                    "district_name": "마포구",
                    "administrative_dong": "서교동"
                },
                "total_night_ride": 18494,
                "avg_night_ride": 3698.8,
                "night_hours_traffic": [10087, 4823, 1961, 1004, 619],
                "peak_night_hour": 23,
                "vs_district_avg": 4109.8
            }
        }


# 3. 출퇴근 시간대 고수요 정류장
class RushHourStationSchema(BaseModel):
    """출퇴근 시간대 고수요 정류장 (06-08, 17-19시)"""
    station: StationInfoSchema
    total_rush_ride: int = Field(..., description="러시아워 총 승차인원 (06-08, 17-19시)")
    morning_rush_ride: int = Field(..., description="오전 러시아워 승차인원 (06-08시)")
    evening_rush_ride: int = Field(..., description="오후 러시아워 승차인원 (17-19시)")
    peak_pattern: Literal["오전집중", "오후집중", "균등분포"] = Field(
        ..., description="러시아워 패턴 유형"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 러시아워 수요 배수")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000422",
                    "station_name": "홍대입구역",
                    "latitude": 37.556641,
                    "longitude": 126.923466,
                    "district_name": "마포구",
                    "administrative_dong": "서교동"
                },
                "total_rush_ride": 51899,
                "morning_rush_ride": 13284,
                "evening_rush_ride": 38615,
                "peak_pattern": "오후집중",
                "vs_district_avg": 5.8
            }
        }


# 4. 점심시간 특화 정류장 (하차 중심)
class LunchTimeStationSchema(BaseModel):
    """점심시간 특화 정류장 (11-13시 하차 중심)"""
    station: StationInfoSchema
    total_lunch_alight: int = Field(..., description="점심시간 총 하차인원 (11-13시)")
    avg_lunch_alight_per_hour: float = Field(..., description="점심시간당 평균 하차인원")
    lunch_spike_pct: float = Field(..., description="점심시간 하차 증가율 (일평균 대비 %)")
    vs_district_avg: float = Field(..., description="구 평균 대비 점심시간 증가율 배수")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000129",
                    "station_name": "합정역",
                    "latitude": 37.550218,
                    "longitude": 126.915307,
                    "district_name": "마포구",
                    "administrative_dong": "서교동"
                },
                "total_lunch_alight": 1328,
                "avg_lunch_alight_per_hour": 442.7,
                "lunch_spike_pct": 273.2,
                "vs_district_avg": 10.6
            }
        }


# 5. 구역 특성별 정류장 (승하차 불균형 기준)
class AreaTypeStationSchema(BaseModel):
    """구역 특성별 정류장 (승하차 불균형 분석)"""
    station: StationInfoSchema
    area_type: Literal["주거지역", "업무지역", "상업지역", "교통허브"] = Field(
        ..., description="지역 특성 유형"
    )
    total_ride: int = Field(..., description="총 승차인원")
    total_alight: int = Field(..., description="총 하차인원")
    ride_ratio: float = Field(..., description="승차 비율 (%)")
    alight_ratio: float = Field(..., description="하차 비율 (%)")
    morning_ride: int = Field(..., description="오전 러시아워 승차 (06-09시)")
    morning_alight: int = Field(..., description="오전 러시아워 하차 (06-09시)")
    evening_ride: int = Field(..., description="오후 러시아워 승차 (17-20시)")
    evening_alight: int = Field(..., description="오후 러시아워 하차 (17-20시)")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000412",
                    "station_name": "합정역",
                    "latitude": 37.549546,
                    "longitude": 126.913799,
                    "district_name": "마포구",
                    "administrative_dong": "합정동"
                },
                "area_type": "주거지역",
                "total_ride": 73383,
                "total_alight": 19512,
                "ride_ratio": 79.0,
                "alight_ratio": 21.0,
                "morning_ride": 11788,
                "morning_alight": 2072,
                "evening_ride": 23686,
                "evening_alight": 6300
            }
        }


# 6. 시계열 변동지수가 높은 정류장
class HighVolatilityStationSchema(BaseModel):
    """시계열 변동지수가 높은 정류장"""
    station: StationInfoSchema
    cv_coefficient: float = Field(..., description="변동계수 (표준편차/평균)")
    average_traffic: float = Field(..., description="평균 교통량")
    std_deviation: float = Field(..., description="표준편차")
    max_traffic: int = Field(..., description="최대 교통량")
    min_traffic: int = Field(..., description="최소 교통량")
    peak_volatility_hour: int = Field(..., description="최대 변동지수 시간대")
    peak_hour_cv: float = Field(..., description="해당 시간대 변동계수")
    volatility_type: Literal["초고변동", "고변동", "중변동", "저변동"] = Field(
        ..., description="변동성 유형 (CV 기준)"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 변동계수 배수")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113000428",
                    "station_name": "난지한강공원",
                    "latitude": 37.568751,
                    "longitude": 126.875258,
                    "district_name": "마포구",
                    "administrative_dong": "상암동"
                },
                "cv_coefficient": 3.064,
                "average_traffic": 5.3,
                "std_deviation": 16.3,
                "max_traffic": 167,
                "min_traffic": 1,
                "peak_volatility_hour": 21,
                "peak_hour_cv": 2.123,
                "volatility_type": "초고변동",
                "vs_district_avg": 2.27
            }
        }


# ==========================================
# 3. 메인 응답 스키마 (6가지 특이패턴)
# ==========================================

class AnomalyPatternResponse(BaseModel):
    """교통 특이패턴 분석 API 메인 응답"""
    
    # 기본 메타 정보
    district_name: str = Field(..., description="분석 대상 구명")
    analysis_period: str = Field(..., description="분석 기간 (YYYY-MM-DD ~ YYYY-MM-DD)")
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)")
    generated_at: str = Field(..., description="분석 생성 시간 (ISO 8601)")
    
    # 구 전체 평균 지표 (비교 기준)
    district_averages: DistrictAverageSchema = Field(
        ..., description="구 전체 평균 지표 (각 패턴별 비교 기준)"
    )
    
    # 6가지 특이패턴별 상위 5개 정류장
    weekend_dominant_stations: List[WeekendDominantStationSchema] = Field(
        ..., 
        max_items=5,
        description="주말 우세 정류장 (관광지/명소 특성) TOP 5"
    )
    
    night_demand_stations: List[NightDemandStationSchema] = Field(
        ..., 
        max_items=5,
        description="심야시간 고수요 정류장 (23-03시) TOP 5"
    )
    
    rush_hour_stations: List[RushHourStationSchema] = Field(
        ..., 
        max_items=5,
        description="출퇴근 시간대 고수요 정류장 (06-08, 17-19시) TOP 5"
    )
    
    lunch_time_stations: List[LunchTimeStationSchema] = Field(
        ..., 
        max_items=5,
        description="점심시간 특화 정류장 (11-13시 하차 중심) TOP 5"
    )
    
    area_type_stations: List[AreaTypeStationSchema] = Field(
        ..., 
        max_items=5,
        description="구역 특성별 정류장 (승하차 불균형 기준) TOP 5"
    )
    
    high_volatility_stations: List[HighVolatilityStationSchema] = Field(
        ..., 
        max_items=5,
        description="시계열 변동지수가 높은 정류장 TOP 5"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "district_name": "마포구",
                "analysis_period": "2025-07-16 ~ 2025-07-31",
                "analysis_month": "2025-07",
                "generated_at": "2025-08-30T10:30:00Z",
                "district_averages": {
                    "avg_weekend_increase_pct": 15.2,
                    "avg_night_traffic_ratio": 4.8,
                    "avg_rush_hour_traffic": 2850.5,
                    "avg_lunch_spike_pct": 25.7,
                    "avg_cv_coefficient": 1.35,
                    "total_stations": 547,
                    "analysis_period_days": 16
                },
                "weekend_dominant_stations": [],
                "night_demand_stations": [],
                "rush_hour_stations": [],
                "lunch_time_stations": [],
                "area_type_stations": [],
                "high_volatility_stations": []
            }
        }


# ==========================================
# 4. 요청 스키마
# ==========================================

class AnomalyPatternFilterSchema(BaseModel):
    """교통 특이패턴 분석 필터 옵션"""
    top_n: int = Field(
        5,
        ge=1,
        le=10,
        description="각 패턴별 상위 N개 정류장 (기본값: 5개)"
    )
    min_weekend_increase_pct: Optional[float] = Field(
        None,
        ge=0,
        description="주말 우세 패턴 최소 증가율 임계값 (%)"
    )
    min_night_traffic_ratio: Optional[float] = Field(
        None,
        ge=0,
        description="심야수요 패턴 최소 교통량 비율 임계값 (%)"
    )
    min_rush_hour_traffic: Optional[int] = Field(
        None,
        ge=0,
        description="러시아워 패턴 최소 교통량 임계값"
    )
    min_lunch_spike_pct: Optional[float] = Field(
        None,
        ge=0,
        description="점심특화 패턴 최소 증가율 임계값 (%)"
    )
    min_cv_coefficient: Optional[float] = Field(
        None,
        ge=0,
        description="변동성 패턴 최소 CV계수 임계값"
    )


class AnomalyPatternRequest(BaseModel):
    """교통 특이패턴 분석 요청"""
    district_name: str = Field(..., description="분석 대상 구명 (예: 마포구, 강남구)")
    analysis_month: date = Field(..., description="분석 월 (YYYY-MM-DD 형식, 월 첫째 날)")
    filters: Optional[AnomalyPatternFilterSchema] = Field(
        None,
        description="분석 필터 옵션"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "district_name": "마포구",
                "analysis_month": "2025-07-01",
                "filters": {
                    "top_n": 5,
                    "min_weekend_increase_pct": 20.0,
                    "min_night_traffic_ratio": 3.0,
                    "min_rush_hour_traffic": 1000,
                    "min_lunch_spike_pct": 50.0,
                    "min_cv_coefficient": 1.5
                }
            }
        }