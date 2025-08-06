#!/usr/bin/env python3
# create_mstgcn_sample.py - 빠른 샘플 생성

import pandas as pd
import numpy as np
import json

def create_sample_dataset():
    """샘플 MST-GCN 데이터셋 생성"""
    print("Creating sample MST-GCN dataset...")
    
    # 작은 샘플 사용
    csv_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_drt_sample.csv'
    df = pd.read_csv(csv_file)
    
    # 상위 50개 정류장만 사용
    top_stops = df['stop_id'].value_counts().head(50).index.tolist()
    df_sample = df[df['stop_id'].isin(top_stops)].copy()
    
    print(f"Using {len(top_stops)} stops with {len(df_sample)} records")
    
    # 정류장 정보
    stops_df = df_sample[['stop_id', 'stop_name', 'latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    stop_to_idx = {stop_id: idx for idx, stop_id in enumerate(stops_df['stop_id'])}
    
    # 시간 범위
    df_sample['recorded_at'] = pd.to_datetime(df_sample['recorded_at'])
    time_range = pd.date_range(
        start=df_sample['recorded_at'].min(),
        end=df_sample['recorded_at'].max(),
        freq='h'
    )
    
    print(f"Time range: {len(time_range)} hours")
    
    # 그래프 신호 행렬
    num_timesteps = len(time_range)
    num_nodes = len(stops_df)
    graph_signal_matrix = np.zeros((num_timesteps, num_nodes, 1))
    
    # 데이터 채우기
    for _, row in df_sample.iterrows():
        if row['stop_id'] in stop_to_idx:
            stop_idx = stop_to_idx[row['stop_id']]
            time_idx = int((row['recorded_at'] - time_range[0]).total_seconds() // 3600)
            if 0 <= time_idx < num_timesteps:
                graph_signal_matrix[time_idx, stop_idx, 0] = row['drt_probability']
    
    # 간단한 인접 행렬 (모든 노드가 연결된 완전 그래프)
    adj_matrix = np.ones((num_nodes, num_nodes)) - np.eye(num_nodes)
    
    print(f"Graph signal matrix: {graph_signal_matrix.shape}")
    print(f"Adjacency matrix: {adj_matrix.shape}")
    
    # 간단한 전처리
    num_of_hours = 6
    samples_x, samples_y = [], []
    
    for i in range(num_of_hours, num_timesteps - 1):
        x = graph_signal_matrix[i-num_of_hours:i].transpose(1, 2, 0)  # (N, F, T)
        y = graph_signal_matrix[i:i+1, :, 0].T  # (N, 1)
        samples_x.append(x)
        samples_y.append(y)
    
    X = np.array(samples_x)  # (B, N, F, T)
    Y = np.array(samples_y)  # (B, N, 1)
    
    print(f"Generated {len(X)} samples")
    print(f"X shape: {X.shape}, Y shape: {Y.shape}")
    
    if len(X) == 0:
        print("No samples generated!")
        return
    
    # 분할
    n = len(X)
    train_size = int(n * 0.6)
    val_size = int(n * 0.2)
    
    X_train, Y_train = X[:train_size], Y[:train_size]
    X_val, Y_val = X[train_size:train_size+val_size], Y[train_size:train_size+val_size]
    X_test, Y_test = X[train_size+val_size:], Y[train_size+val_size:]
    
    # 정규화
    mean, std = X_train.mean(), X_train.std()
    X_train_norm = (X_train - mean) / std
    X_val_norm = (X_val - mean) / std
    X_test_norm = (X_test - mean) / std
    
    # 저장
    output_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_mstgcn_sample.npz'
    np.savez_compressed(
        output_file,
        train_x=X_train_norm, train_target=Y_train,
        val_x=X_val_norm, val_target=Y_val,
        test_x=X_test_norm, test_target=Y_test,
        mean=mean, std=std,
        adj_matrix=adj_matrix
    )
    
    # 메타데이터
    metadata = {
        'num_nodes': num_nodes,
        'num_features': 1,
        'input_timesteps': num_of_hours,
        'output_timesteps': 1,
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'stops_info': {row['stop_id']: {
            'index': idx, 'name': row['stop_name'],
            'lat': row['latitude'], 'lon': row['longitude']
        } for idx, row in stops_df.iterrows()}
    }
    
    metadata_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_mstgcn_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\\nSaved files:")
    print(f"- Data: {output_file}")
    print(f"- Metadata: {metadata_file}")
    
    print(f"\\nDataset Summary:")
    print(f"- Nodes: {num_nodes}")
    print(f"- Input time steps: {num_of_hours}")
    print(f"- Train samples: {len(X_train)}")
    print(f"- Val samples: {len(X_val)}")
    print(f"- Test samples: {len(X_test)}")
    
    return output_file, metadata_file

if __name__ == "__main__":
    create_sample_dataset()