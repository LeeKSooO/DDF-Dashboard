"""
서울시 교통량 히트맵 컴포넌트 스키마
지도 구성을 위한 경계 좌표와 정류장별/구별 교통량 집계 데이터
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CoordinateSchema(BaseModel):
    """좌표 스키마 (위도, 경도)"""
    
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")

    class Config:
        schema_extra = {
            "example": {
                "lat": 37.5665,
                "lng": 126.9780
            }
        }


class BoundarySchema(BaseModel):
    """경계 좌표 스키마 (폴리곤)"""
    
    coordinates: List[List[CoordinateSchema]] = Field(
        ..., 
        description="경계 좌표 배열 (첫 번째 배열은 외곽선, 나머지는 구멍)"
    )

    class Config:
        schema_extra = {
            "example": {
                "coordinates": [[
                    {"lat": 37.5665, "lng": 126.9780},
                    {"lat": 37.5665, "lng": 126.9880},
                    {"lat": 37.5765, "lng": 126.9880},
                    {"lat": 37.5765, "lng": 126.9780},
                    {"lat": 37.5665, "lng": 126.9780}
                ]]
            }
        }


class StationTrafficSchema(BaseModel):
    """정류장별 교통량 스키마"""
    
    station_id: str = Field(..., description="정류장 ID")
    station_name: str = Field(..., description="정류장명")
    coordinate: CoordinateSchema = Field(..., description="정류장 좌표")
    total_traffic: int = Field(..., ge=0, description="월간 총 교통량 (승차+하차)")
    total_ride: int = Field(..., ge=0, description="월간 총 승차 인원")
    total_alight: int = Field(..., ge=0, description="월간 총 하차 인원")
    daily_average: float = Field(..., ge=0, description="일평균 교통량")

    class Config:
        schema_extra = {
            "example": {
                "station_id": "100000001",
                "station_name": "강남역",
                "coordinate": {"lat": 37.4979, "lng": 127.0276},
                "total_traffic": 15420,
                "total_ride": 7850,
                "total_alight": 7570,
                "daily_average": 497.1
            }
        }


class DistrictTrafficSchema(BaseModel):
    """구별 교통량 집계 스키마"""
    
    district_code: str = Field(..., description="구 코드")
    district_name: str = Field(..., description="구명")
    boundary: BoundarySchema = Field(..., description="구 경계 좌표")
    
    # 교통량 집계 데이터
    total_traffic: int = Field(..., ge=0, description="구 전체 월간 총 교통량")
    total_ride: int = Field(..., ge=0, description="구 전체 월간 총 승차 인원")
    total_alight: int = Field(..., ge=0, description="구 전체 월간 총 하차 인원")
    daily_average: float = Field(..., ge=0, description="구 전체 일평균 교통량")
    station_count: int = Field(..., ge=0, description="구 내 정류장 수")
    
    # 정류장별 상세 데이터
    stations: List[StationTrafficSchema] = Field(
        ..., 
        description="구 내 정류장별 교통량 데이터"
    )
    
    # 순위 정보
    traffic_rank: int = Field(..., ge=1, description="서울시 내 교통량 순위")
    traffic_density: float = Field(..., ge=0, description="교통량 밀도 (총교통량/정류장수)")

    class Config:
        schema_extra = {
            "example": {
                "district_code": "11680",
                "district_name": "강남구",
                "boundary": {
                    "coordinates": [[
                        {"lat": 37.4979, "lng": 127.0276},
                        {"lat": 37.4979, "lng": 127.0376}
                    ]]
                },
                "total_traffic": 485200,
                "total_ride": 245800,
                "total_alight": 239400,
                "daily_average": 15651.6,
                "station_count": 89,
                "stations": [],
                "traffic_rank": 1,
                "traffic_density": 5451.7
            }
        }


class HeatmapStatisticsSchema(BaseModel):
    """히트맵 통계 스키마"""
    
    max_district_traffic: int = Field(..., description="최대 구별 교통량")
    min_district_traffic: int = Field(..., description="최소 구별 교통량") 
    max_station_traffic: int = Field(..., description="최대 정류장 교통량")
    min_station_traffic: int = Field(..., description="최소 정류장 교통량")
    total_seoul_traffic: int = Field(..., description="서울시 전체 교통량")
    total_stations: int = Field(..., description="전체 정류장 수")
    
    # 히트맵 색상 범위를 위한 구간 정보
    district_traffic_quartiles: List[int] = Field(
        ..., 
        description="구별 교통량 사분위수 [Q1, Q2, Q3]",
        min_items=3,
        max_items=3
    )
    station_traffic_quartiles: List[int] = Field(
        ..., 
        description="정류장별 교통량 사분위수 [Q1, Q2, Q3]", 
        min_items=3,
        max_items=3
    )

    class Config:
        schema_extra = {
            "example": {
                "max_district_traffic": 485200,
                "min_district_traffic": 12500,
                "max_station_traffic": 15420,
                "min_station_traffic": 45,
                "total_seoul_traffic": 5850000,
                "total_stations": 1245,
                "district_traffic_quartiles": [125000, 235000, 385000],
                "station_traffic_quartiles": [1200, 3500, 7800]
            }
        }


class SeoulHeatmapSchema(BaseModel):
    """서울시 교통량 히트맵 컴포넌트 응답 스키마"""
    
    # 기본 정보
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)", pattern=r"^\d{4}-\d{2}$")
    seoul_boundary: BoundarySchema = Field(..., description="서울시 경계 좌표")
    
    # 구별 계층적 데이터 
    districts: List[DistrictTrafficSchema] = Field(
        ..., 
        description="구별 교통량 및 정류장 데이터",
        min_items=1
    )
    
    # 통계 및 메타데이터
    statistics: HeatmapStatisticsSchema = Field(..., description="히트맵 렌더링을 위한 통계")
    
    # 추가 메타데이터
    data_period: str = Field(..., description="데이터 수집 기간")
    last_updated: str = Field(..., description="최종 업데이트 시간")

    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "seoul_boundary": {
                    "coordinates": [[
                        {"lat": 37.7134, "lng": 126.7342},
                        {"lat": 37.7134, "lng": 127.2698}
                    ]]
                },
                "districts": [],
                "statistics": {
                    "max_district_traffic": 485200,
                    "min_district_traffic": 12500,
                    "max_station_traffic": 15420,
                    "min_station_traffic": 45,
                    "total_seoul_traffic": 5850000,
                    "total_stations": 1245,
                    "district_traffic_quartiles": [125000, 235000, 385000],
                    "station_traffic_quartiles": [1200, 3500, 7800]
                },
                "data_period": "2025-07-16 ~ 2025-07-31",
                "last_updated": "2025-08-27T12:30:00Z"
            }
        }


# 요청 스키마
class HeatmapRequest(BaseModel):
    """히트맵 요청 스키마"""
    
    analysis_month: str = Field(..., description="분석 월 (YYYY-MM)", pattern=r"^\d{4}-\d{2}$")
    include_station_details: bool = Field(
        True, 
        description="정류장별 상세 데이터 포함 여부 (false시 구별 집계만 반환)"
    )
    min_traffic_threshold: Optional[int] = Field(
        None, 
        ge=0, 
        description="최소 교통량 임계값 (이하 정류장 제외)"
    )

    class Config:
        schema_extra = {
            "example": {
                "analysis_month": "2025-07",
                "include_station_details": True,
                "min_traffic_threshold": 100
            }
        }