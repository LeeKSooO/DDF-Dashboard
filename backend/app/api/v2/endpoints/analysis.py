# app/api/v2/endpoints/analysis.py 
# 버스 정류장 이용 현황, 예측 정확도, 시스템 성능 등 다양한 분석 데이터를 제공하는 API 앤드포인트 정의
# DB에 저장된 데이터를 기반으로 통계 및 분석 정보를 조회하는 읽기 전용(read-only) API 역할

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger

from app.db.session import get_db
from app.db.models import (
    StopUsage, BusStop, Prediction, 
    PredictionRequest, ModelMetadata, DRTFeature
)

router = APIRouter()

@router.get("/usage/summary")
async def get_usage_summary(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    stop_id: Optional[str] = Query(None, description="Filter by stop ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get usage summary statistics"""
    try:
        # Base query
        query = select(
            func.count(StopUsage.stop_id).label("total_records"),
            func.sum(StopUsage.boarding_count).label("total_boarding"),
            func.sum(StopUsage.alighting_count).label("total_alighting"),
            func.avg(StopUsage.boarding_count).label("avg_boarding"),
            func.avg(StopUsage.alighting_count).label("avg_alighting")
        ).where(
            and_(
                StopUsage.recorded_at >= start_date,
                StopUsage.recorded_at <= end_date,
                StopUsage.is_operational == True
            )
        )
        
        if stop_id:
            query = query.where(StopUsage.stop_id == stop_id)
        
        result = await db.execute(query)
        summary = result.first()
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "stop_id": stop_id,
            "summary": {
                "total_records": summary.total_records or 0,
                "total_boarding": int(summary.total_boarding or 0),
                "total_alighting": int(summary.total_alighting or 0),
                "avg_boarding": float(summary.avg_boarding or 0),
                "avg_alighting": float(summary.avg_alighting or 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage/hourly")
async def get_hourly_usage(
    date: datetime = Query(..., description="Target date"),
    stop_id: Optional[str] = Query(None, description="Filter by stop ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get hourly usage patterns for a specific date"""
    try:
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        query = select(
            func.extract('hour', StopUsage.recorded_at).label("hour"),
            func.sum(StopUsage.boarding_count).label("total_boarding"),
            func.sum(StopUsage.alighting_count).label("total_alighting"),
            func.count(StopUsage.stop_id).label("stop_count")
        ).where(
            and_(
                StopUsage.recorded_at >= start_of_day,
                StopUsage.recorded_at < end_of_day,
                StopUsage.is_operational == True
            )
        ).group_by(
            func.extract('hour', StopUsage.recorded_at)
        ).order_by(
            func.extract('hour', StopUsage.recorded_at)
        )
        
        if stop_id:
            query = query.where(StopUsage.stop_id == stop_id)
        
        result = await db.execute(query)
        hourly_data = []
        
        for row in result:
            hourly_data.append({
                "hour": int(row.hour),
                "total_boarding": int(row.total_boarding or 0),
                "total_alighting": int(row.total_alighting or 0),
                "stop_count": int(row.stop_count or 0),
                "avg_boarding_per_stop": float((row.total_boarding or 0) / (row.stop_count or 1))
            })
        
        return {
            "date": start_of_day.date(),
            "stop_id": stop_id,
            "hourly_usage": hourly_data
        }
        
    except Exception as e:
        logger.error(f"Error getting hourly usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage/top-stops")
async def get_top_stops(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    limit: int = Query(10, le=50, description="Number of stops to return"),
    metric: str = Query("boarding", regex="^(boarding|alighting|total)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get top stops by usage"""
    try:
        if metric == "boarding":
            metric_col = func.sum(StopUsage.boarding_count)
        elif metric == "alighting":
            metric_col = func.sum(StopUsage.alighting_count)
        else:  # total
            metric_col = func.sum(StopUsage.boarding_count + StopUsage.alighting_count)
        
        query = select(
            BusStop.stop_id,
            BusStop.stop_name,
            BusStop.stop_number,
            metric_col.label("usage_count"),
            func.count(StopUsage.recorded_at).label("record_count")
        ).join(
            StopUsage, BusStop.stop_id == StopUsage.stop_id
        ).where(
            and_(
                StopUsage.recorded_at >= start_date,
                StopUsage.recorded_at <= end_date,
                StopUsage.is_operational == True
            )
        ).group_by(
            BusStop.stop_id, BusStop.stop_name, BusStop.stop_number
        ).order_by(
            desc("usage_count")
        ).limit(limit)
        
        result = await db.execute(query)
        top_stops = []
        
        for row in result:
            top_stops.append({
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
                "stop_number": row.stop_number,
                "usage_count": int(row.usage_count or 0),
                "record_count": int(row.record_count or 0),
                "avg_per_record": float((row.usage_count or 0) / (row.record_count or 1))
            })
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "metric": metric,
            "top_stops": top_stops
        }
        
    except Exception as e:
        logger.error(f"Error getting top stops: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predictions/accuracy")
async def get_prediction_accuracy(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    model_version: Optional[str] = Query(None, description="Filter by model version"),
    db: AsyncSession = Depends(get_db)
):
    """Analyze prediction accuracy against actual data"""
    try:
        # This is a simplified version - real implementation would require
        # matching predictions with actual usage data
        query = select(
            func.count(Prediction.prediction_id).label("total_predictions"),
            func.avg(Prediction.drt_probability).label("avg_drt_probability"),
            func.avg(Prediction.predicted_boarding_count).label("avg_predicted_boarding"),
            Prediction.model_version
        ).where(
            and_(
                Prediction.target_time >= start_date,
                Prediction.target_time <= end_date
            )
        ).group_by(Prediction.model_version)
        
        if model_version:
            query = query.where(Prediction.model_version == model_version)
        
        result = await db.execute(query)
        accuracy_data = []
        
        for row in result:
            accuracy_data.append({
                "model_version": row.model_version,
                "total_predictions": int(row.total_predictions),
                "avg_drt_probability": float(row.avg_drt_probability or 0),
                "avg_predicted_boarding": float(row.avg_predicted_boarding or 0)
            })
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "model_version": model_version,
            "accuracy_analysis": accuracy_data
        }
        
    except Exception as e:
        logger.error(f"Error analyzing prediction accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/requests")
async def get_request_performance(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    db: AsyncSession = Depends(get_db)
):
    """Get request performance metrics"""
    try:
        query = select(
            func.count(PredictionRequest.request_id).label("total_requests"),
            func.avg(PredictionRequest.preprocessing_time_ms).label("avg_preprocessing_time"),
            func.avg(PredictionRequest.inference_time_ms).label("avg_inference_time"),
            func.avg(PredictionRequest.total_time_ms).label("avg_total_time"),
            func.max(PredictionRequest.total_time_ms).label("max_total_time"),
            func.min(PredictionRequest.total_time_ms).label("min_total_time"),
            func.sum(PredictionRequest.requested_stops).label("total_stops_requested")
        ).where(
            and_(
                PredictionRequest.created_at >= start_date,
                PredictionRequest.created_at <= end_date
            )
        )
        
        result = await db.execute(query)
        performance = result.first()
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "performance_metrics": {
                "total_requests": performance.total_requests or 0,
                "total_stops_requested": performance.total_stops_requested or 0,
                "avg_preprocessing_time_ms": float(performance.avg_preprocessing_time or 0),
                "avg_inference_time_ms": float(performance.avg_inference_time or 0),
                "avg_total_time_ms": float(performance.avg_total_time or 0),
                "max_total_time_ms": performance.max_total_time or 0,
                "min_total_time_ms": performance.min_total_time or 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting request performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drt/hotspots")
async def get_drt_hotspots(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    min_drt_prob: float = Query(0.5, ge=0, le=1, description="Minimum DRT probability"),
    limit: int = Query(20, le=100, description="Number of hotspots to return"),
    db: AsyncSession = Depends(get_db)
):
    """Identify DRT demand hotspots"""
    try:
        query = select(
            BusStop.stop_id,
            BusStop.stop_name,
            BusStop.stop_number,
            BusStop.latitude,
            BusStop.longitude,
            func.avg(DRTFeature.drt_prob).label("avg_drt_prob"),
            func.count(DRTFeature.feature_id).label("record_count"),
            func.sum(DRTFeature.boarding_count).label("total_boarding")
        ).join(
            DRTFeature, BusStop.stop_id == DRTFeature.stop_id
        ).where(
            and_(
                DRTFeature.recorded_at >= start_date,
                DRTFeature.recorded_at <= end_date,
                DRTFeature.drt_prob >= min_drt_prob
            )
        ).group_by(
            BusStop.stop_id, BusStop.stop_name, BusStop.stop_number,
            BusStop.latitude, BusStop.longitude
        ).order_by(
            desc("avg_drt_prob")
        ).limit(limit)
        
        result = await db.execute(query)
        hotspots = []
        
        for row in result:
            hotspots.append({
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
                "stop_number": row.stop_number,
                "latitude": float(row.latitude) if row.latitude else None,
                "longitude": float(row.longitude) if row.longitude else None,
                "avg_drt_probability": float(row.avg_drt_prob or 0),
                "record_count": int(row.record_count or 0),
                "total_boarding": int(row.total_boarding or 0)
            })
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "min_drt_probability": min_drt_prob,
            "drt_hotspots": hotspots
        }
        
    except Exception as e:
        logger.error(f"Error getting DRT hotspots: {e}")
        raise HTTPException(status_code=500, detail=str(e))