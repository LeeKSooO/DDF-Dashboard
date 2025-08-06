-- ===============================================
-- database/init/03-prediction-schema.sql (예측 & 모델 관리용)
-- ===============================================

-- 모델 메타데이터 (먼저 생성 - 다른 테이블에서 참조함)
CREATE TABLE model_metadata (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) DEFAULT 'MSTGCN',
    
    -- 학습 정보
    training_start TIMESTAMP,
    training_end TIMESTAMP,
    training_data_start TIMESTAMP, -- 학습 데이터 시작 시점
    training_data_end TIMESTAMP, -- 학습 데이터 종료 시점
    
    -- 모델 성능 메트릭
    metrics JSONB, -- {
                   --   "rmse": 0.123,
                   --   "mae": 0.089,
                   --   "mape": 12.5,
                   --   "r2": 0.85,
                   --   "validation_loss": 0.045
                   -- }
    
    -- 하이퍼파라미터
    hyperparameters JSONB, -- {
                          --   "K": 3,
                          --   "nb_block": 2,
                          --   "nb_chev_filter": 64,
                          --   "nb_time_filter": 64,
                          --   "time_strides": 1,
                          --   "len_input": 12,
                          --   "num_for_predict": 3,
                          --   "learning_rate": 0.001,
                          --   "batch_size": 32,
                          --   "epochs": 50
                          -- }
    
    -- 모델 구조 정보
    model_architecture JSONB, -- {
                             --   "num_of_vertices": 848,
                             --   "in_channels": 2,
                             --   "features": ["boarding_count", "drt_probability"]
                             -- }
    
    -- 정규화 통계
    normalization_stats JSONB, -- {
                              --   "mean": 0.1110,
                              --   "std": 1.1544,
                              --   "method": "z-score"
                              -- }
    
    -- 파일 경로
    model_path VARCHAR(500) NOT NULL, -- 실제 .pth 파일 경로
    stats_path VARCHAR(500), -- stats.npz 파일 경로
    graph_path VARCHAR(500), -- 그래프 데이터 경로
    
    -- 상태 관리
    is_active BOOLEAN DEFAULT false, -- 현재 서빙 중인 모델
    is_validated BOOLEAN DEFAULT false, -- 검증 완료 여부
    deployment_status VARCHAR(50) DEFAULT 'inactive', -- inactive, deploying, active, deprecated
    
    -- 추가 정보
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(model_name, model_version)
);

-- 예측 결과 저장 테이블
CREATE TABLE predictions (
    prediction_id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL, -- 동일 요청에 대한 여러 정류장 예측 그룹화
    stop_id VARCHAR(50) REFERENCES bus_stops(stop_id),
    route_id VARCHAR(50) REFERENCES bus_routes(route_id),
    
    -- 시간 정보
    prediction_time TIMESTAMP NOT NULL, -- 예측 수행 시점
    target_time TIMESTAMP NOT NULL, -- 예측 대상 시점
    prediction_horizon INTEGER NOT NULL, -- 예측 시간 범위 (1, 2, 3 시간 후)
    
    -- 예측 결과
    drt_probability DECIMAL(10, 4) NOT NULL, -- DRT 잠재수요 확률
    predicted_boarding_count DECIMAL(10, 2), -- 예측 승차 인원
    predicted_alighting_count DECIMAL(10, 2), -- 예측 하차 인원
    
    -- 모델 정보
    model_id INTEGER REFERENCES model_metadata(model_id),
    model_version VARCHAR(50) NOT NULL,
    
    -- 추가 메타데이터
    input_features JSONB, -- 입력으로 사용된 feature 정보
    confidence_interval JSONB, -- {"lower": 0.15, "upper": 0.25}
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 예측 결과 인덱스
CREATE INDEX idx_predictions_request ON predictions (request_id);
CREATE INDEX idx_predictions_stop_target ON predictions (stop_id, target_time);
CREATE INDEX idx_predictions_created ON predictions (created_at DESC);
CREATE INDEX idx_predictions_model ON predictions (model_id);

-- 모델 배포 이력
CREATE TABLE model_deployment_history (
    deployment_id SERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES model_metadata(model_id),
    action VARCHAR(50) NOT NULL, -- deploy, rollback, deactivate
    previous_model_id INTEGER REFERENCES model_metadata(model_id),
    deployment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_by VARCHAR(100),
    notes TEXT
);

-- 예측 요청 로그 (성능 모니터링용)
CREATE TABLE prediction_requests (
    request_id UUID PRIMARY KEY,
    target_datetime TIMESTAMP NOT NULL,
    requested_stops INTEGER NOT NULL, -- 요청된 정류장 수
    model_id INTEGER REFERENCES model_metadata(model_id),
    
    -- 성능 메트릭
    preprocessing_time_ms INTEGER, -- 전처리 소요 시간
    inference_time_ms INTEGER, -- 추론 소요 시간
    total_time_ms INTEGER, -- 전체 소요 시간
    
    -- 요청 정보
    request_source VARCHAR(50), -- web, api, batch
    user_ip VARCHAR(45),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 모델 성능 모니터링 (실시간 성능 추적)
CREATE TABLE model_performance_monitoring (
    monitoring_id SERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES model_metadata(model_id),
    monitoring_date DATE NOT NULL,
    
    -- 일별 집계 메트릭
    total_predictions INTEGER DEFAULT 0,
    avg_inference_time_ms DECIMAL(10, 2),
    max_inference_time_ms INTEGER,
    min_inference_time_ms INTEGER,
    
    -- 실제 vs 예측 비교 (ground truth 확보 시)
    actual_vs_predicted JSONB, -- 정류장별 실제값과 예측값 비교
    daily_rmse DECIMAL(10, 4),
    daily_mae DECIMAL(10, 4),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, monitoring_date)
);

-- 인덱스 추가
CREATE INDEX idx_model_metadata_active ON model_metadata (is_active) WHERE is_active = true;
CREATE INDEX idx_model_deployment_history_time ON model_deployment_history (deployment_time DESC);
CREATE INDEX idx_prediction_requests_time ON prediction_requests (created_at DESC);
CREATE INDEX idx_model_performance_date ON model_performance_monitoring (monitoring_date DESC);