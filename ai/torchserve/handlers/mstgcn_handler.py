import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import logging
import os
from typing import List, Dict
from scipy.sparse.linalg import eigs

logger = logging.getLogger(__name__)

# =================================================================================
# 1. 모델 아키텍처 정의
# =================================================================================

class cheb_conv(nn.Module):
    def __init__(self, K, cheb_polynomials, in_channels, out_channels):
        super(cheb_conv, self).__init__()
        self.K = K
        self.cheb_polynomials = cheb_polynomials
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.DEVICE = cheb_polynomials[0].device
        self.Theta = nn.ParameterList([
            nn.Parameter(torch.FloatTensor(in_channels, out_channels))
            for _ in range(K)
        ])
    
    def forward(self, x):
        batch_size, num_of_vertices, in_channels, num_of_timesteps = x.shape
        outputs = []
        for time_step in range(num_of_timesteps):
            graph_signal = x[:, :, :, time_step]
            output = torch.zeros(batch_size, num_of_vertices, self.out_channels).to(self.DEVICE)
            for k in range(self.K):
                T_k = self.cheb_polynomials[k]
                theta_k = self.Theta[k]
                rhs = torch.matmul(T_k, graph_signal)
                output = output + torch.matmul(rhs, theta_k)
            outputs.append(output.unsqueeze(-1))
        return F.relu(torch.cat(outputs, dim=-1))

class MSTGCN_block(nn.Module):
    def __init__(self, DEVICE, in_channels, K, nb_chev_filter, nb_time_filter, time_conv_strides, cheb_polynomials):
        super(MSTGCN_block, self).__init__()
        self.cheb_conv = cheb_conv(K, cheb_polynomials, in_channels, nb_chev_filter)
        self.time_conv = nn.Conv2d(nb_chev_filter, nb_time_filter, kernel_size=(1, 3), stride=(1, time_conv_strides), padding=(0, 1))
        self.residual_conv = nn.Conv2d(in_channels, nb_time_filter, kernel_size=(1, 1), stride=(1, time_conv_strides))
        self.ln = nn.LayerNorm(nb_time_filter)
    
    def forward(self, x):
        spatial_gcn = self.cheb_conv(x)
        time_conv_output = self.time_conv(spatial_gcn.permute(0, 2, 1, 3)).permute(0, 2, 1, 3)
        x_residual = self.residual_conv(x.permute(0, 2, 1, 3)).permute(0, 2, 1, 3)
        out = F.relu(x_residual + time_conv_output)
        out = self.ln(out.permute(0, 1, 3, 2)).permute(0, 1, 3, 2)
        return out

class MSTGCN_submodule(nn.Module):
    def __init__(self, DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials, num_for_predict, len_input, num_of_vertices):
        super(MSTGCN_submodule, self).__init__()
        self.BlockList = nn.ModuleList([MSTGCN_block(DEVICE, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials)])
        for _ in range(nb_block - 1):
            self.BlockList.append(MSTGCN_block(DEVICE, nb_time_filter, K, nb_chev_filter, nb_time_filter, 1, cheb_polynomials))
        self.final_conv = nn.Conv2d(int(len_input / time_strides), num_for_predict, kernel_size=(1, nb_time_filter))
        self.W = nn.Parameter(torch.FloatTensor(num_of_vertices, num_for_predict))
    
    def forward(self, x):
        for block in self.BlockList:
            x = block(x)
        output = self.final_conv(x.permute(0, 3, 1, 2))[:, :, :, 0].permute(0, 2, 1)
        return output * self.W

class MSTGCN(nn.Module):
    def __init__(self, DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials, num_for_predict, num_of_vertices, len_hour, len_day, len_week):
        super(MSTGCN, self).__init__()
        self.hour_module = MSTGCN_submodule(DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials, num_for_predict, len_hour, num_of_vertices)
        self.day_module = MSTGCN_submodule(DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials, num_for_predict, len_day, num_of_vertices)
        self.week_module = MSTGCN_submodule(DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter, time_strides, cheb_polynomials, num_for_predict, len_week, num_of_vertices)
    
    def forward(self, x_hour, x_day, x_week):
        hour_output = self.hour_module(x_hour)
        day_output = self.day_module(x_day)
        week_output = self.week_module(x_week)
        return hour_output + day_output + week_output

# =================================================================================
# 2. 그래프 유틸리티 함수
# =================================================================================

def scaled_laplacian_scipy(W):
    """학습 때와 동일한, 효율적인 scipy 버전으로 변경"""
    assert W.shape[0] == W.shape[1]
    # [수정] 데이터 타입을 명시적으로 float64로 변환
    W = W.astype(np.float64)
    D = np.diag(np.sum(W, axis=1))
    L = D - W
    lambda_max = eigs(L, k=1, which='LR')[0].real
    return (2 * L) / lambda_max - np.identity(W.shape[0])

