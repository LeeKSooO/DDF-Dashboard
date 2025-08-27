"""
시간대별 교통량 컴포넌트 스키마
서울시/구별 월별 시간대별 승하차 패턴 응답 모델
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class HourlyPatternSchema(BaseModel):
    """시간대별 교통량 패턴 스키마"""
    
    hour: int = Field(..., ge=0, le=23, description="시간 (0-23)")
    avg_ride_passengers: float = Field(..., ge=0, description="평균 승차 인원")
    avg_alight_passengers: float = Field(..., ge=0, description="평균 하차 인원")
    avg_total_passengers: float = Field(..., ge=0, description="평균 총 승하차 인원")

    class Config:
        schema_extra = {
            "example": {
                "hour": 8,
                "avg_ride_passengers": 125.5,
                "avg_alight_passengers": 89.3,
                "avg_total_passengers": 214.8
            }
        }


class PeakHourInfoSchema(BaseModel):
    """피크 시간 정보 스키마"""
    
    hour: int = Field(..., ge=0, le=23, description="피크 시간")
    avg_total_passengers: float = Field(..., ge=0, description="피크 시간 평균 총 승하차 인원")

    class Config:
        schema_extra = {
            "example": {
                "hour": 8,
                "avg_total_passengers": 214.8
            }
        }


class PeakHoursSchema(BaseModel):
    """피크 시간들 정보 스키마"""
    
    weekday_morning_peak: PeakHourInfoSchema = Field(..., description="평일 아침 피크 (6-10시 중)")
    weekday_evening_peak: PeakHourInfoSchema = Field(..., description="평일 저녁 피크 (17-20시 중)")
    weekend_peak: PeakHourInfoSchema = Field(..., description="주말 피크 (전체 시간 중)")

    class Config:
        schema_extra = {
            "example": {
                "weekday_morning_peak": {"hour": 8, "avg_total_passengers": 214.8},
                "weekday_evening_peak": {"hour": 18, "avg_total_passengers": 198.3},
                "weekend_peak": {"hour": 14, "avg_total_passengers": 156.7}
            }
        }


class HourlyTrafficSchema(BaseModel):
    """시간대별 교통량 컴포넌트 응답 스키마"""
    
    # 기본 정보
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)", pattern=r"^\d{4}-\d{2}$")
    region_type: Literal["seoul", "district"] = Field(..., description="지역 구분")
    region_name: str = Field(..., description="지역명")
    district_name: Optional[str] = Field(None, description="구명 (region_type='district'일 때만)")
    
    # 시간대별 패턴 (평일/주말 구분)
    weekday_patterns: List[HourlyPatternSchema] = Field(
        ..., 
        description="평일 시간대별 패턴 (0시-23시, 총 24개)",
        min_items=24,
        max_items=24
    )
    weekend_patterns: List[HourlyPatternSchema] = Field(
        ..., 
        description="주말 시간대별 패턴 (0시-23시, 총 24개)",
        min_items=24,
        max_items=24
    )
    
    # 피크 시간 정보
    peak_hours: PeakHoursSchema = Field(..., description="피크 시간 정보")
    
    # 집계 정보
    total_weekday_passengers: int = Field(..., ge=0, description="평일 총 승하차 인원 (일평균)")
    total_weekend_passengers: int = Field(..., ge=0, description="주말 총 승하차 인원 (일평균)")
    weekday_weekend_ratio: float = Field(..., ge=0, description="평일/주말 비율")

    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "region_type": "district",
                "region_name": "강남구",
                "district_name": "강남구",
                "weekday_patterns": [
                    {"hour": 0, "avg_ride_passengers": 12.5, "avg_alight_passengers": 8.3, "avg_total_passengers": 20.8},
                    {"hour": 1, "avg_ride_passengers": 5.2, "avg_alight_passengers": 3.1, "avg_total_passengers": 8.3}
                ],
                "weekend_patterns": [
                    {"hour": 0, "avg_ride_passengers": 8.1, "avg_alight_passengers": 6.4, "avg_total_passengers": 14.5}
                ],
                "peak_hours": {
                    "weekday_morning_peak": {"hour": 8, "avg_total_passengers": 214.8},
                    "weekday_evening_peak": {"hour": 18, "avg_total_passengers": 198.3},
                    "weekend_peak": {"hour": 14, "avg_total_passengers": 156.7}
                },
                "total_weekday_passengers": 1250,
                "total_weekend_passengers": 890,
                "weekday_weekend_ratio": 1.40
            }
        }


# 요청 스키마
class HourlyTrafficRequest(BaseModel):
    """시간대별 교통량 요청 스키마"""
    
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)", pattern=r"^\d{4}-\d{2}$")
    region_type: Literal["seoul", "district"] = Field(..., description="지역 구분")
    district_name: Optional[str] = Field(None, description="구명 (region_type='district'일 때 필수)")

    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "region_type": "district", 
                "district_name": "강남구"
            }
        }