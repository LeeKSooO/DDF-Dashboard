#!/usr/bin/env python3
# data_preparation/mstgcn_utils.py
# MST-GCN 모델을 위한 유틸리티 함수들

import numpy as np
import pandas as pd
import torch
import os
import pickle
from typing import Tuple, Optional, List

def get_sample_indices(data_sequence: np.ndarray, 
                      num_of_weeks: int, 
                      num_of_days: int,
                      num_of_hours: int, 
                      label_start_idx: int,
                      num_for_predict: int, 
                      points_per_hour: int = 1) -> Tuple:
    """
    MST-GCN을 위한 샘플 인덱스 생성
    
    Args:
        data_sequence: (time_steps, num_nodes, features) 형태의 데이터
        num_of_weeks: 주간 패턴 사용할 주 수
        num_of_days: 일간 패턴 사용할 일 수  
        num_of_hours: 시간 패턴 사용할 시간 수
        label_start_idx: 예측 시작 인덱스
        num_for_predict: 예측할 시간 스텝 수
        points_per_hour: 시간당 데이터 포인트 수 (기본 1 = 1시간 단위)
    
    Returns:
        (week_sample, day_sample, hour_sample, target) 튜플
    """
    
    week_sample, day_sample, hour_sample = None, None, None
    
    if label_start_idx + num_for_predict > data_sequence.shape[0]:
        return week_sample, day_sample, hour_sample, None
    
    if num_of_hours > 0:
        hour_start = label_start_idx - num_of_hours
        if hour_start >= 0:
            hour_sample = data_sequence[hour_start:label_start_idx]
    
    if num_of_days > 0:
        day_start = label_start_idx - num_of_days * 24 * points_per_hour
        if day_start >= 0:
            day_sample = data_sequence[day_start:day_start + num_of_days * 24 * points_per_hour:24 * points_per_hour]
    
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


def normalization(train: np.ndarray, 
                 val: np.ndarray, 
                 test: np.ndarray) -> Tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
    """
    Z-score 정규화
    
    Args:
        train: 훈련 데이터
        val: 검증 데이터  
        test: 테스트 데이터
    
    Returns:
        (stats, train_norm, val_norm, test_norm)
    """
    
    mean = train.mean()
    std = train.std()
    
    stats = {'_mean': mean, '_std': std}
    
    def normalize_data(data):
        return (data - mean) / std
    
    train_norm = normalize_data(train)
    val_norm = normalize_data(val) 
    test_norm = normalize_data(test)
    
    return stats, train_norm, val_norm, test_norm


def read_and_generate_dataset(graph_signal_matrix_filename: str,
                             num_of_weeks: int = 1, 
                             num_of_days: int = 1,
                             num_of_hours: int = 3, 
                             num_for_predict: int = 1,
                             points_per_hour: int = 1, 
                             save: bool = False) -> dict:
    """
    MST-GCN을 위한 데이터셋 생성
    
    Args:
        graph_signal_matrix_filename: 그래프 신호 행렬 파일 경로 (.npz)
        num_of_weeks: 주간 패턴 수
        num_of_days: 일간 패턴 수
        num_of_hours: 시간 패턴 수
        num_for_predict: 예측할 시간 스텝 수
        points_per_hour: 시간당 포인트 수
        save: 전처리된 데이터 저장 여부
    
    Returns:
        전처리된 데이터 딕셔너리
    """
    
    print(f"Loading data from: {graph_signal_matrix_filename}")
    
    # 데이터 로드
    data_file = np.load(graph_signal_matrix_filename, allow_pickle=True)
    data_seq = data_file['data']  # (T, N, F) 형태
    
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
    (stats, train_x_norm, val_x_norm, test_x_norm) = normalization(train_x, val_x, test_x)
    
    all_data = {
        'train': {'x': train_x_norm, 'target': train_target},
        'val': {'x': val_x_norm, 'target': val_target},
        'test': {'x': test_x_norm, 'target': test_target},
        'stats': {'_mean': stats['_mean'], '_std': stats['_std']}
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


def load_graphdata_channel1(graph_signal_matrix_filename: str, 
                           num_of_hours: int, 
                           num_of_days: int, 
                           num_of_weeks: int, 
                           device: torch.device, 
                           batch_size: int, 
                           shuffle: bool = True) -> Tuple:
    """
    전처리된 그래프 데이터 로드 및 DataLoader 생성
    
    Args:
        graph_signal_matrix_filename: 원본 데이터 파일 경로
        num_of_hours: 시간 패턴 수
        num_of_days: 일간 패턴 수  
        num_of_weeks: 주간 패턴 수
        device: PyTorch 디바이스
        batch_size: 배치 크기
        shuffle: 셔플 여부
    
    Returns:
        (train_loader, train_target_tensor, val_loader, val_target_tensor, 
         test_loader, test_target_tensor, mean, std)
    """
    
    file = os.path.basename(graph_signal_matrix_filename).split('.')[0]
    dirpath = os.path.dirname(graph_signal_matrix_filename)
    filename = os.path.join(dirpath, f"{file}_r{num_of_hours}_d{num_of_days}_w{num_of_weeks}_mstgcn.npz")
    
    print(f'Loading preprocessed file: {filename}')
    
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Preprocessed file not found: {filename}")
    
    file_data = np.load(filename)
    
    train_x, train_target = file_data['train_x'], file_data['train_target']
    val_x, val_target = file_data['val_x'], file_data['val_target']
    test_x, test_target = file_data['test_x'], file_data['test_target']
    mean, std = file_data['mean'], file_data['std']
    
    # 첫 번째 특성만 사용 (DRT probability)
    if train_x.shape[2] > 1:
        print(f"Original feature size: {train_x.shape[2]}, using the first feature.")
        train_x = train_x[:, :, 0:1, :]
        val_x = val_x[:, :, 0:1, :]
        test_x = test_x[:, :, 0:1, :]
        if len(mean.shape) > 0:
            mean = mean[0] if hasattr(mean, 'shape') else mean
            std = std[0] if hasattr(std, 'shape') else std
    
    # PyTorch 텐서로 변환
    train_x_tensor = torch.from_numpy(train_x).type(torch.FloatTensor).to(device)
    train_target_tensor = torch.from_numpy(train_target).type(torch.FloatTensor).to(device)
    
    val_x_tensor = torch.from_numpy(val_x).type(torch.FloatTensor).to(device)
    val_target_tensor = torch.from_numpy(val_target).type(torch.FloatTensor).to(device)
    
    test_x_tensor = torch.from_numpy(test_x).type(torch.FloatTensor).to(device)
    test_target_tensor = torch.from_numpy(test_target).type(torch.FloatTensor).to(device)
    
    # DataLoader 생성
    train_dataset = torch.utils.data.TensorDataset(train_x_tensor, train_target_tensor)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=shuffle)
    
    val_dataset = torch.utils.data.TensorDataset(val_x_tensor, val_target_tensor)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    test_dataset = torch.utils.data.TensorDataset(test_x_tensor, test_target_tensor)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    print('Train:', train_x_tensor.size(), train_target_tensor.size())
    print('Validation:', val_x_tensor.size(), val_target_tensor.size())
    print('Test:', test_x_tensor.size(), test_target_tensor.size())
    
    return (train_loader, train_target_tensor, val_loader, val_target_tensor, 
            test_loader, test_target_tensor, mean, std)