def cheb_polynomial_torch(L_tilde, K):
    N = L_tilde.shape[0]
    cheb_polynomials = [torch.eye(N), L_tilde.clone()]
    for i in range(2, K):
        cheb_polynomials.append(2 * torch.matmul(L_tilde, cheb_polynomials[i-1]) - cheb_polynomials[i-2])
    return cheb_polynomials

# =================================================================================
# 3. 글로벌 변수 및 초기화
# =================================================================================

_model = None
_device = None
_stats = None
_initialized = False

def initialize(context):
    """TorchServe 초기화"""
    global _model, _device, _stats, _initialized
    
    if _initialized:
        return
    
    properties = context.system_properties
    _device = torch.device("cuda" if torch.cuda.is_available() and properties.get("gpu_id") is not None else "cpu")
    model_dir = properties.get("model_dir")
    
    # 모델 파라미터
    model_params = {
        'K': 3, 'nb_block': 2, 'in_channels': 4, 'nb_chev_filter': 64,
        'nb_time_filter': 64, 'time_strides': 1, 'num_for_predict': 24,
        'len_hour': 6, 'len_day': 24, 'len_week': 24
    }
    
    # 정규화 통계 로드
    stats_path = os.path.join(model_dir, "stats.npz")
    stats_data = np.load(stats_path)
    _stats = {key: torch.from_numpy(stats_data[key]).float().to(_device) for key in stats_data.files}
    
    # 인접 행렬 로드 및 체비셰프 다항식 계산
    adj_mx_path = os.path.join(model_dir, "adj_mx.npy")
    adj_mx = np.load(adj_mx_path)
    model_params['num_of_vertices'] = adj_mx.shape[0]
    
    L_tilde = scaled_laplacian_scipy(adj_mx)
    cheb_polynomials = cheb_polynomial_torch(torch.from_numpy(L_tilde).float().to(_device), model_params['K'])
    
    # 모델 생성 및 로드
    _model = MSTGCN(DEVICE=_device, cheb_polynomials=cheb_polynomials, **model_params)
    model_pt_path = os.path.join(model_dir, "mstgcn_model_v1.pt")
    _model.load_state_dict(torch.load(model_pt_path, map_location=_device))
    _model.to(_device)
    _model.eval()
    
    _initialized = True
    logger.info("MST-GCN model initialized successfully")

def preprocess(data):
    """전처리"""
    if not data or not data[0]:
        # TorchServe 초기화 시 빈 데이터 처리
        return None
    req = data[0].get("body") or data[0]
    hour_data = torch.tensor(req.get("hour_data"), dtype=torch.float32)
    day_data = torch.tensor(req.get("day_data"), dtype=torch.float32)
    week_data = torch.tensor(req.get("week_data"), dtype=torch.float32)
    
    # 데이터 정규화
    hour_data = hour_data.permute(2, 0, 1, 3)
    day_data = day_data.permute(2, 0, 1, 3)
    week_data = week_data.permute(2, 0, 1, 3)
    
    hour_data = (hour_data - _stats['hour_mean'][:, None, None, None]) / _stats['hour_std'][:, None, None, None]
    day_data = (day_data - _stats['day_mean'][:, None, None, None]) / _stats['day_std'][:, None, None, None]
    week_data = (week_data - _stats['week_mean'][:, None, None, None]) / _stats['week_std'][:, None, None, None]
    
    hour_data = hour_data.permute(1, 2, 0, 3).to(_device)
    day_data = day_data.permute(1, 2, 0, 3).to(_device)
    week_data = week_data.permute(1, 2, 0, 3).to(_device)
    
    return {"hour": hour_data, "day": day_data, "week": week_data}

def inference(data):
    """추론"""
    if data is None:
        # 초기화 시에는 더미 출력 반환
        return torch.zeros((1, 24, 1))
    with torch.no_grad():
        output = _model(data["hour"], data["day"], data["week"])
    return output

def postprocess(data):
    """후처리"""
    if data is None or data.numel() == 0:
        return [{"predictions": []}]
    predictions = data.permute(0, 2, 1).cpu().numpy().tolist()
    return [{"predictions": predictions}]

# =================================================================================
# 4. TorchServe 핸들러 엔트리 포인트
# =================================================================================

def handle(data, context):
    """TorchServe 핸들러 엔트리 포인트"""
    if not _initialized:
        initialize(context)
    
    processed_data = preprocess(data)
    predictions = inference(processed_data)
    return postprocess(predictions)