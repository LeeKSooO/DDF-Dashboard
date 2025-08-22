"""
서울시 교통 API 응답 스키마 정의
외부 API 데이터 구조 및 응답 모델
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime


class PassengerDataItem(BaseModel):
    """정류장별 승하차 데이터 항목"""
    stdrDe: str = Field(..., description="기준일자 (YYYYMMDD)")
    routeId: str = Field(..., description="노선ID")
    routeNm: str = Field(..., description="노선명")
    rtType: str = Field(..., description="노선타입")
    staId: str = Field(..., description="정류장ID")
    staNm: str = Field(..., description="정류장명")
    staTy: str = Field(..., description="정류장타입")
    staArs: str = Field(..., description="정류장번호")
    a05: Optional[str] = Field(None, description="총 배차수")
    ridePnsgerCnt: Optional[str] = Field(None, description="총 승차인원")
    alghPnsgerCnt: Optional[str] = Field(None, description="총 하차인원")
    staSn: Optional[str] = Field(None, description="정류장순번")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stdrDe": "20250801",
                "routeId": "229000023",
                "routeNm": "9710파주",
                "rtType": "8",
                "staId": "229000520",
                "staNm": "장곡삼거리",
                "staTy": "2",
                "staArs": "30523",
                "a05": "43",
                "ridePnsgerCnt": "125",
                "alghPnsgerCnt": "98"
            }
        }


class PassengerDataResponse(BaseModel):
    """정류장별 승하차 데이터 응답"""
    status: str = Field(..., description="응답 상태")
    data: List[PassengerDataItem] = Field(..., description="승하차 데이터 목록")
    count: int = Field(..., description="데이터 건수")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class ODDataItem(BaseModel):
    """행정동별 OD 데이터 항목"""
    stdrDe: str = Field(..., description="기준일자")
    emdCd: str = Field(..., description="행정동코드")
    emdNm: str = Field(..., description="행정동명")
    destinationEmdCd: Optional[str] = Field(None, description="목적지 행정동코드")
    destinationEmdNm: Optional[str] = Field(None, description="목적지 행정동명")
    tripCnt: Optional[int] = Field(None, description="통행량")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stdrDe": "20250801",
                "emdCd": "1111051",
                "emdNm": "청운효자동",
                "destinationEmdCd": "1111052",
                "destinationEmdNm": "사직동",
                "tripCnt": 142
            }
        }


class ODDataResponse(BaseModel):
    """행정동별 OD 데이터 응답"""
    status: str = Field(..., description="응답 상태")
    data: List[ODDataItem] = Field(..., description="OD 데이터 목록")
    count: int = Field(..., description="데이터 건수")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class TrafficInfoItem(BaseModel):
    """구간별 소통정보 항목"""
    stndDt: str = Field(..., description="기준날짜")
    linkId: str = Field(..., description="링크ID")
    linkNm: Optional[str] = Field(None, description="링크명")
    speed: Optional[float] = Field(None, description="평균속도")
    congestionLevel: Optional[str] = Field(None, description="혼잡도")
    travelTime: Optional[float] = Field(None, description="통행시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stndDt": "20250801",
                "linkId": "1010001001",
                "linkNm": "세종대로",
                "speed": 45.2,
                "congestionLevel": "보통",
                "travelTime": 3.5
            }
        }


class TrafficInfoResponse(BaseModel):
    """구간별 소통정보 응답"""
    status: str = Field(..., description="응답 상태")
    data: List[TrafficInfoItem] = Field(..., description="소통정보 데이터 목록")
    count: int = Field(..., description="데이터 건수")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class PopulationDataResponse(BaseModel):
    """실시간 인구 데이터 응답"""
    status: str = Field(..., description="응답 상태")
    data: Union[Dict[str, Any], str] = Field(..., description="인구 데이터 (JSON 또는 XML)")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class VehicleStatsItem(BaseModel):
    """차량운행통계 항목"""
    stdrDe: str = Field(..., description="기준일자")
    vehId: str = Field(..., description="차량ID")
    routeId: str = Field(..., description="노선ID")
    totalDistance: Optional[float] = Field(None, description="총 운행거리")
    totalRuntime: Optional[float] = Field(None, description="총 운행시간")
    fuelConsumption: Optional[float] = Field(None, description="연료소모량")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stdrDe": "20250801",
                "vehId": "VEH001",
                "routeId": "100100001",
                "totalDistance": 245.8,
                "totalRuntime": 8.5,
                "fuelConsumption": 42.3
            }
        }


class VehicleStatsResponse(BaseModel):
    """차량운행통계 응답"""
    status: str = Field(..., description="응답 상태")
    data: List[VehicleStatsItem] = Field(..., description="차량통계 데이터 목록")
    count: int = Field(..., description="데이터 건수")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class BusRouteDataItem(BaseModel):
    """노선-정류장 마스터 항목"""
    routeId: str = Field(..., description="노선ID")
    routeNm: str = Field(..., description="노선명")
    staId: str = Field(..., description="정류장ID")
    staNm: str = Field(..., description="정류장명")
    staSeq: Optional[int] = Field(None, description="정류장 순번")
    
    class Config:
        json_schema_extra = {
            "example": {
                "routeId": "100100001",
                "routeNm": "9710",
                "staId": "229000520",
                "staNm": "장곡삼거리",
                "staSeq": 1
            }
        }


class BusRouteDataResponse(BaseModel):
    """노선-정류장 마스터 응답"""
    status: str = Field(..., description="응답 상태")
    data: List[BusRouteDataItem] = Field(..., description="노선-정류장 데이터 목록")
    count: int = Field(..., description="데이터 건수")
    api_info: Dict[str, Any] = Field(..., description="API 정보")


class APIStatusItem(BaseModel):
    """API 상태 항목"""
    name: str = Field(..., description="API 명")
    status: str = Field(..., description="상태 (available/discontinued)")


class AllAPIsStatusResponse(BaseModel):
    """전체 API 상태 응답"""
    total_apis: int = Field(..., description="전체 API 수")
    available_apis: int = Field(..., description="사용 가능한 API 수")
    discontinued_apis: int = Field(..., description="중단된 API 수")
    success_rate: str = Field(..., description="성공률")
    api_details: Dict[str, APIStatusItem] = Field(..., description="API별 상세 상태")
    last_checked: str = Field(..., description="마지막 확인 시간")


class IntegratedTrafficDataResponse(BaseModel):
    """통합 교통 데이터 응답"""
    date: str = Field(..., description="조회 날짜")
    passenger_data: Optional[List[PassengerDataItem]] = Field(None, description="승객 데이터")
    od_data: Optional[List[ODDataItem]] = Field(None, description="OD 데이터")
    traffic_data: Optional[List[TrafficInfoItem]] = Field(None, description="교통정보 데이터")
    vehicle_data: Optional[List[VehicleStatsItem]] = Field(None, description="차량통계 데이터")
    integration_summary: Dict[str, Any] = Field(..., description="통합 결과 요약")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "20250801",
                "integration_summary": {
                    "successful_apis": 3,
                    "total_apis": 4,
                    "timestamp": "2025-08-18T10:30:00"
                }
            }
        }