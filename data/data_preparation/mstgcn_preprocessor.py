#!/usr/bin/env python3
# data_preparation/mstgcn_preprocessor.py
# MST-GCN 데이터 전처리 (차원 문제 해결)

import numpy as np
import os

def get_sample_indices(data_sequence, num_of_weeks, num_of_days, num_of_hours, 
                      label_start_idx, num_for_predict, points_per_hour=1):
    """MST-GCN 샘플 인덱스 생성 (차원 수정)"""
    week_sample, day_sample, hour_sample = None, None, None
    
    if label_start_idx + num_for_predict > data_sequence.shape[0]:
        return week_sample, day_sample, hour_sample, None
    
    # 시간 패턴
    if num_of_hours > 0:
        hour_start = label_start_idx - num_of_hours
        if hour_start >= 0:
            hour_sample = data_sequence[hour_start:label_start_idx]
    
    # 일간 패턴 (24시간 간격으로 추출)
    if num_of_days > 0:
        day_samples = []
        for d in range(num_of_days):
            day_idx = label_start_idx - (d + 1) * 24 * points_per_hour
            if day_idx >= 0:
                day_samples.append(data_sequence[day_idx:day_idx + 1])
        if day_samples:
            day_sample = np.concatenate(day_samples, axis=0)
    
    # 주간 패턴 (7일 간격으로 추출)
    if num_of_weeks > 0:
        week_samples = []
        for w in range(num_of_weeks):
            week_idx = label_start_idx - (w + 1) * 7 * 24 * points_per_hour
            if week_idx >= 0:
                week_samples.append(data_sequence[week_idx:week_idx + 1])
        if week_samples:
            week_sample = np.concatenate(week_samples, axis=0)
    
    target = data_sequence[label_start_idx:label_start_idx + num_for_predict]
    
    return week_sample, day_sample, hour_sample, target


def read_and_generate_dataset(graph_signal_matrix_filename,
                             num_of_weeks=1, num_of_days=1, num_of_hours=3,
                             num_for_predict=1, points_per_hour=1, save=False):
    """MST-GCN 데이터셋 생성 (수정된 버전)"""
    print(f"Loading data from: {graph_signal_matrix_filename}")
    
    # 데이터 로드
    data_file = np.load(graph_signal_matrix_filename, allow_pickle=True)
    data_seq = data_file['data']  # (T, N, F)
    
    print(f"Original data shape: {data_seq.shape}")
    print(f"Time steps: {data_seq.shape[0]}, Nodes: {data_seq.shape[1]}, Features: {data_seq.shape[2]}")
    
    all_samples = []
    
    # 샘플 생성 (더 보수적인 접근)
    min_history = max(num_of_hours, num_of_days * 24, num_of_weeks * 7 * 24)
    for idx in range(min_history, data_seq.shape[0] - num_for_predict + 1):
        sample = get_sample_indices(
            data_seq, num_of_weeks, num_of_days,
            num_of_hours, idx, num_for_predict,
            points_per_hour
        )
        
        week_sample, day_sample, hour_sample, target = sample
        
        # 모든 패턴이 존재하는지 확인
        if target is None:
            continue
            
        sample_list = []
        input_sequences = []
        
        # 각 패턴을 (B, N, F, T) 형태로 변환
        if num_of_weeks > 0 and week_sample is not None:
            # (T, N, F) -> (1, N, F, T)
            week_sample_reshaped = week_sample.transpose(1, 2, 0)[np.newaxis, :]
            input_sequences.append(week_sample_reshaped)
        
        if num_of_days > 0 and day_sample is not None:
            day_sample_reshaped = day_sample.transpose(1, 2, 0)[np.newaxis, :]
            input_sequences.append(day_sample_reshaped)
        
        if num_of_hours > 0 and hour_sample is not None:
            hour_sample_reshaped = hour_sample.transpose(1, 2, 0)[np.newaxis, :]
            input_sequences.append(hour_sample_reshaped)
        
        # 타겟: (T, N, F) -> (1, N, T)
        target_reshaped = target.transpose(1, 2, 0)[:, 0, :][np.newaxis, :]
        
        if input_sequences:
            # 입력들을 시간 축으로 연결: (1, N, F, T_total)
            concatenated_input = np.concatenate(input_sequences, axis=3)
            sample_list = [concatenated_input, target_reshaped]
            all_samples.append(sample_list)
    
    print(f"Generated {len(all_samples)} samples")
    
    if len(all_samples) == 0:
        raise ValueError("No valid samples generated. Check data parameters.")
    
    # 훈련/검증/테스트 분할 (6:2:2)
    split_line1 = int(len(all_samples) * 0.6)
    split_line2 = int(len(all_samples) * 0.8)
    
    training_set = [np.concatenate([sample[i] for sample in all_samples[:split_line1]], axis=0) for i in range(2)]
    validation_set = [np.concatenate([sample[i] for sample in all_samples[split_line1:split_line2]], axis=0) for i in range(2)]
    testing_set = [np.concatenate([sample[i] for sample in all_samples[split_line2:]], axis=0) for i in range(2)]
    
    train_x, train_target = training_set
    val_x, val_target = validation_set
    test_x, test_target = testing_set
    
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
    data_file = '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/processed/gapyeong_drt_data.npz'
    
    print("Generating MST-GCN dataset...")
    dataset = read_and_generate_dataset(
        data_file,
        num_of_weeks=1,
        num_of_days=1, 
        num_of_hours=3,
        num_for_predict=1,
        points_per_hour=1,
        save=True
    )
    
    print("\\nDataset preprocessing completed!")
    print("Files created:")
    print("- gapyeong_drt_data_r3_d1_w1_mstgcn.npz")


if __name__ == "__main__":
    main()