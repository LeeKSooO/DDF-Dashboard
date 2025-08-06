from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from loguru import logger
import json
import os
from pathlib import Path

from app.db.session import get_db
from app.db.models import ModelMetadata
from app.core.config import settings
from sqlalchemy import select, desc

router = APIRouter()

@router.get("/")
async def list_models(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """List all available models"""
    try:
        query = select(ModelMetadata).order_by(desc(ModelMetadata.created_at))
        
        if active_only:
            query = query.where(ModelMetadata.is_active == True)
        
        result = await db.execute(query)
        models = result.scalars().all()
        
        return [{
            "model_id": model.model_id,
            "model_name": model.model_name,
            "model_version": model.model_version,
            "model_type": model.model_type,
            "is_active": model.is_active,
            "is_validated": model.is_validated,
            "deployment_status": model.deployment_status,
            "metrics": model.metrics,
            "created_at": model.created_at,
            "description": model.description
        } for model in models]
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model_id}")
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get specific model details"""
    try:
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return {
            "model_id": model.model_id,
            "model_name": model.model_name,
            "model_version": model.model_version,
            "model_type": model.model_type,
            "training_start": model.training_start,
            "training_end": model.training_end,
            "training_data_start": model.training_data_start,
            "training_data_end": model.training_data_end,
            "metrics": model.metrics,
            "hyperparameters": model.hyperparameters,
            "model_architecture": model.model_architecture,
            "normalization_stats": model.normalization_stats,
            "is_active": model.is_active,
            "is_validated": model.is_validated,
            "deployment_status": model.deployment_status,
            "description": model.description,
            "created_by": model.created_by,
            "created_at": model.created_at,
            "updated_at": model.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{model_id}/activate")
async def activate_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Activate a model (deactivates others)"""
    try:
        # Check if model exists
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.model_id == model_id)
        )
        target_model = result.scalar_one_or_none()
        
        if not target_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        if not target_model.is_validated:
            raise HTTPException(status_code=400, detail="Model must be validated before activation")
        
        # Deactivate all other models
        all_models_result = await db.execute(select(ModelMetadata))
        all_models = all_models_result.scalars().all()
        
        for model in all_models:
            model.is_active = (model.model_id == model_id)
            model.deployment_status = "active" if model.model_id == model_id else "inactive"
        
        await db.commit()
        
        logger.info(f"Model {model_id} ({target_model.model_name} v{target_model.model_version}) activated")
        
        return {"message": f"Model {model_id} activated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating model {model_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{model_id}/validate")
async def validate_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Validate a model"""
    try:
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Check if model files exist
        if not os.path.exists(model.model_path):
            raise HTTPException(status_code=400, detail="Model file not found")
        
        # Perform basic validation
        # TODO: Add more comprehensive validation logic
        model.is_validated = True
        model.deployment_status = "validated"
        
        await db.commit()
        
        logger.info(f"Model {model_id} validated successfully")
        
        return {"message": f"Model {model_id} validated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating model {model_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a model"""
    try:
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        if model.is_active:
            raise HTTPException(status_code=400, detail="Cannot delete active model")
        
        # Remove model files
        if os.path.exists(model.model_path):
            os.remove(model.model_path)
        
        if model.stats_path and os.path.exists(model.stats_path):
            os.remove(model.stats_path)
        
        if model.graph_path and os.path.exists(model.graph_path):
            os.remove(model.graph_path)
        
        # Delete from database
        await db.delete(model)
        await db.commit()
        
        logger.info(f"Model {model_id} deleted successfully")
        
        return {"message": f"Model {model_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting model {model_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model_id}/metrics")
async def get_model_metrics(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get model performance metrics"""
    try:
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return {
            "model_id": model.model_id,
            "model_version": model.model_version,
            "metrics": model.metrics,
            "training_period": {
                "start": model.training_data_start,
                "end": model.training_data_end
            },
            "hyperparameters": model.hyperparameters,
            "normalization_stats": model.normalization_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))