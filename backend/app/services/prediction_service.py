import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger
import time
import json
from uuid import UUID, uuid4

from app.db.models import BusStop, Prediction, PredictionRequest, ModelMetadata
from app.core.config import settings
from app.schemas.prediction import PredictionRequest as PredictionRequestSchema
from app.schemas.prediction import PredictionResponse, StopPrediction

class PredictionService:
    def __init__(self):
        self.torchserve_url = settings.TORCHSERVE_URL
        self.model_name = settings.TORCHSERVE_MODEL_NAME
        
        # [중요] 학습에 사용된 957개 정류장 ID 로드
        try:
            # 텍스트 파일에서 로드 (더 안전한 방법)
            with open(settings.MODEL_BASE_PATH + '/valid_stop_ids.txt', 'r') as f:
                self.valid_stop_ids = np.array([line.strip() for line in f.readlines()])
        except Exception as e:
            logger.error(f'Error loading valid_stop_ids.txt: {e}')
            # 비상 상황에서 임시로 사용할 수 있는 샘플 ID들
            self.valid_stop_ids = np.array([f'GGB239000{i:03d}' for i in range(1, 958)])
            logger.warning('Using fallback stop IDs due to loading error')
            
        self.valid_stop_ids_set = set(self.valid_stop_ids)  # 빠른 검색을 위한 집합
        
        logger.info(f"PredictionService initialized with TorchServe URL: {self.torchserve_url}")
        logger.info(f"Loaded {len(self.valid_stop_ids)} valid stop IDs for model inference")
    
    async def health_check(self) -> bool:
        """Check if TorchServe is available"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.torchserve_url}/ping")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"TorchServe health check failed: {e}")
            return False
    
    async def predict(
        self,
        db: AsyncSession,
        request: PredictionRequestSchema
    ) -> PredictionResponse:
        """
        Main prediction method
        """
        start_time = time.time()
        request_id = uuid4()
        
        try:
            # 1. Get active model info
            active_model = await self._get_active_model(db)
            if not active_model:
                raise ValueError("No active model found")
        
            # 2. Prepare input data (전체 정류장 예측)
            preprocessing_start = time.time()
            input_data, stop_ids = await self._prepare_input_data(
                db, 
                request.target_datetime,
                None  # 전체 정류장 예측
            )
            preprocessing_time = int((time.time() - preprocessing_start) * 1000)
            
            # 3. Check TorchServe availability
            if not await self.health_check():
                raise ValueError("TorchServe is not available")
            
            # 4. Call TorchServe for inference
            inference_start = time.time()
            predictions = await self._call_torchserve(input_data)
            inference_time = int((time.time() - inference_start) * 1000)
            
            # 4. Post-process predictions
            stop_predictions = await self._post_process_predictions(
                predictions,
                stop_ids,
                request.target_datetime,
                active_model,
                request_id
            )
            
            # 5. Save predictions to database
            await self._save_predictions(
                db,
                stop_predictions,
                active_model,
                request_id,
                request.target_datetime
            )
            
            # 6. Log request metrics
            total_time = int((time.time() - start_time) * 1000)
            await self._log_request_metrics(
                db,
                request_id,
                request.target_datetime,
                len(stop_ids),
                active_model.model_id,
                preprocessing_time,
                inference_time,
                total_time
            )
            
            return PredictionResponse(
                request_id=str(request_id),
                target_datetime=request.target_datetime,
                predictions=stop_predictions,
                model_version=active_model.model_version,
                processing_time_ms=total_time
            )
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

        

    async def _get_active_model(self, db: AsyncSession) -> Optional[ModelMetadata]:
        """Get currently active model"""
        result = await db.execute(
            select(ModelMetadata).where(ModelMetadata.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def _prepare_input_data(
        self,
        db: AsyncSession,
        target_datetime: datetime,
        stop_ids: Optional[List[str]] = None
    ) -> Tuple[Dict[str, np.ndarray], List[str]]:
        """
        Prepare MST-GCN input data with 3 components:
        1. Recent 6 hours data (Hour)
        2. Recent 24 hours data (Day) 
        3. Same 24 hours from 1 week ago (Week)
        
        Returns: (input_data_dict, stop_ids)
        """
        # Calculate time ranges for three components
        # Round target_datetime to hour boundary
        target_hour = target_datetime.replace(minute=0, second=0, microsecond=0)
        
        # 1. Recent 6 hours: 6 hours before target time
        hour_start = target_hour - timedelta(hours=6)
        
        # 2. Recent 24 hours: 24 hours before target time  
        day_start = target_hour - timedelta(hours=24)
        
        # 3. Same 24 hours from 1 week ago
        week_start = target_hour - timedelta(days=7, hours=24)
        week_end = target_hour - timedelta(days=7)
        
        # [중요] 학습에 사용된 957개 정류장만 사용
        # 1. 사용자가 지정한 정류장이 있으면 그 중에서 유효한 것만 필터링
        if stop_ids:
            # 사용자 지정 정류장 중 모델이 아는 것만 필터링
            target_stops = [stop_id for stop_id in stop_ids if stop_id in self.valid_stop_ids_set]
            if len(target_stops) != len(stop_ids):
                invalid_stops = [stop_id for stop_id in stop_ids if stop_id not in self.valid_stop_ids_set]
                logger.warning(f"Invalid stop IDs filtered out: {invalid_stops}")
        else:
            # 사용자가 지정하지 않으면 모델이 아는 모든 정류장
            target_stops = self.valid_stop_ids.tolist()
            
        logger.info(f"Target stops for inference: {len(target_stops)} stops")
        
        # Use raw SQL for drt_features_mstgcn table
        from sqlalchemy import text
        feature_table = None
        
        # Prepare three datasets
        datasets = {}
        time_ranges = {
            'hour': (hour_start, target_hour, 6),
            'day': (day_start, target_hour, 24),
            'week': (week_start, week_end, 24)
        }
        
        for component, (start_time, end_time, expected_hours) in time_ranges.items():
            # Using raw SQL for drt_features_mstgcn table
            query_sql = """
                SELECT stop_id, recorded_at, normalized_log_boarding_count, 
                       service_availability, is_rest_day, normalized_interval
                FROM drt_features_mstgcn 
                WHERE recorded_at >= :start_time AND recorded_at < :end_time
            """
            
            # Add stop_id filter if specified
            if stop_ids:
                placeholders = ', '.join([f':stop_id_{i}' for i in range(len(stop_ids))])
                query_sql += f" AND stop_id IN ({placeholders})"
            
            query_sql += " ORDER BY stop_id, recorded_at"
            
            query = text(query_sql)
            
            # Prepare parameters
            params = {
                'start_time': start_time,
                'end_time': end_time
            }
            
            # Add stop_id parameters
            if stop_ids:
                for i, stop_id in enumerate(stop_ids):
                    params[f'stop_id_{i}'] = stop_id
            
            result = await db.execute(query, params)
            
            df = pd.DataFrame(result.fetchall(), columns=[
                'stop_id', 'recorded_at', 'normalized_log_boarding_count',
                'service_availability', 'is_rest_day', 'normalized_interval'
            ])
            
            if df.empty:
                logger.warning(f"No data found for {component} time range: {start_time} to {end_time}")
                # Create empty data with zeros
                df = pd.DataFrame({
                    'stop_id': target_stops * expected_hours,
                    'recorded_at': [start_time + timedelta(hours=i) for i in range(expected_hours)] * len(target_stops),
                    'normalized_log_boarding_count': [0.0] * (len(target_stops) * expected_hours),
                    'service_availability': [0] * (len(target_stops) * expected_hours),
                    'is_rest_day': [False] * (len(target_stops) * expected_hours),
                    'normalized_interval': [0.0] * (len(target_stops) * expected_hours)
                })
            
            # Pivot data to create 4-feature matrices
            feature_names = ['normalized_log_boarding_count', 'service_availability', 'is_rest_day', 'normalized_interval']
            df_pivot_features = {}
            
            for feature in feature_names:
                df_pivot_features[feature] = df.pivot_table(
                    index='stop_id',
                    columns='recorded_at',
                    values=feature
                ).fillna(0)
            
            # [중요] 학습에 사용된 957개 정류장의 정확한 순서로 데이터 정렬
            # 1. 모델이 아는 모든 정류장에 대한 데이터 준비
            final_features = {}
            for feature in feature_names:
                # valid_stop_ids 순서로 데이터 정렬
                feature_data = []
                for stop_id in self.valid_stop_ids:
                    if stop_id in df_pivot_features[feature].index:
                        feature_data.append(df_pivot_features[feature].loc[stop_id].values)
                    else:
                        # 데이터가 없는 정류장은 0으로 채움
                        feature_data.append(np.zeros(expected_hours))
                
                final_features[feature] = np.array(feature_data)
            
            # 2. MST-GCN은 그래프 컨볼루션이므로 항상 전체 957개 정류장 데이터 필요
            # 사용자 지정 정류장 필터링은 후처리에서 수행
            
            # 3. Stack 4 input features: (F, N, T)
            feature_matrix = np.stack([
                final_features['normalized_log_boarding_count'],
                final_features['service_availability'],
                final_features['is_rest_day'].astype(float),
                final_features['normalized_interval']
            ])
            
            # Transpose to (N, F, T) and add batch dimension: (1, N, F, T)
            feature_matrix = feature_matrix.transpose(1, 0, 2)
            datasets[component] = np.expand_dims(feature_matrix, axis=0).astype(np.float32)
        
        return datasets, target_stops
    
    def _get_valid_stop_ids(self) -> List[str]:
        """Get valid stop IDs in model training order"""
        return self.valid_stop_ids.tolist()
    
    async def _call_torchserve(self, input_data: Dict[str, np.ndarray]) -> np.ndarray:
        """Call TorchServe for MST-GCN inference"""
        try:
            async with httpx.AsyncClient(timeout=settings.TORCHSERVE_TIMEOUT) as client:
                # Convert numpy arrays to lists for JSON serialization
                # Note: 핸들러에서 정규화를 수행하므로 raw 데이터를 전송
                request_data = {
                    "hour_data": input_data["hour"].tolist(),
                    "day_data": input_data["day"].tolist(),
                    "week_data": input_data["week"].tolist()
                }
                
                # Make prediction request to TorchServe
                response = await client.post(
                    f"{self.torchserve_url}/predictions/{self.model_name}",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    logger.error(f"TorchServe request failed: {response.status_code}, {response.text}")
                    raise ValueError(f"TorchServe error: HTTP {response.status_code}")
                
                # Parse response - TorchServe returns predictions directly
                predictions_data = response.json()
                
                # Convert back to numpy array
                if isinstance(predictions_data, list):
                    predictions = np.array(predictions_data)
                else:
                    # Handle different response formats
                    predictions = np.array(predictions_data.get("predictions", predictions_data))
                
                logger.info(f"TorchServe MST-GCN inference successful, output shape: {predictions.shape}")
                return predictions
                
        except httpx.TimeoutException:
            logger.error("TorchServe request timed out")
            raise ValueError("TorchServe request timeout")
        except Exception as e:
            logger.error(f"TorchServe inference failed: {e}")
            raise
    
    async def _post_process_predictions(
        self,
        predictions: np.ndarray,
        stop_ids: List[str],
        target_datetime: datetime,
        model: ModelMetadata,
        request_id: UUID
    ) -> List[StopPrediction]:
        """Post-process model predictions"""
        # TorchServe 출력 shape: [1, 24, 957] (1배치, 24시간, 957정류장)
        # Extract predictions for next 24 hours
        predictions_24h = predictions[0]  # Shape: [24, 957]
        
        # 사용자가 요청한 정류장만 필터링
        stop_predictions = []
        for stop_id in stop_ids:
            # valid_stop_ids에서 해당 정류장의 인덱스 찾기
            if stop_id in self.valid_stop_ids_set:
                stop_index = np.where(self.valid_stop_ids == stop_id)[0][0]
                # Get 24-hour predictions for this stop
                stop_24h_predictions = predictions_24h[:, stop_index]  # Shape: [24]
                
                # Calculate DRT probability for next hour (first prediction)
                next_hour_pred = float(stop_24h_predictions[0])
                drt_prob = float(1 / (1 + np.exp(-next_hour_pred)))
            
                # Predicted boarding count for next hour
                boarding_count = max(0, float(next_hour_pred))
                
                # Calculate confidence interval based on prediction variance
                pred_variance = float(np.var(stop_24h_predictions))
                confidence_std = np.sqrt(pred_variance) if pred_variance > 0 else 0.1
                
                stop_predictions.append(StopPrediction(
                    stop_id=stop_id,
                    drt_probability=drt_prob,
                    predicted_boarding_count=boarding_count,
                    prediction_horizon=1,  # Next hour
                    confidence_interval={
                        "lower": float(max(0, boarding_count - 1.96 * confidence_std)),
                        "upper": float(boarding_count + 1.96 * confidence_std)
                    }
                ))
        
        return stop_predictions
    
    async def _save_predictions(
        self,
        db: AsyncSession,
        predictions: List[StopPrediction],
        model: ModelMetadata,
        request_id: UUID,
        target_datetime: datetime
    ):
        """Save predictions to database"""
        prediction_time = datetime.utcnow()
        
        for pred in predictions:
            db_prediction = Prediction(
                request_id=request_id,
                stop_id=pred.stop_id,
                prediction_time=prediction_time,
                target_time=target_datetime,
                prediction_horizon=pred.prediction_horizon,
                drt_probability=pred.drt_probability,
                predicted_boarding_count=pred.predicted_boarding_count,
                model_id=model.model_id,
                model_version=model.model_version,
                confidence_interval=pred.confidence_interval
            )
            db.add(db_prediction)
        
        await db.commit()
    
    async def _log_request_metrics(
        self,
        db: AsyncSession,
        request_id: UUID,
        target_datetime: datetime,
        requested_stops: int,
        model_id: int,
        preprocessing_time_ms: int,
        inference_time_ms: int,
        total_time_ms: int
    ):
        """Log request metrics for monitoring"""
        request_log = PredictionRequest(
            request_id=request_id,
            target_datetime=target_datetime,
            requested_stops=requested_stops,
            model_id=model_id,
            preprocessing_time_ms=preprocessing_time_ms,
            inference_time_ms=inference_time_ms,
            total_time_ms=total_time_ms,
            request_source="api"
        )
        db.add(request_log)
        await db.commit()