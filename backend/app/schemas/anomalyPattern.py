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


# 3. 러시아워 고수요 정류장 (오전/오후 분리)
class MorningRushStationSchema(BaseModel):
    """오전 러시아워 고수요 정류장 (06-08시)"""
    station: StationInfoSchema
    total_morning_rush: int = Field(..., description="오전 러시아워 총 승차인원 (06-08시)")
    morning_hours_traffic: List[int] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="시간대별 승차량 [06시, 07시, 08시]"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 오전 러시아워 수요 배수")

class EveningRushStationSchema(BaseModel):
    """오후 러시아워 고수요 정류장 (17-19시)"""
    station: StationInfoSchema
    total_evening_rush: int = Field(..., description="오후 러시아워 총 승차인원 (17-19시)")
    evening_hours_traffic: List[int] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="시간대별 승차량 [17시, 18시, 19시]"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 오후 러시아워 수요 배수")

# 통합 러시아워 응답
class RushHourStationSchema(BaseModel):
    """러시아워 종합 분석 응답"""
    morning_rush: List[MorningRushStationSchema] = Field(..., description="오전 러시아워 TOP N")
    evening_rush: List[EveningRushStationSchema] = Field(..., description="오후 러시아워 TOP N")
    
    class Config:
        schema_extra = {
            "example": {
                "morning_rush": [
                    {
                        "station": {
                            "station_id": "113000422",
                            "station_name": "홍대입구역",
                            "latitude": 37.556641,
                            "longitude": 126.923466,
                            "district_name": "마포구",
                            "administrative_dong": "서교동"
                        },
                        "total_morning_rush": 13284,
                        "morning_hours_traffic": [4128, 4856, 4300],
                        "vs_district_avg": 8.2
                    }
                ],
                "evening_rush": [
                    {
                        "station": {
                            "station_id": "113000422", 
                            "station_name": "홍대입구역",
                            "latitude": 37.556641,
                            "longitude": 126.923466,
                            "district_name": "마포구",
                            "administrative_dong": "서교동"
                        },
                        "total_evening_rush": 38615,
                        "evening_hours_traffic": [12800, 13215, 12600],
                        "vs_district_avg": 15.3
                    }
                ]
            }
        }


# 4. 점심시간 특화 정류장 (하차 중심)
class LunchTimeStationSchema(BaseModel):
    """점심시간 특화 정류장 (11-13시 하차 중심)"""
    station: StationInfoSchema
    total_lunch_alight: int = Field(..., description="점심시간 총 하차인원 (11-13시)")
    lunch_hours_alight: List[int] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="시간대별 하차량 [11시, 12시, 13시]"
    )
    vs_district_avg: float = Field(..., description="구 평균 대비 점심시간 하차인원 배수")
    
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
                "lunch_hours_alight": [420, 480, 428],
                "vs_district_avg": 8.4
            }
        }


# 5. 주거지역 정류장 (출퇴근 승하차 불균형 기준)
class ResidentialAreaStationSchema(BaseModel):
    """주거지역 정류장 (출근시 승차>>하차, 퇴근시 하차>>승차)
    
    비즈니스 로직:
    - 1000명 이상 교통량 필터링
    - 불균형 비율: (출근승차/출근하차) × (퇴근하차/퇴근승차)
    - 출퇴근 시간대: 6-9시, 17-19시
    """
    station: StationInfoSchema
    morning_ride: int = Field(..., description="출근시간대 승차인원 (6-9시)")
    morning_alight: int = Field(..., description="출근시간대 하차인원 (6-9시)")
    evening_ride: int = Field(..., description="퇴근시간대 승차인원 (17-19시)")
    evening_alight: int = Field(..., description="퇴근시간대 하차인원 (17-19시)")
    total_traffic: int = Field(..., description="총 교통량 (1000명 이상)")
    imbalance_ratio: float = Field(..., description="불균형 비율 ((출근승차/출근하차) × (퇴근하차/퇴근승차))")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113001234",
                    "station_name": "한강타운.우성아파트16동앞",
                    "latitude": 37.556641,
                    "longitude": 126.923466,
                    "district_name": "마포구",
                    "administrative_dong": "도화동"
                },
                "morning_ride": 530,
                "morning_alight": 16,
                "evening_ride": 145,
                "evening_alight": 629,
                "total_traffic": 1320,
                "imbalance_ratio": 143.69
            }
        }


# 6. 업무지역 정류장 (출퇴근 승하차 불균형 기준)
class BusinessAreaStationSchema(BaseModel):
    """업무지역 정류장 (출근시 하차>>승차, 퇴근시 승차>>하차)
    
    비즈니스 로직:
    - 1000명 이상 교통량 필터링
    - 불균형 비율: (출근하차/출근승차) × (퇴근승차/퇴근하차)
    - 출퇴근 시간대: 6-9시, 17-19시
    """
    station: StationInfoSchema
    morning_ride: int = Field(..., description="출근시간대 승차인원 (6-9시)")
    morning_alight: int = Field(..., description="출근시간대 하차인원 (6-9시)")
    evening_ride: int = Field(..., description="퇴근시간대 승차인원 (17-19시)")
    evening_alight: int = Field(..., description="퇴근시간대 하차인원 (17-19시)")
    total_traffic: int = Field(..., description="총 교통량 (1000명 이상)")
    imbalance_ratio: float = Field(..., description="불균형 비율 ((출근하차/출근승차) × (퇴근승차/퇴근하차))")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113005678",
                    "station_name": "서울역사박물관",
                    "latitude": 37.571234,
                    "longitude": 126.968567,
                    "district_name": "종로구",
                    "administrative_dong": "사직동"
                },
                "morning_ride": 29,
                "morning_alight": 2746,
                "evening_ride": 1720,
                "evening_alight": 356,
                "total_traffic": 4851,
                "imbalance_ratio": 457.49
            }
        }


