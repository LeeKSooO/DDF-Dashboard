from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from loguru import logger

from app.db.session import get_db
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse
)

router = APIRouter()
prediction_service = PredictionService()

@router.post("/predict", response_model=PredictionResponse)
async def create_prediction(
    request: PredictionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create predictions for all stops at specified datetime
    
    - **target_datetime**: Target datetime for prediction (YYYY-MM-DD HH:MM:SS)
    
    Returns predictions for all 957 stops in the model
    """
    try:
        # Validate target datetime
        # if request.target_datetime <= datetime.now():
        #     raise HTTPException(
        #         status_code=400,
        #         detail="Target datetime must be in the future"
        #     )
        
        # 전체 정류장 예측이므로 stop count 검증 제거
        
        # Create prediction
        result = await prediction_service.predict(db, request)
        return result
        
    except ValueError as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/predict/batch", response_model=BatchPredictionResponse)
async def create_batch_prediction(
    request: BatchPredictionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create predictions for multiple time points
    """
    try:
        predictions = []
        
        for target_time in request.target_times:
            pred_request = PredictionRequest(
                target_datetime=target_time,
                stop_ids=request.stop_ids
            )
            result = await prediction_service.predict(db, pred_request)
            predictions.append(result)
        
        return BatchPredictionResponse(predictions=predictions)
        
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predict/latest")
async def get_latest_predictions(
    stop_id: Optional[str] = Query(None, description="Filter by stop ID"),
    limit: int = Query(10, le=100, description="Number of predictions to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get latest predictions
    """
    try:
        from sqlalchemy import select, desc
        from app.db.models import Prediction, BusStop
        
        query = select(
            Prediction,
            BusStop.stop_name
        ).join(
            BusStop,
            Prediction.stop_id == BusStop.stop_id
        ).order_by(
            desc(Prediction.created_at)
        )
        
        if stop_id:
            query = query.where(Prediction.stop_id == stop_id)
        
        query = query.limit(limit)
        
        result = await db.execute(query)
        predictions = []
        
        for pred, stop_name in result:
            predictions.append({
                "prediction_id": pred.prediction_id,
                "stop_id": pred.stop_id,
                "stop_name": stop_name,
                "target_time": pred.target_time,
                "drt_probability": float(pred.drt_probability),
                "predicted_boarding_count": float(pred.predicted_boarding_count),
                "model_version": pred.model_version,
                "created_at": pred.created_at
            })
        
        return predictions
        
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predict/history/{stop_id}")
async def get_prediction_history(
    stop_id: str,
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get prediction history for a specific stop
    """
    try:
        from sqlalchemy import select, and_
        from app.db.models import Prediction
        
        query = select(Prediction).where(
            and_(
                Prediction.stop_id == stop_id,
                Prediction.target_time >= start_date,
                Prediction.target_time <= end_date
            )
        ).order_by(Prediction.target_time)
        
        result = await db.execute(query)
        predictions = result.scalars().all()
        
        return [{
            "target_time": pred.target_time,
            "drt_probability": float(pred.drt_probability),
            "predicted_boarding_count": float(pred.predicted_boarding_count),
            "model_version": pred.model_version
        } for pred in predictions]
        
    except Exception as e:
        logger.error(f"Error fetching prediction history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/torchserve")
async def check_torchserve_health():
    """
    Check TorchServe health status
    """
    try:
        is_healthy = await prediction_service.health_check()
        return {
            "torchserve_available": is_healthy,
            "status": "healthy" if is_healthy else "unhealthy"
        }
    except Exception as e:
        logger.error(f"Error checking TorchServe health: {e}")
        return {
            "torchserve_available": False,
            "status": "unhealthy",
            "error": str(e)
        }