# data_preparation/mstgcn_data_loader.py
# MST-GCN용 데이터 로더 (새 스키마 정합성)

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
import logging
import os
import gc
from typing import Dict, List, Tuple, Optional
from sklearn.metrics.pairwise import haversine_distances
import pickle
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    # fallback for environments without dateutil
    def relativedelta(months=0):
        class FakeRelativeDelta:
            def __init__(self, months):
                self.months = months
        return FakeRelativeDelta(months)

logger = logging.getLogger(__name__)

class MSTGCN_DataLoader:
    """MST-GCN 모델을 위한 4개 피처 데이터 로더"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        
    def connect_db(self):
        """DB 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def close_db(self):
        """DB 연결 종료"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def load_mstgcn_features(self, start_date: Optional[str] = None, 
                            end_date: Optional[str] = None) -> Tuple[np.ndarray, List[str], pd.DatetimeIndex]:
        """
        MST-GCN 4개 피처 데이터 로딩
        
        Returns:
            feature_matrix: (4, N, T) shape의 피처 행렬
            stop_ids: 정류장 ID 리스트
            time_index: 시간 인덱스
        """
        logger.info("Loading MST-GCN features from database...")
        
        # 날짜 필터 조건
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND recorded_at >= '{start_date}' AND recorded_at <= '{end_date}'"
        
        # 4개 입력 피처 + DRT 확률 (타겟) 조회 (Log+Z-score 정규화 적용)
        query = f"""
        SELECT 
            stop_id,
            recorded_at,
            normalized_log_boarding_count,
            service_availability,
            is_rest_day::int as is_rest_day_int,
            normalized_interval,  -- Log+Z-score 정규화된 배차간격
            drt_probability
        FROM drt_features_mstgcn 
        WHERE 1=1 {date_filter}
        ORDER BY recorded_at, stop_id;
        """
        
        self.cur.execute(query)
        results = self.cur.fetchall()
        
        if not results:
            raise ValueError("No MST-GCN features found in database")
        
        # DataFrame으로 변환
        df = pd.DataFrame(results, columns=[
            'stop_id', 'recorded_at', 'normalized_log_boarding_count', 
            'service_availability', 'is_rest_day_int', 'normalized_interval', 'drt_probability'
        ])
        
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        
        logger.info(f"Loaded {len(df)} feature records")
        
        # 피벗 테이블 생성 (각 피처별)
        pivot_features = {}
        feature_names = ['normalized_log_boarding_count', 'service_availability', 
                        'is_rest_day_int', 'normalized_interval']
        
        for feature in feature_names:
            pivot_features[feature] = df.pivot_table(
                index='stop_id', 
                columns='recorded_at', 
                values=feature, 
                fill_value=0
            )
        
        # DRT 확률 (타겟)
        pivot_features['drt_probability'] = df.pivot_table(
            index='stop_id', 
            columns='recorded_at', 
            values='drt_probability', 
            fill_value=0
        )
        
        # 모든 피처가 같은 shape인지 확인
        shapes = [pivot_features[f].shape for f in feature_names + ['drt_probability']]
        if not all(s == shapes[0] for s in shapes):
            raise ValueError("Feature matrices have inconsistent shapes")
        
        # Feature matrix 구성: (5, N, T) - 4개 입력 피처 + 1개 타겟
        feature_matrix = np.stack([
            pivot_features['normalized_log_boarding_count'].values,
            pivot_features['service_availability'].values, 
            pivot_features['is_rest_day_int'].values,
            pivot_features['normalized_interval'].values,
            pivot_features['drt_probability'].values  # 타겟
        ])
        
        stop_ids = pivot_features['normalized_log_boarding_count'].index.tolist()
        time_index = pivot_features['normalized_log_boarding_count'].columns
        
        logger.info(f"Feature matrix shape: {feature_matrix.shape}")
        logger.info(f"Number of stops: {len(stop_ids)}")
        logger.info(f"Time range: {time_index.min()} to {time_index.max()}")
        
        return feature_matrix, stop_ids, time_index
    
    def load_adjacency_matrix(self, stop_ids: List[str], threshold_km: float = 1.0) -> np.ndarray:
        """
        정류장 인접 행렬 생성
        
        Args:
            stop_ids: 정류장 ID 리스트
            threshold_km: 인접성 판정 거리 임계값 (km)
            
        Returns:
            adj_matrix: (N, N) 인접 행렬
        """
        logger.info(f"Building adjacency matrix for {len(stop_ids)} stops...")
        
        # 정류장 좌표 조회
        stop_ids_str = "','".join(stop_ids)
        query = f"""
        SELECT stop_id, latitude, longitude
        FROM bus_stops 
        WHERE stop_id IN ('{stop_ids_str}')
        AND latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY ARRAY_POSITION(ARRAY['{stop_ids_str}']::text[], stop_id);
        """
        
        self.cur.execute(query)
        coords_data = self.cur.fetchall()
        
        if len(coords_data) != len(stop_ids):
            logger.warning(f"Coordinate mismatch: {len(coords_data)} vs {len(stop_ids)}")
        
        # 좌표 배열 생성
        coords = []
        for stop_id, lat, lon in coords_data:
            coords.append([np.radians(float(lat)), np.radians(float(lon))])
        
        coords = np.array(coords)
        
        # Haversine 거리 계산
        distances = haversine_distances(coords) * 6371  # km 단위
        
        # 임계값 기반 인접 행렬 생성
        adj_matrix = (distances <= threshold_km).astype(float)
        np.fill_diagonal(adj_matrix, 0)  # 자기 자신 제거
        
        edge_count = np.sum(adj_matrix) / 2
        avg_degree = np.sum(adj_matrix, axis=1).mean()
        
        logger.info(f"Adjacency matrix: {adj_matrix.shape}, edges: {edge_count}, avg degree: {avg_degree:.2f}")
        
        return adj_matrix
    
    def create_multi_scale_sequences(self, feature_matrix: np.ndarray, 
                                   hour_len: int = 6, day_len: int = 24, week_len: int = 24,
                                   output_len: int = 24, week_offset: int = 168) -> Tuple[np.ndarray, ...]:
        """
        MST-GCN용 다중 스케일 시퀀스 생성
        
        Args:
            feature_matrix: (5, N, T) 피처 행렬 (4개 입력 + 1개 타겟)
            hour_len: 시간 스케일 길이
            day_len: 일 스케일 길이
            week_len: 주 스케일 길이
            output_len: 예측 길이
            week_offset: 주간 오프셋
            
        Returns:
            X_hour, X_day, X_week, y: 다중 스케일 입력 시퀀스와 타겟
        """
        logger.info("Creating multi-scale sequences...")
        
        # 입력 피처만 사용 (처음 4개)
        input_features = feature_matrix[:4, :, :]  # (4, N, T)
        target_feature = feature_matrix[4, :, :]   # (N, T) - DRT 확률
        
        X_hour, X_day, X_week, y = [], [], [], []
        
        for i in range(week_offset, input_features.shape[2] - output_len + 1):
            # Recent pattern (최근 6시간)
            hour_slice = input_features[:, :, i-hour_len:i]
            X_hour.append(hour_slice)
            
            # Daily pattern (과거 24시간)
            day_slice = input_features[:, :, i-day_len:i]
            X_day.append(day_slice)
            
            # Weekly pattern (1주일 전 24시간)
            week_slice = input_features[:, :, i-week_offset:i-week_offset+week_len]
            X_week.append(week_slice)
            
            # Target (다음 24시간 DRT 확률)
            y_slice = target_feature[:, i:i+output_len]
            y.append(y_slice)
        
        # Numpy 배열로 변환
        X_hour = np.array(X_hour)  # (samples, features, nodes, time)
        X_day = np.array(X_day)
        X_week = np.array(X_week)
        y = np.array(y)  # (samples, nodes, time)
        
        # MST-GCN 입력 형태로 변환: (samples, nodes, features, time)
        X_hour = X_hour.transpose(0, 2, 1, 3)
        X_day = X_day.transpose(0, 2, 1, 3)
        X_week = X_week.transpose(0, 2, 1, 3)
        
        logger.info(f"Multi-scale sequences created:")
        logger.info(f"  X_hour: {X_hour.shape}")
        logger.info(f"  X_day: {X_day.shape}")
        logger.info(f"  X_week: {X_week.shape}")
        logger.info(f"  y: {y.shape}")
        
        return X_hour, X_day, X_week, y
    
    def save_mstgcn_data(self, save_path: str, feature_matrix: np.ndarray, 
                        stop_ids: List[str], adj_matrix: np.ndarray,
                        X_hour: np.ndarray, X_day: np.ndarray, X_week: np.ndarray, y: np.ndarray):
        """MST-GCN 학습 데이터 저장"""
        logger.info(f"Saving MST-GCN data to {save_path}")
        
        np.savez_compressed(
            save_path,
            feature_matrix=feature_matrix,
            stop_ids=np.array(stop_ids),
            adj_matrix=adj_matrix,
            X_hour=X_hour,
            X_day=X_day,
            X_week=X_week,
            y=y
        )
        
        logger.info("MST-GCN data saved successfully")

def main():
    """월별로 MST-GCN 데이터셋을 생성하고 저장하는 메인 함수"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ddf_db',
        'user': 'ddf_user',
        'password': 'ddf_password'
    }
    
    loader = MSTGCN_DataLoader(db_config)
    
    start_date = datetime(2024, 11, 1)
    end_date = datetime(2025, 6, 25)
    current_date = start_date
    
    try:
        loader.connect_db()
        
        while current_date <= end_date:
            # 월의 시작일과 마지막일 계산
            month_start = current_date.replace(day=1)
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)
            
            # 데이터 기간 설정 (전체 기간을 넘지 않도록)
            period_start = max(month_start, start_date)
            period_end = min(month_end, end_date)
            
            logger.info(f"===== Processing data for {period_start.strftime('%Y-%m')} =====")
            
            try:
                # 데이터 로딩
                feature_matrix, stop_ids, time_index = loader.load_mstgcn_features(
                    start_date=period_start.strftime('%Y-%m-%d'), 
                    end_date=period_end.strftime('%Y-%m-%d')
                )
                
                if feature_matrix.size == 0:
                    logger.warning(f"No data found for {period_start.strftime('%Y-%m')}. Skipping.")
                    current_date += relativedelta(months=1)
                    continue

                adj_matrix = loader.load_adjacency_matrix(stop_ids)
                
                # 다중 스케일 시퀀스 생성
                X_hour, X_day, X_week, y = loader.create_multi_scale_sequences(feature_matrix)
                
                # 데이터 저장
                save_dir = "/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/monthly"
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"mstgcn_data_{period_start.strftime('%Y_%m')}.npz")
                
                loader.save_mstgcn_data(save_path, feature_matrix, stop_ids, adj_matrix, X_hour, X_day, X_week, y)
                
                print(f"✅ MST-GCN 데이터 저장 완료: {save_path}")

            except ValueError as ve:
                logger.error(f"Skipping {period_start.strftime('%Y-%m')} due to ValueError: {ve}")
            except Exception as e:
                logger.error(f"An unexpected error occurred for {period_start.strftime('%Y-%m')}: {e}")

            # 다음 달로 이동
            current_date = month_start + relativedelta(months=1)
            gc.collect() # 메모리 관리

    except Exception as e:
        logger.error(f"Main process failed: {e}")
    finally:
        loader.close_db()

if __name__ == "__main__":
    main()