# 통합 지역 특성 분석 응답
class AreaTypeAnalysisSchema(BaseModel):
    """지역 특성별 정류장 분석 통합 응답"""
    residential_stations: List[ResidentialAreaStationSchema] = Field(
        ..., description="주거지역 정류장 TOP N (불균형 비율 순)"
    )
    business_stations: List[BusinessAreaStationSchema] = Field(
        ..., description="업무지역 정류장 TOP N (불균형 비율 순)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "residential_stations": [
                    {
                        "station": {
                            "station_id": "113001234",
                            "station_name": "한강타운.우성아파트16동앞",
                            "latitude": 37.556641,
                            "longitude": 126.923466,
                            "district_name": "마포구",
                            "administrative_dong": "도화동"
                        },
                        "morning_ride": 530,
                        "morning_alight": 16,
                        "evening_ride": 145,
                        "evening_alight": 629,
                        "total_traffic": 1320,
                        "imbalance_ratio": 143.69
                    }
                ],
                "business_stations": [
                    {
                        "station": {
                            "station_id": "113005678",
                            "station_name": "서울역사박물관",
                            "latitude": 37.571234,
                            "longitude": 126.968567,
                            "district_name": "종로구",
                            "administrative_dong": "사직동"
                        },
                        "morning_ride": 29,
                        "morning_alight": 2746,
                        "evening_ride": 1720,
                        "evening_alight": 356,
                        "total_traffic": 4851,
                        "imbalance_ratio": 457.49
                    }
                ]
            }
        }









# 6. 저활용 정류장 (운영 최적화 대상)
class UnderutilizedStationSchema(BaseModel):
    """저활용 정류장 (운영 최적화 및 효율성 개선 대상)
    
    비즈니스 로직:
    - 구별 하위 25% 교통량 기준
    - 연결 노선수와 교통량 효율성 분석
    - 운영비용 대비 효과 측정
    """
    station: StationInfoSchema
    avg_daily_passengers: int = Field(..., description="일평균 승하차 인원")
    max_daily_passengers: int = Field(..., description="최대 일일 승하차 인원")
    connecting_routes: int = Field(..., description="연결된 버스 노선 수")
    utilization_rate: float = Field(..., description="구 평균 대비 활용률 (%)")
    efficiency_score: float = Field(..., description="효율성 점수 (승객수/노선수)")
    
    class Config:
        schema_extra = {
            "example": {
                "station": {
                    "station_id": "113002345",
                    "station_name": "한적한마을입구",
                    "latitude": 37.556641,
                    "longitude": 126.923466,
                    "district_name": "마포구",
                    "administrative_dong": "상암동"
                },
                "avg_daily_passengers": 3,
                "max_daily_passengers": 15,
                "connecting_routes": 1,
                "utilization_rate": 35.3,
                "efficiency_score": 3.0
            }
        }




# ==========================================
# 3. 통합 분석 응답 스키마
# ==========================================

class IntegratedAnomalyPatternResponse(BaseModel):
    """교통 특이패턴 통합 분석 API 응답 (6개 패턴)"""
    
    # 기본 메타 정보
    district_name: str = Field(..., description="분석 대상 구명")
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)")
    generated_at: str = Field(..., description="분석 생성 시간 (ISO 8601)")
    
    # 6가지 특이패턴별 결과
    weekend_dominant_stations: List[WeekendDominantStationSchema] = Field(
        ..., description="주말 우세 정류장 TOP N"
    )
    
    night_demand_stations: List[NightDemandStationSchema] = Field(
        ..., description="심야시간 고수요 정류장 TOP N"
    )
    
    rush_hour_stations: RushHourStationSchema = Field(
        ..., description="러시아워 고수요 정류장 (오전/오후 분리)"
    )
    
    lunch_time_stations: List[LunchTimeStationSchema] = Field(
        ..., description="점심시간 특화 정류장 TOP N"
    )
    
    area_type_analysis: AreaTypeAnalysisSchema = Field(
        ..., description="지역 특성별 정류장 분석 (주거/업무지역)"
    )
    
    underutilized_stations: List[UnderutilizedStationSchema] = Field(
        ..., description="저활용 정류장 TOP N"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "district_name": "강남구",
                "analysis_month": "2025-07",
                "generated_at": "2025-08-31T04:50:00Z",
                "weekend_dominant_stations": [],
                "night_demand_stations": [],
                "rush_hour_stations": {"morning_rush": [], "evening_rush": []},
                "lunch_time_stations": [],
                "area_type_analysis": {"residential_stations": [], "business_stations": []},
                "underutilized_stations": []
            }
        }


# ==========================================
# 4. 레거시 메인 응답 스키마 (호환성 유지)
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
    
    area_type_analysis: AreaTypeAnalysisSchema = Field(
        ..., 
        description="지역 특성별 정류장 분석 (주거지역/업무지역)"
    )
    
    underutilized_stations: List[UnderutilizedStationSchema] = Field(
        ...,
        max_items=10,
        description="저활용 정류장 TOP N (운영 최적화 대상)"
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
                "area_type_analysis": {
                    "residential_stations": [],
                    "business_stations": []
                },
                "underutilized_stations": []
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