def calculate_cheb_poly(adj_matrix: np.ndarray, K: int) -> List[torch.Tensor]:
    """
    체비셰프 다항식 계산
    
    Args:
        adj_matrix: 인접 행렬
        K: 체비셰프 다항식 차수
    
    Returns:
        체비셰프 다항식 리스트
    """
    
    num_nodes = adj_matrix.shape[0]
    
    # 정규화된 라플라시안 계산
    degree = np.sum(adj_matrix, axis=1)
    degree[degree == 0] = 1  # 0으로 나누기 방지
    
    D_inv_sqrt = np.diag(1.0 / np.sqrt(degree))
    normalized_laplacian = np.eye(num_nodes) - D_inv_sqrt @ adj_matrix @ D_inv_sqrt
    
    # 고유값의 최대값으로 스케일링
    eigenvalues = np.linalg.eigvals(normalized_laplacian)
    lambda_max = np.max(eigenvalues.real)
    
    if lambda_max > 1e-8:
        scaled_laplacian = (2.0 / lambda_max) * normalized_laplacian - np.eye(num_nodes)
    else:
        scaled_laplacian = normalized_laplacian
    
    # 체비셰프 다항식 계산
    cheb_polynomials = []
    
    # T_0 = I
    cheb_polynomials.append(torch.FloatTensor(np.eye(num_nodes)))
    
    if K > 1:
        # T_1 = L_scaled
        cheb_polynomials.append(torch.FloatTensor(scaled_laplacian))
    
    # T_k = 2 * L_scaled * T_{k-1} - T_{k-2}
    for k in range(2, K):
        T_k = 2 * scaled_laplacian @ cheb_polynomials[-1].numpy() - cheb_polynomials[-2].numpy()
        cheb_polynomials.append(torch.FloatTensor(T_k))
    
    return cheb_polynomials


def create_adjacency_from_csv(csv_file: str, 
                             distance_threshold: float = 5.0) -> Tuple[np.ndarray, dict]:
    """
    CSV 파일에서 인접 행렬 생성
    
    Args:
        csv_file: 정류장 정보 CSV 파일
        distance_threshold: 거리 임계값 (km)
    
    Returns:
        (adjacency_matrix, stop_mapping)
    """
    
    df = pd.read_csv(csv_file)
    
    # 고유한 정류장 정보 추출
    stops_df = df[['stop_id', 'stop_name', 'latitude', 'longitude']].drop_duplicates()
    
    num_stops = len(stops_df)
    adj_matrix = np.zeros((num_stops, num_stops))
    
    stop_mapping = {}
    for idx, row in stops_df.iterrows():
        stop_mapping[row['stop_id']] = {
            'index': idx,
            'name': row['stop_name'],
            'lat': row['latitude'], 
            'lon': row['longitude']
        }
    
    # 거리 기반 인접성 계산
    coords = stops_df[['latitude', 'longitude']].values
    coords_rad = np.radians(coords)
    
    from sklearn.metrics.pairwise import haversine_distances
    distances = haversine_distances(coords_rad) * 6371  # km
    
    # 임계값 이내의 정류장들을 연결
    adj_matrix = (distances <= distance_threshold).astype(float)
    np.fill_diagonal(adj_matrix, 0)  # 자기 자신과의 연결 제거
    
    return adj_matrix, stop_mapping