#!/usr/bin/env python3
"""
8개월 데이터 통합 및 시간 순서 기반 데이터 분할 스크립트
Google Colab용 MST-GCN 학습 데이터 준비

수정사항:
1. 8개월 데이터를 하나로 통합
2. 시간 순서 기반 train/val/test 분할 (Data Leakage 방지)
3. 데이터 경로를 '/content/drive/MyDrive/train_dataset/dataset.npz'로 변경
"""

import numpy as np
import os
from typing import List, Dict, Tuple

def find_common_stops(monthly_dir: str) -> np.ndarray:
    """모든 월별 파일에서 공통 정류장 찾기"""
    npz_files = sorted([f for f in os.listdir(monthly_dir) if f.endswith('.npz')])
    
    common_stops = None
    for file in npz_files:
        file_path = os.path.join(monthly_dir, file)
        data = np.load(file_path)
        stop_ids = data['stop_ids']
        
        if common_stops is None:
            common_stops = set(stop_ids)
        else:
            common_stops = common_stops.intersection(set(stop_ids))
    
    return np.array(sorted(list(common_stops)))

def filter_data_by_stops(data: Dict, common_stops: np.ndarray) -> Dict:
    """공통 정류장으로 데이터 필터링"""
    stop_ids = data['stop_ids']
    
    # 공통 정류장의 인덱스 찾기
    common_indices = []
    for stop in common_stops:
        idx = np.where(stop_ids == stop)[0]
        if len(idx) > 0:
            common_indices.append(idx[0])
    
    common_indices = np.array(common_indices)
    
    # 데이터 필터링
    filtered_data = {}
    for key in data.keys():
        if key in ['X_hour', 'X_day', 'X_week', 'y']:
            # 시계열 데이터: (samples, nodes, ...) 구조
            filtered_data[key] = data[key][:, common_indices, ...]
        elif key in ['feature_matrix']:
            # 피처 행렬: (features, nodes, time) 구조
            filtered_data[key] = data[key][:, common_indices, :]
        elif key in ['adj_matrix']:
            # 인접 행렬: (nodes, nodes) 구조
            filtered_data[key] = data[key][np.ix_(common_indices, common_indices)]
        elif key == 'stop_ids':
            filtered_data[key] = common_stops
        else:
            filtered_data[key] = data[key]
    
    return filtered_data

