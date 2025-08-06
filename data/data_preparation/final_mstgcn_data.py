#!/usr/bin/env python3
# data_preparation/final_mstgcn_data.py
# 최종 MST-GCN 데이터 생성

import pandas as pd
import numpy as np
import os
import json

def create_simple_mstgcn_data():
    """간단한 MST-GCN 데이터 생성"""
    
    # 큰 데이터셋 로드
    csv_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_drt_full.csv'
    print("Loading full dataset...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records")
    
    # 정류장 정보 추출
    stops_df = df[['stop_id', 'stop_name', 'latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"Found {len(stops_df)} unique stops")
    
    # 정류장 ID to 인덱스 매핑
    stop_to_idx = {stop_id: idx for idx, stop_id in enumerate(stops_df['stop_id'])}
    
    # 시간 범위 생성
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    time_range = pd.date_range(
        start=df['recorded_at'].min(),
        end=df['recorded_at'].max(),
        freq='h'  # 'H' 대신 'h' 사용
    )
    print(f"Time range: {time_range[0]} to {time_range[-1]} ({len(time_range)} steps)")
    
    # 그래프 신호 행렬 초기화 (T, N, F)
    num_timesteps = len(time_range)
    num_nodes = len(stops_df)
    num_features = 1
    
    graph_signal_matrix = np.zeros((num_timesteps, num_nodes, num_features))
    
    # 데이터 채우기
    print("Filling graph signal matrix...")
    for _, row in df.iterrows():
        stop_idx = stop_to_idx[row['stop_id']]
        time_idx = (row['recorded_at'] - time_range[0]).total_seconds() // 3600
        time_idx = int(time_idx)
        
        if 0 <= time_idx < num_timesteps:
            graph_signal_matrix[time_idx, stop_idx, 0] = row['drt_probability']
    
    print(f"Graph signal matrix shape: {graph_signal_matrix.shape}")
    
    # 간단한 인접 행렬 (가까운 거리의 정류장들 연결)
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return R * c
    
    print("Creating adjacency matrix...")
    adj_matrix = np.zeros((num_nodes, num_nodes))
    threshold = 3.0  # 3km 이내
    
    for i in range(num_nodes):
        for j in range(i+1, num_nodes):
            dist = haversine_distance(
                stops_df.iloc[i]['latitude'], stops_df.iloc[i]['longitude'],
                stops_df.iloc[j]['latitude'], stops_df.iloc[j]['longitude']
            )
            if dist <= threshold:
                adj_matrix[i, j] = 1
                adj_matrix[j, i] = 1
    
    print(f"Adjacency matrix density: {np.sum(adj_matrix) / (adj_matrix.shape[0] * adj_matrix.shape[1]):.4f}")
    
    # 저장
    output_dir = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed'
    
    # 1. NPZ 파일로 저장
    data_file = os.path.join(output_dir, 'gapyeong_drt_full.npz')
    np.savez_compressed(
        data_file,
        data=graph_signal_matrix,
        adj_matrix=adj_matrix
    )
    print(f"Saved NPZ file: {data_file}")
    
    # 2. 메타데이터 저장
    metadata = {
        'num_nodes': num_nodes,
        'num_features': num_features,
        'num_timesteps': num_timesteps,
        'time_range': {
            'start': str(time_range[0]),
            'end': str(time_range[-1]),
            'freq': 'h'
        },
        'adjacency_threshold_km': threshold,
        'feature_description': 'DRT demand probability (normalized)'
    }
    
    metadata_file = os.path.join(output_dir, 'metadata_full.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved metadata: {metadata_file}")
    
    return data_file, metadata_file

def simple_preprocessing(data_file, num_of_hours=6, num_for_predict=1):
    """간단한 전처리"""
    print(f"\\nSimple preprocessing with {num_of_hours} hours history -> {num_for_predict} hours prediction")
    
    # 데이터 로드
    data = np.load(data_file)
    graph_signal = data['data']  # (T, N, F)
    adj_matrix = data['adj_matrix']
    
    print(f"Data shape: {graph_signal.shape}")
    
    samples_x = []
    samples_y = []
    
    # 슬라이딩 윈도우로 샘플 생성
    for i in range(num_of_hours, graph_signal.shape[0] - num_for_predict + 1):
        # 입력: (num_of_hours, N, F) -> (N, F, num_of_hours)
        x = graph_signal[i-num_of_hours:i].transpose(1, 2, 0)
        # 타겟: (num_for_predict, N, F) -> (N, num_for_predict)
        y = graph_signal[i:i+num_for_predict, :, 0]
        
        samples_x.append(x)
        samples_y.append(y)
    
    # 배열로 변환
    X = np.array(samples_x)  # (B, N, F, T)
    Y = np.array(samples_y)  # (B, N, T_pred)
    
    print(f"Generated {len(X)} samples")
    print(f"X shape: {X.shape}, Y shape: {Y.shape}")
    
    # 훈련/검증/테스트 분할
    n_samples = len(X)
    train_size = int(n_samples * 0.6)
    val_size = int(n_samples * 0.2)
    
    X_train = X[:train_size]
    Y_train = Y[:train_size]
    X_val = X[train_size:train_size+val_size]
    Y_val = Y[train_size:train_size+val_size]
    X_test = X[train_size+val_size:]
    Y_test = Y[train_size+val_size:]
    
    # 정규화
    mean = X_train.mean()
    std = X_train.std()
    
    X_train_norm = (X_train - mean) / std
    X_val_norm = (X_val - mean) / std
    X_test_norm = (X_test - mean) / std
    
    print(f"Train: {X_train_norm.shape}, {Y_train.shape}")
    print(f"Val: {X_val_norm.shape}, {Y_val.shape}")
    print(f"Test: {X_test_norm.shape}, {Y_test.shape}")
    
    # 저장
    output_file = data_file.replace('.npz', f'_processed_h{num_of_hours}_p{num_for_predict}.npz')
    np.savez_compressed(
        output_file,
        train_x=X_train_norm, train_target=Y_train,
        val_x=X_val_norm, val_target=Y_val,
        test_x=X_test_norm, test_target=Y_test,
        mean=mean, std=std,
        adj_matrix=adj_matrix
    )
    
    print(f"Saved processed data: {output_file}")
    return output_file

def main():
    """메인 실행"""
    print("Creating MST-GCN dataset for Gapyeong DRT...")
    
    # 1. 기본 데이터 생성
    data_file, metadata_file = create_simple_mstgcn_data()
    
    # 2. 전처리
    processed_file = simple_preprocessing(data_file, num_of_hours=6, num_for_predict=1)
    
    print("\\n" + "="*50)
    print("MST-GCN Dataset Creation Completed!")
    print("="*50)
    print(f"Raw data: {data_file}")
    print(f"Processed data: {processed_file}")
    print(f"Metadata: {metadata_file}")
    
    # 데이터 요약
    data = np.load(processed_file)
    print("\\nDataset Summary:")
    print(f"- Nodes (Bus Stops): {data['train_x'].shape[1]}")
    print(f"- Features: {data['train_x'].shape[2]}")
    print(f"- Input Time Steps: {data['train_x'].shape[3]}")
    print(f"- Output Time Steps: {data['train_target'].shape[2]}")
    print(f"- Training Samples: {data['train_x'].shape[0]}")
    print(f"- Validation Samples: {data['val_x'].shape[0]}")
    print(f"- Test Samples: {data['test_x'].shape[0]}")
    print(f"- Adjacency Matrix: {data['adj_matrix'].shape}")

if __name__ == "__main__":
    main()