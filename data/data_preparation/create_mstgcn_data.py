#!/usr/bin/env python3
# data_preparation/create_mstgcn_data.py
# CSV 데이터를 MST-GCN 형식으로 변환

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Haversine 공식을 사용한 거리 계산 (km)
    """
    R = 6371  # 지구 반지름 (km)
    
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return R * c

def create_adjacency_matrix(stops_df, threshold=5.0):
    """
    거리 기반 인접 행렬 생성
    """
    n = len(stops_df)
    adj_matrix = np.zeros((n, n))
    
    for i in range(n):
        for j in range(i+1, n):
            dist = haversine_distance(
                stops_df.iloc[i]['latitude'], stops_df.iloc[i]['longitude'],
                stops_df.iloc[j]['latitude'], stops_df.iloc[j]['longitude']
            )
            if dist <= threshold:
                adj_matrix[i, j] = 1
                adj_matrix[j, i] = 1
    
    return adj_matrix

def create_graph_signal_matrix(df):
    """
    시공간 그래프 신호 행렬 생성
    """
    print("Creating graph signal matrix...")
    
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
        freq='H'
    )
    print(f"Time range: {time_range[0]} to {time_range[-1]} ({len(time_range)} steps)")
    
    # 그래프 신호 행렬 초기화 (T, N, F)
    num_timesteps = len(time_range)
    num_nodes = len(stops_df)
    num_features = 1  # DRT probability
    
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
    return graph_signal_matrix, stops_df, time_range

def save_mstgcn_format(graph_signal_matrix, adj_matrix, stops_df, time_range, output_dir):
    """
    MST-GCN 형식으로 저장
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. NPZ 파일로 저장
    data_file = os.path.join(output_dir, 'gapyeong_drt_data.npz')
    np.savez_compressed(
        data_file,
        data=graph_signal_matrix,  # (T, N, F)
        adj_matrix=adj_matrix
    )
    print(f"Saved NPZ file: {data_file}")
    
    # 2. 메타데이터 저장
    metadata = {
        'num_nodes': len(stops_df),
        'num_features': graph_signal_matrix.shape[2],
        'num_timesteps': graph_signal_matrix.shape[0],
        'time_range': {
            'start': str(time_range[0]),
            'end': str(time_range[-1]),
            'freq': 'H'
        },
        'stops_info': {
            row['stop_id']: {
                'index': idx,
                'name': row['stop_name'],
                'lat': row['latitude'],
                'lon': row['longitude']
            }
            for idx, row in stops_df.iterrows()
        },
        'feature_description': 'DRT demand probability (normalized)'
    }
    
    import json
    metadata_file = os.path.join(output_dir, 'metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved metadata: {metadata_file}")
    
    # 3. 정류장 정보 CSV 저장
    stops_file = os.path.join(output_dir, 'stops_info.csv')
    stops_df.to_csv(stops_file, index=False)
    print(f"Saved stops info: {stops_file}")
    
    return data_file, metadata_file, stops_file

def get_sample_indices(data_sequence, num_of_weeks, num_of_days, num_of_hours, 
                      label_start_idx, num_for_predict, points_per_hour=1):
    """
    MST-GCN 샘플 인덱스 생성
    """
    week_sample, day_sample, hour_sample = None, None, None
    
    if label_start_idx + num_for_predict > data_sequence.shape[0]:
        return week_sample, day_sample, hour_sample, None
    
    # 시간 패턴
    if num_of_hours > 0:
        hour_start = label_start_idx - num_of_hours
        if hour_start >= 0:
            hour_sample = data_sequence[hour_start:label_start_idx]
    
    # 일간 패턴
    if num_of_days > 0:
        day_start = label_start_idx - num_of_days * 24 * points_per_hour
        if day_start >= 0:
            day_sample = data_sequence[day_start:day_start + num_of_days * 24 * points_per_hour:24 * points_per_hour]
    
    # 주간 패턴
    if num_of_weeks > 0:
        week_start = label_start_idx - num_of_weeks * 7 * 24 * points_per_hour
        if week_start >= 0:
            week_indices = []
            for week in range(num_of_weeks):
                start_idx = week_start + week * 7 * 24 * points_per_hour
                week_indices.extend(range(start_idx, start_idx + 7 * 24 * points_per_hour, 24 * points_per_hour))
            if all(idx >= 0 for idx in week_indices):
                week_sample = data_sequence[week_indices]
    
    target = data_sequence[label_start_idx:label_start_idx + num_for_predict]
    
    return week_sample, day_sample, hour_sample, target

def read_and_generate_dataset(graph_signal_matrix_filename,
                             num_of_weeks=1, num_of_days=1, num_of_hours=3,
                             num_for_predict=1, points_per_hour=1, save=False):
    """
    MST-GCN 데이터셋 생성
    """
    print(f"Loading data from: {graph_signal_matrix_filename}")
    
    # 데이터 로드
    data_file = np.load(graph_signal_matrix_filename, allow_pickle=True)
    data_seq = data_file['data']  # (T, N, F)
    
    print(f"Original data shape: {data_seq.shape}")
    print(f"Time steps: {data_seq.shape[0]}, Nodes: {data_seq.shape[1]}, Features: {data_seq.shape[2]}")
    
    all_samples = []
    
    # 샘플 생성
    for idx in range(data_seq.shape[0]):
        sample = get_sample_indices(
            data_seq, num_of_weeks, num_of_days,
            num_of_hours, idx, num_for_predict,
            points_per_hour
        )
        
        if all(s is None for s in sample[:3]) or sample[3] is None:
            continue
            
        week_sample, day_sample, hour_sample, target = sample
        
        sample_list = []
        
        # 주간 패턴
        if num_of_weeks > 0 and week_sample is not None:
            week_sample = np.expand_dims(week_sample, axis=0).transpose((0, 2, 3, 1))
            sample_list.append(week_sample)
        
        # 일간 패턴  
        if num_of_days > 0 and day_sample is not None:
            day_sample = np.expand_dims(day_sample, axis=0).transpose((0, 2, 3, 1))
            sample_list.append(day_sample)
        
        # 시간 패턴
        if num_of_hours > 0 and hour_sample is not None:
            hour_sample = np.expand_dims(hour_sample, axis=0).transpose((0, 2, 3, 1))
            sample_list.append(hour_sample)
        
        # 타겟
        if target is not None:
            target = np.expand_dims(target, axis=0).transpose((0, 2, 3, 1))[:, :, 0, :]
            sample_list.append(target)
            
            if len(sample_list) > 1:  # 최소한 입력과 타겟이 있어야 함
                all_samples.append(sample_list)
    
    print(f"Generated {len(all_samples)} samples")
    
    if len(all_samples) == 0:
        raise ValueError("No valid samples generated. Check data parameters.")
    
    # 훈련/검증/테스트 분할 (6:2:2)
    split_line1 = int(len(all_samples) * 0.6)
    split_line2 = int(len(all_samples) * 0.8)
    
    training_set = [np.concatenate(i, axis=0) for i in zip(*all_samples[:split_line1])]
    validation_set = [np.concatenate(i, axis=0) for i in zip(*all_samples[split_line1:split_line2])]
    testing_set = [np.concatenate(i, axis=0) for i in zip(*all_samples[split_line2:])]
    
    # 입력 특성 결합
    train_x = np.concatenate(training_set[:-1], axis=-1)
    val_x = np.concatenate(validation_set[:-1], axis=-1)
    test_x = np.concatenate(testing_set[:-1], axis=-1)
    
    # 타겟
    train_target = training_set[-1]
    val_target = validation_set[-1]
    test_target = testing_set[-1]
    
    # 정규화
    mean = train_x.mean()
    std = train_x.std()
    
    train_x_norm = (train_x - mean) / std
    val_x_norm = (val_x - mean) / std
    test_x_norm = (test_x - mean) / std
    
    all_data = {
        'train': {'x': train_x_norm, 'target': train_target},
        'val': {'x': val_x_norm, 'target': val_target},
        'test': {'x': test_x_norm, 'target': test_target},
        'stats': {'_mean': mean, '_std': std}
    }
    
    print('Train x:', all_data['train']['x'].shape)
    print('Train target:', all_data['train']['target'].shape)
    print('Val x:', all_data['val']['x'].shape)
    print('Val target:', all_data['val']['target'].shape)
    print('Test x:', all_data['test']['x'].shape)
    print('Test target:', all_data['test']['target'].shape)
    
    # 저장
    if save:
        file_name = os.path.basename(graph_signal_matrix_filename).split('.')[0]
        dirpath = os.path.dirname(graph_signal_matrix_filename)
        filename = os.path.join(dirpath, f"{file_name}_r{num_of_hours}_d{num_of_days}_w{num_of_weeks}_mstgcn")
        
        print(f'Saving preprocessed file to: {filename}.npz')
        np.savez_compressed(
            filename,
            train_x=all_data['train']['x'], train_target=all_data['train']['target'],
            val_x=all_data['val']['x'], val_target=all_data['val']['target'],
            test_x=all_data['test']['x'], test_target=all_data['test']['target'],
            mean=all_data['stats']['_mean'], std=all_data['stats']['_std']
        )
    
    return all_data

def main():
    """메인 실행"""
    # CSV 파일 로드
    csv_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_drt_sample.csv'
    output_dir = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed'
    
    print("Loading CSV data...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records")
    
    # 그래프 신호 행렬 생성
    graph_signal_matrix, stops_df, time_range = create_graph_signal_matrix(df)
    
    # 인접 행렬 생성
    print("Creating adjacency matrix...")
    adj_matrix = create_adjacency_matrix(stops_df, threshold=5.0)
    print(f"Adjacency matrix shape: {adj_matrix.shape}")
    print(f"Adjacency density: {np.sum(adj_matrix) / (adj_matrix.shape[0] * adj_matrix.shape[1]):.4f}")
    
    # MST-GCN 형식으로 저장
    data_file, metadata_file, stops_file = save_mstgcn_format(
        graph_signal_matrix, adj_matrix, stops_df, time_range, output_dir
    )
    
    # 데이터셋 생성 (전처리)
    print("\\nGenerating MST-GCN dataset...")
    dataset = read_and_generate_dataset(
        data_file,
        num_of_weeks=1,
        num_of_days=1, 
        num_of_hours=3,
        num_for_predict=1,
        points_per_hour=1,
        save=True
    )
    
    print("\\nDataset creation completed!")
    print(f"Data file: {data_file}")
    print(f"Metadata: {metadata_file}")
    print(f"Stops info: {stops_file}")

if __name__ == "__main__":
    main()