def merge_monthly_data(monthly_dir: str, output_path: str) -> None:
    """8개월 데이터를 시간 순서대로 통합"""
    
    print("🔄 8개월 데이터 통합 시작...")
    
    # 1. 공통 정류장 찾기
    print("1. 공통 정류장 식별 중...")
    common_stops = find_common_stops(monthly_dir)
    print(f"   공통 정류장 수: {len(common_stops)}개")
    
    # 2. 월별 파일 로드 및 필터링
    npz_files = sorted([f for f in os.listdir(monthly_dir) if f.endswith('.npz')])
    
    merged_data = {
        'X_hour': [],
        'X_day': [],
        'X_week': [],
        'y': [],
        'feature_matrix': None,
        'stop_ids': common_stops,
        'adj_matrix': None
    }
    
    print("2. 월별 데이터 로드 및 필터링 중...")
    total_samples = 0
    
    for i, file in enumerate(npz_files):
        file_path = os.path.join(monthly_dir, file)
        print(f"   처리 중: {file}")
        
        data = {key: val for key, val in np.load(file_path).items()}
        filtered_data = filter_data_by_stops(data, common_stops)
        
        # 시계열 데이터 누적
        merged_data['X_hour'].append(filtered_data['X_hour'])
        merged_data['X_day'].append(filtered_data['X_day'])
        merged_data['X_week'].append(filtered_data['X_week'])
        merged_data['y'].append(filtered_data['y'])
        
        total_samples += filtered_data['X_hour'].shape[0]
        print(f"     샘플 수: {filtered_data['X_hour'].shape[0]}")
        
        # 마지막 파일의 메타데이터 사용
        if i == len(npz_files) - 1:
            merged_data['feature_matrix'] = filtered_data['feature_matrix']
            merged_data['adj_matrix'] = filtered_data['adj_matrix']
    
    # 3. 시간축으로 연결
    print("3. 시간축으로 데이터 연결 중...")
    merged_data['X_hour'] = np.concatenate(merged_data['X_hour'], axis=0)
    merged_data['X_day'] = np.concatenate(merged_data['X_day'], axis=0)
    merged_data['X_week'] = np.concatenate(merged_data['X_week'], axis=0)
    merged_data['y'] = np.concatenate(merged_data['y'], axis=0)
    
    print(f"✅ 통합 완료:")
    print(f"   총 샘플 수: {total_samples}")
    print(f"   정류장 수: {len(common_stops)}")
    print(f"   X_hour shape: {merged_data['X_hour'].shape}")
    print(f"   X_day shape: {merged_data['X_day'].shape}")
    print(f"   X_week shape: {merged_data['X_week'].shape}")
    print(f"   y shape: {merged_data['y'].shape}")
    
    # 4. 저장
    print(f"4. 저장 중: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.savez_compressed(output_path, **merged_data)
    print("✅ 저장 완료!")

# TimeSeriesDataset는 Google Colab에서 torch와 함께 정의됨

def create_temporal_splits(dataset_size: int, train_ratio: float = 0.7, 
                         val_ratio: float = 0.15) -> Tuple[List[int], List[int], List[int]]:
    """시간 순서 기반 데이터 분할 (Data Leakage 방지)"""
    
    train_end = int(dataset_size * train_ratio)
    val_end = int(dataset_size * (train_ratio + val_ratio))
    
    train_indices = list(range(0, train_end))
    val_indices = list(range(train_end, val_end))
    test_indices = list(range(val_end, dataset_size))
    
    print(f"📊 시간 순서 기반 데이터 분할:")
    print(f"   Train: 샘플 [0:{train_end}] ({len(train_indices)} 샘플, {len(train_indices)/dataset_size*100:.1f}%)")
    print(f"   Val:   샘플 [{train_end}:{val_end}] ({len(val_indices)} 샘플, {len(val_indices)/dataset_size*100:.1f}%)")
    print(f"   Test:  샘플 [{val_end}:{dataset_size}] ({len(test_indices)} 샘플, {len(test_indices)/dataset_size*100:.1f}%)")
    
    return train_indices, val_indices, test_indices

# Google Colab용 데이터 준비 함수
def prepare_colab_dataset():
    """Google Colab용 데이터 준비 (로컬에서 실행)"""
    
    # 로컬 경로
    monthly_dir = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/monthly'
    output_dir = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/colab_dataset'
    output_path = os.path.join(output_dir, 'dataset.npz')
    
    # 8개월 데이터 통합
    merge_monthly_data(monthly_dir, output_path)
    
    print(f"\n🎯 Google Colab으로 업로드할 파일:")
    print(f"   파일 경로: {output_path}")
    print(f"   Colab 저장 경로: /content/drive/MyDrive/train_dataset/dataset.npz")
    print(f"\n📋 Colab에서 사용할 수정된 Cell 3 코드:")
    print(f"""
# Google Colab Cell 3 수정 버전
base_path = '/content/drive/MyDrive/train_dataset/dataset.npz'
data = np.load(base_path)

feature_matrix = data['feature_matrix']
stop_ids = data['stop_ids'] 
adj_mx = data['adj_matrix']
X_hour = data['X_hour']
X_day = data['X_day']
X_week = data['X_week']
y = data['y']

print("✅ 통합된 8개월 MST-GCN 데이터 로딩 완료:")
print(f"Feature matrix shape: {{feature_matrix.shape}}")
print(f"정류장 수: {{len(stop_ids)}}")
print(f"X_hour shape: {{X_hour.shape}}")
print(f"X_day shape: {{X_day.shape}}")
print(f"X_week shape: {{X_week.shape}}")
print(f"y shape: {{y.shape}}")
""")

    print(f"\n📋 Colab에서 사용할 수정된 Cell 6 코드 (Data Leakage 방지):")
    print(f"""
# Google Colab Cell 6 수정 버전 - 시간 순서 기반 분할
X_hour_tensor = torch.from_numpy(X_hour).type(torch.FloatTensor)
X_day_tensor = torch.from_numpy(X_day).type(torch.FloatTensor)
X_week_tensor = torch.from_numpy(X_week).type(torch.FloatTensor)
y_tensor = torch.from_numpy(y).type(torch.FloatTensor)

# 전체 데이터셋 생성
dataset = MultiScaleDataset(X_hour_tensor, X_day_tensor, X_week_tensor, y_tensor)

# 🚨 시간 순서 기반 분할 (Data Leakage 방지)
dataset_size = len(dataset)
train_end = int(dataset_size * 0.7)
val_end = int(dataset_size * 0.85)

train_indices = list(range(0, train_end))
val_indices = list(range(train_end, val_end))
test_indices = list(range(val_end, dataset_size))

# Subset으로 분할
train_dataset = Subset(dataset, train_indices)
val_dataset = Subset(dataset, val_indices)
test_dataset = Subset(dataset, test_indices)

# DataLoader 생성
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)  # Train만 셔플
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

print(f"📊 시간 순서 기반 데이터 분할 (Data Leakage 방지):")
print(f"전체: {{len(dataset)}} 샘플")
print(f"학습: {{len(train_dataset)}} 샘플 (초기 70% 시간대)")
print(f"검증: {{len(val_dataset)}} 샘플 (중간 15% 시간대)")
print(f"테스트: {{len(test_dataset)}} 샘플 (마지막 15% 시간대)")
""")

if __name__ == "__main__":
    prepare_colab_dataset()