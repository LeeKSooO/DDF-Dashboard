#!/usr/bin/env python3
# data_preparation/mstgcn_data_builder.py
# MST-GCN 모델을 위한 시공간 그래프 데이터 구축

import pandas as pd
import numpy as np
import psycopg2
import os
import logging
from datetime import datetime, timedelta
import networkx as nx
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import haversine_distances
import pickle

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ASTGCNDataBuilder:
    def __init__(self, db_config):
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
    
    def get_active_stops_mapping(self):
        """활성 정류장 매핑 정보 구축"""
        logger.info("Building active stops mapping...")
        
        # DRT features에서 실제 사용된 정류장만 추출
        query = """
        SELECT DISTINCT df.stop_id, bs.stop_name, bs.latitude, bs.longitude
        FROM drt_features df
        JOIN bus_stops bs ON df.stop_id = bs.stop_id
        WHERE bs.latitude IS NOT NULL AND bs.longitude IS NOT NULL
        ORDER BY df.stop_id
        """
        
        self.cur.execute(query)
        results = self.cur.fetchall()
        
        stops_info = {}
        stop_id_to_index = {}
        
        for idx, (stop_id, stop_name, lat, lon) in enumerate(results):
            stops_info[stop_id] = {
                'index': idx,
                'name': stop_name,
                'lat': float(lat),
                'lon': float(lon)
            }
            stop_id_to_index[stop_id] = idx
            
        logger.info(f"Found {len(stops_info)} active stops")
        return stops_info, stop_id_to_index
    
    def build_adjacency_matrix(self, stops_info, method='distance', threshold=5.0):
        """인접 행렬 구축"""
        logger.info(f"Building adjacency matrix using {method} method...")
        
        num_stops = len(stops_info)
        adj_matrix = np.zeros((num_stops, num_stops))
        
        # 좌표 배열 생성
        coords = []
        stop_ids = list(stops_info.keys())
        
        for stop_id in stop_ids:
            lat = stops_info[stop_id]['lat']
            lon = stops_info[stop_id]['lon']
            coords.append([np.radians(lat), np.radians(lon)])
        
        coords = np.array(coords)
        
        if method == 'distance':
            # Haversine 거리 기반 인접성
            distances = haversine_distances(coords) * 6371  # km 단위
            
            # threshold km 이내의 정류장들을 연결
            adj_matrix = (distances <= threshold).astype(float)
            
            # 대각선 제거 (자기 자신과의 연결 제거)
            np.fill_diagonal(adj_matrix, 0)
            
        elif method == 'route_based':
            # 노선 기반 인접성 (같은 노선을 공유하는 정류장들)
            route_query = """
            SELECT rs1.stop_id as stop1, rs2.stop_id as stop2, rs1.route_id
            FROM route_stops rs1
            JOIN route_stops rs2 ON rs1.route_id = rs2.route_id
            WHERE rs1.stop_id != rs2.stop_id
            AND ABS(rs1.stop_sequence - rs2.stop_sequence) <= 2
            """
            
            self.cur.execute(route_query)
            route_connections = self.cur.fetchall()
            
            for stop1, stop2, route_id in route_connections:
                if stop1 in stops_info and stop2 in stops_info:
                    idx1 = stops_info[stop1]['index']
                    idx2 = stops_info[stop2]['index']
                    adj_matrix[idx1, idx2] = 1
                    adj_matrix[idx2, idx1] = 1
        
        # 연결성 확인
        connected_components = self._get_connected_components(adj_matrix)
        logger.info(f"Adjacency matrix built: {num_stops}x{num_stops}, "
                   f"Connected components: {connected_components}")
        
        return adj_matrix
    
    def _get_connected_components(self, adj_matrix):
        """그래프의 연결 성분 수 계산"""
        G = nx.from_numpy_array(adj_matrix)
        return nx.number_connected_components(G)
    
    def extract_temporal_data(self, start_date='2024-11-01', end_date='2025-06-25', 
                             feature_type='drt_prob_normalized'):
        """시간별 데이터 추출"""
        logger.info(f"Extracting temporal data from {start_date} to {end_date}...")
        
        query = f"""
        SELECT 
            df.stop_id,
            df.recorded_at,
            df.hour_of_day,
            df.day_of_week,
            df.is_weekend,
            df.boarding_count,
            df.alighting_count,
            df.{feature_type} as feature_value,
            df.is_operational
        FROM drt_features df
        WHERE df.recorded_at >= %s AND df.recorded_at <= %s
        ORDER BY df.recorded_at, df.stop_id
        """
        
        self.cur.execute(query, (start_date, end_date))
        results = self.cur.fetchall()
        
        # DataFrame으로 변환
        df = pd.DataFrame(results, columns=[
            'stop_id', 'recorded_at', 'hour_of_day', 'day_of_week',
            'is_weekend', 'boarding_count', 'alighting_count', 
            'feature_value', 'is_operational'
        ])
        
        logger.info(f"Extracted {len(df)} records")
        return df
    
    def create_graph_signal_matrix(self, df, stops_info, stop_id_to_index):
        """그래프 신호 행렬 생성 (N x F x T)"""
        logger.info("Creating graph signal matrix...")
        
        # 시간 인덱스 생성
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        time_range = pd.date_range(
            start=df['recorded_at'].min(),
            end=df['recorded_at'].max(),
            freq='H'
        )
        
        num_nodes = len(stops_info)
        num_features = 1  # DRT probability만 사용
        num_timesteps = len(time_range)
        
        # 초기화
        graph_signal_matrix = np.zeros((num_nodes, num_features, num_timesteps))
        
        # 데이터 채우기
        for _, row in df.iterrows():
            stop_id = row['stop_id']
            if stop_id in stop_id_to_index:
                node_idx = stop_id_to_index[stop_id]
                time_idx = (row['recorded_at'] - time_range[0]).total_seconds() // 3600
                time_idx = int(time_idx)
                
                if 0 <= time_idx < num_timesteps:
                    graph_signal_matrix[node_idx, 0, time_idx] = row['feature_value']
        
        logger.info(f"Graph signal matrix shape: {graph_signal_matrix.shape}")
        return graph_signal_matrix, time_range
    
    def save_for_mstgcn(self, graph_signal_matrix, adj_matrix, stops_info, time_range, 
                       output_dir='data/processed'):
        """MST-GCN 형식으로 데이터 저장"""
        logger.info("Saving data for MST-GCN...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Graph signal matrix 저장 (npz 형식)
        data_file = os.path.join(output_dir, 'gapyeong_drt_data.npz')
        np.savez_compressed(
            data_file,
            data=graph_signal_matrix.transpose(2, 0, 1),  # (T, N, F) 형식으로 변환
            adj_matrix=adj_matrix
        )
        
        # 2. 메타데이터 저장
        metadata = {
            'num_nodes': len(stops_info),
            'num_features': graph_signal_matrix.shape[1],
            'num_timesteps': graph_signal_matrix.shape[2],
            'time_range': {
                'start': str(time_range[0]),
                'end': str(time_range[-1]),
                'freq': 'H'
            },
            'stops_info': stops_info,
            'feature_description': 'DRT demand probability (normalized)'
        }
        
        metadata_file = os.path.join(output_dir, 'metadata.pkl')
        with open(metadata_file, 'wb') as f:
            pickle.dump(metadata, f)
        
        # 3. CSV 형식으로도 저장 (분석용)
        csv_file = os.path.join(output_dir, 'gapyeong_drt_timeseries.csv')
        self._save_as_csv(graph_signal_matrix, stops_info, time_range, csv_file)
        
        logger.info(f"Data saved to {output_dir}")
        logger.info(f"- NPZ file: {data_file}")
        logger.info(f"- Metadata: {metadata_file}")
        logger.info(f"- CSV file: {csv_file}")
        
        return data_file, metadata_file, csv_file
    
    def _save_as_csv(self, graph_signal_matrix, stops_info, time_range, csv_file):
        """시계열 데이터를 CSV로 저장"""
        data_list = []
        
        stop_ids = list(stops_info.keys())
        
        for t_idx, timestamp in enumerate(time_range):
            for stop_id in stop_ids:
                node_idx = stops_info[stop_id]['index']
                drt_prob = graph_signal_matrix[node_idx, 0, t_idx]
                
                data_list.append({
                    'timestamp': timestamp,
                    'stop_id': stop_id,
                    'stop_name': stops_info[stop_id]['name'],
                    'latitude': stops_info[stop_id]['lat'],
                    'longitude': stops_info[stop_id]['lon'],
                    'drt_probability': drt_prob,
                    'hour_of_day': timestamp.hour,
                    'day_of_week': timestamp.weekday(),
                    'is_weekend': timestamp.weekday() >= 5
                })
        
        df = pd.DataFrame(data_list)
        df.to_csv(csv_file, index=False)
        logger.info(f"CSV saved with {len(df)} records")
    
    def build_complete_dataset(self, start_date='2024-11-01', end_date='2025-06-25',
                              adjacency_method='distance', distance_threshold=5.0,
                              output_dir='data/processed'):
        """완전한 MST-GCN 데이터셋 구축"""
        logger.info("Building complete MST-GCN dataset...")
        
        try:
            self.connect_db()
            
            # 1. 활성 정류장 매핑
            stops_info, stop_id_to_index = self.get_active_stops_mapping()
            
            # 2. 인접 행렬 구축
            adj_matrix = self.build_adjacency_matrix(
                stops_info, 
                method=adjacency_method, 
                threshold=distance_threshold
            )
            
            # 3. 시간별 데이터 추출
            temporal_df = self.extract_temporal_data(start_date, end_date)
            
            # 4. 그래프 신호 행렬 생성
            graph_signal_matrix, time_range = self.create_graph_signal_matrix(
                temporal_df, stops_info, stop_id_to_index
            )
            
            # 5. MST-GCN 형식으로 저장
            data_file, metadata_file, csv_file = self.save_for_mstgcn(
                graph_signal_matrix, adj_matrix, stops_info, time_range, output_dir
            )
            
            # 6. 데이터 통계 출력
            self._print_dataset_stats(graph_signal_matrix, adj_matrix, stops_info, time_range)
            
            return {
                'data_file': data_file,
                'metadata_file': metadata_file,
                'csv_file': csv_file,
                'num_nodes': len(stops_info),
                'num_timesteps': len(time_range),
                'adjacency_density': np.sum(adj_matrix) / (adj_matrix.shape[0] * adj_matrix.shape[1])
            }
            
        finally:
            self.close_db()
    
    def _print_dataset_stats(self, graph_signal_matrix, adj_matrix, stops_info, time_range):
        """데이터셋 통계 출력"""
        logger.info("Dataset Statistics:")
        logger.info(f"- Number of nodes (stops): {len(stops_info)}")
        logger.info(f"- Number of timesteps: {len(time_range)}")
        logger.info(f"- Time range: {time_range[0]} to {time_range[-1]}")
        logger.info(f"- Graph signal matrix shape: {graph_signal_matrix.shape}")
        logger.info(f"- Adjacency matrix shape: {adj_matrix.shape}")
        logger.info(f"- Adjacency matrix density: {np.sum(adj_matrix) / (adj_matrix.shape[0] * adj_matrix.shape[1]):.4f}")
        logger.info(f"- DRT probability range: [{np.min(graph_signal_matrix):.4f}, {np.max(graph_signal_matrix):.4f}]")
        logger.info(f"- Non-zero values: {np.count_nonzero(graph_signal_matrix)} / {graph_signal_matrix.size}")


def main():
    """메인 실행 함수"""
    # 데이터베이스 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 데이터 빌더 생성
    builder = ASTGCNDataBuilder(db_config)
    
    # 완전한 데이터셋 구축
    result = builder.build_complete_dataset(
        start_date='2024-11-01',
        end_date='2025-06-25',
        adjacency_method='distance',  # 'distance' or 'route_based'
        distance_threshold=5.0,  # km
        output_dir='data/processed'
    )
    
    logger.info("Dataset building completed!")
    logger.info(f"Results: {result}")


if __name__ == "__main__":
    main()