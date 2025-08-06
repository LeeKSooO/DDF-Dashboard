from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional, Dict
from uuid import UUID

class PredictionRequest(BaseModel):
    target_datetime: datetime = Field(..., description="Target datetime for prediction")
    
    @validator('target_datetime')
    def validate_datetime_range(cls, v):
        # 🚨 [수정] 테스트 데이터 기간에 맞춰 예측 가능 기간 설정
        # 데이터 범위: 2024-11-08 ~ 2025-06-24
        min_date = datetime(2024, 11, 8)
        max_date = datetime(2025, 6, 24, 23, 59, 59)
        
        if v < min_date or v > max_date:
            raise ValueError(f'Target datetime must be between {min_date.strftime("%Y-%m-%d")} and {max_date.strftime("%Y-%m-%d")}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "target_datetime": "2024-12-01T14:00:00"
            }
        }

class BatchPredictionRequest(BaseModel):
    target_times: List[datetime] = Field(..., description="List of target times")
    stop_ids: Optional[List[str]] = Field(None, description="List of stop IDs")
    
    @validator('target_times')
    def validate_target_times(cls, v):
        if len(v) > 24:
            raise ValueError('Maximum 24 time points per batch request')
        return v

class StopPrediction(BaseModel):
    stop_id: str
    stop_name: Optional[str] = None
    target_datetime: Optional[datetime] = None
    drt_probability: float = Field(..., ge=0, le=1)
    predicted_boarding_count: float = Field(..., ge=0)
    predicted_alighting_count: Optional[float] = Field(None, ge=0)
    prediction_horizon: int = Field(..., ge=1, le=3)
    confidence_interval: Optional[Dict[str, float]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "stop_id": "GGB239000001",
                "stop_name": "가평터미널",
                "drt_probability": 0.75,
                "predicted_boarding_count": 12.5,
                "prediction_horizon": 1,
                "confidence_interval": {
                    "lower": 10.0,
                    "upper": 15.0
                }
            }
        }

class PredictionResponse(BaseModel):
    request_id: str
    target_datetime: datetime
    predictions: List[StopPrediction]
    model_version: str
    processing_time_ms: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_datetime": "2024-12-01T14:00:00",
                "predictions": [
                    {
                        "stop_id": "GGB239000001",
                        "drt_probability": 0.75,
                        "predicted_boarding_count": 12.5,
                        "prediction_horizon": 1
                    }
                ],
                "model_version": "ddf_v1",
                "processing_time_ms": 250
            }
        }

class BatchPredictionResponse(BaseModel):
    predictions: List[PredictionResponse]

class PredictionHistoryItem(BaseModel):
    target_time: datetime
    drt_probability: float
    predicted_boarding_count: float
    actual_boarding_count: Optional[float] = None
    model_version: str