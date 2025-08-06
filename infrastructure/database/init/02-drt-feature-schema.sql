-- ===============================================
-- database/init/03-drt-feature-schema-mstgcn.sql 
-- DRT 수요응답형 버스 Feature 테이블 (MST-GCN 최적화)
-- ===============================================

-- 1. MST-GCN용 실시간 Feature 테이블 (핵심)
DROP TABLE IF EXISTS drt_features_mstgcn CASCADE;
CREATE TABLE drt_features_mstgcn (
    feature_id BIGSERIAL,
    stop_id VARCHAR(50), -- 외래키 제약은 hypertable 생성 후 추가
    recorded_at TIMESTAMP NOT NULL,

    -- MST-GCN 입력 피처 (4개 MVP 최적화)
    -- 1. 수요 관련 피처 (2개)
    normalized_log_boarding_count DECIMAL(8,4) NOT NULL DEFAULT 0, -- Log+Z-score: (LN(boarding_count+1) - μ_log) / σ_log
    service_availability INTEGER NOT NULL DEFAULT 0, -- 0=비운행, 1=운행날+시간외, 2=운행날+시간내
    
    -- 2. 시간적 컨텍스트 피처 (1개)
    is_rest_day BOOLEAN NOT NULL, -- 주말+공휴일 통합 (도메인 특화 패턴)
    
    -- 3. 공간적/서비스 피처 (1개)
    normalized_interval DECIMAL(8,4) NOT NULL, -- Log+Z-score 정규화: (LN(interval) - μ_log) / σ_log
    
    -- 향후 확장용 피처 (POI 데이터 수집 후 활성화)
    -- poi_density_score DECIMAL(8,4) DEFAULT 0, -- POI 밀도 점수 [향후 추가]
    
    -- 메타데이터 (피처 생성용)
    hour_of_day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL, -- 0=일요일, 6=토요일
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT false,
    is_in_service_hours BOOLEAN NOT NULL,
    applicable_interval INTEGER NOT NULL, -- 원본 배차간격(분)
    route_count INTEGER DEFAULT 1, -- 경유 노선 수
    
    -- 정답 라벨 (예측 타겟)
    drt_probability DECIMAL(8,4) NOT NULL DEFAULT 0, -- 0~1 DRT 수요 확률
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (feature_id, recorded_at),
    UNIQUE(stop_id, recorded_at)
);

-- 2. 정류장별 정적 메타데이터 (MST-GCN 인접행렬 생성용)
DROP TABLE IF EXISTS stop_spatial_features CASCADE;
CREATE TABLE stop_spatial_features (
    stop_id VARCHAR(50) PRIMARY KEY REFERENCES bus_stops(stop_id),
    
    -- 공간 정보 (인접행렬 계산용)
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    district VARCHAR(50) DEFAULT '가평군',
    
    -- 교통 네트워크 특성
    total_routes INTEGER DEFAULT 1, -- 총 경유 노선 수
    avg_interval_minutes INTEGER DEFAULT 319, -- 평균 배차간격
    accessibility_level VARCHAR(20) DEFAULT 'Poor', -- Very_Poor, Poor, Fair, Good
    
    -- DRT 잠재성 분류 (High, Medium, Low, None)
    drt_potential_level VARCHAR(30) DEFAULT 'Low_DRT_Potential',
    isolation_score DECIMAL(5,3) DEFAULT 0.5, -- 교통 격리도 (0~1)
    
    -- 히스토리컬 통계 (DRT 확률 계산 기준값)
    avg_daily_boarding DECIMAL(10, 2) DEFAULT 0,
    peak_demand_ratio DECIMAL(5,3) DEFAULT 1.0, -- 피크/평균 비율
    zero_demand_rate DECIMAL(5,3) DEFAULT 0.9, -- 무수요시간 비율
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. DRT 확률 계산 룩업 테이블 (성능 최적화용)
DROP TABLE IF EXISTS drt_probability_lookup CASCADE;
CREATE TABLE drt_probability_lookup (
    lookup_id SERIAL PRIMARY KEY,
    
    -- 확률 계산 기준
    interval_range VARCHAR(20) NOT NULL, -- 'very_long', 'long', 'medium', 'short'
    demand_level VARCHAR(20) NOT NULL, -- 'zero', 'low', 'medium', 'high'
    time_category VARCHAR(20) NOT NULL, -- 'peak', 'off_peak', 'night'
    is_weekend BOOLEAN NOT NULL,
    
    -- 결과 확률
    base_drt_probability DECIMAL(5,3) NOT NULL, -- 기본 DRT 확률
    
    -- 범위 정의
    min_interval INTEGER, -- 최소 배차간격(분)
    max_interval INTEGER, -- 최대 배차간격(분)
    min_demand INTEGER, -- 최소 수요
    max_demand INTEGER, -- 최대 수요
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(interval_range, demand_level, time_category, is_weekend)
);

-- 4. MST-GCN 인접행렬 캐시 (추론 성능 최적화)
DROP TABLE IF EXISTS adjacency_matrix_cache CASCADE;
CREATE TABLE adjacency_matrix_cache (
    cache_id SERIAL PRIMARY KEY,
    
    -- 행렬 설정
    distance_threshold_m INTEGER NOT NULL, -- 거리 임계값 (미터)
    matrix_size INTEGER NOT NULL, -- N x N 크기
    
    -- 직렬화된 인접행렬 데이터
    adjacency_data BYTEA NOT NULL, -- numpy 배열을 압축 저장
    stop_order JSONB NOT NULL, -- 정류장 ID 순서 정보
    
    -- 메타데이터
    total_edges INTEGER, -- 총 엣지 수
    avg_degree DECIMAL(5,2), -- 평균 차수
    is_connected BOOLEAN, -- 연결성 여부
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(distance_threshold_m)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('drt_features_mstgcn', 'recorded_at', if_not_exists => TRUE);

-- 외래키 제약 조건 추가 (hypertable 생성 후)
-- 주의: bus_stops 테이블이 존재하는 경우에만 활성화
-- ALTER TABLE drt_features_mstgcn ADD CONSTRAINT fk_drt_features_stop_id FOREIGN KEY (stop_id) REFERENCES bus_stops(stop_id);

-- 인덱스 생성 (MST-GCN 시계열 조회 최적화) - 하이퍼테이블 생성 후 실행
CREATE INDEX idx_drt_features_mstgcn_time_desc ON drt_features_mstgcn (recorded_at DESC);
CREATE INDEX idx_drt_features_mstgcn_stop_time ON drt_features_mstgcn (stop_id, recorded_at DESC);
CREATE INDEX idx_drt_features_mstgcn_hour ON drt_features_mstgcn (hour_of_day);
CREATE INDEX idx_drt_features_mstgcn_service_hours ON drt_features_mstgcn (is_in_service_hours, service_availability);

-- 공간 인덱스 (인접행렬 계산 최적화) - 위치 기반 조회용
CREATE INDEX idx_stop_spatial_lat_lng ON stop_spatial_features (latitude, longitude);

-- 압축 정책 (90일 후 압축) - 초기 단계에서는 비활성화
-- ALTER TABLE drt_features_mstgcn SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'stop_id'
-- );
-- SELECT add_compression_policy('drt_features_mstgcn', INTERVAL '90 days', if_not_exists => TRUE);


-- ===============================================================================
-- DRT 확률 계산 공식 정의 (0~1 연속값)
-- ===============================================================================

-- DRT 확률 계산 함수 (Log+Z-score 기반 연속값)
-- 정답 라벨 규칙 함수
CREATE OR REPLACE FUNCTION calculate_drt_probability(
    boarding_count INTEGER,
    applicable_interval INTEGER,
    hour_of_day INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    service_availability INTEGER
)
RETURNS DECIMAL(8,4) AS $$
DECLARE
    base_prob DECIMAL(8,4);
    interval_factor DECIMAL(8,4);
    demand_factor DECIMAL(8,4);
    time_factor DECIMAL(8,4);
    rest_day_factor DECIMAL(8,4);
    final_prob DECIMAL(8,4);
    log_boarding DECIMAL(8,4);
    norm_log_boarding DECIMAL(8,4);
    norm_interval DECIMAL(8,4);
BEGIN
    -- 1. Log+Z-score 정규화된 수요 팩터 (연속값)
    log_boarding := LN(boarding_count + 1);
    norm_log_boarding := (log_boarding - 0.153) / 0.456;  -- 실제 데이터 기반 μ, σ
    
    -- 수요가 많을수록 DRT 필요도 감소 (역함수 적용)
    demand_factor := GREATEST(0.05, 1.0 - (norm_log_boarding + 0.3355) / 10.691);  -- [0.05, 1.0] 범위
    
    -- 2. Log+Z-score 정규화된 배차간격 팩터
    norm_interval := (LN(applicable_interval) - 4.9986) / 0.7142;  -- Log+Z-score 정규화
    interval_factor := 0.05 + (1 / (1 + EXP(-norm_interval))) * 0.90;  -- Sigmoid [0.05, 0.95] 범위
    
    -- 3. 서비스 가용성별 보정
    CASE service_availability
        WHEN 0 THEN  -- 비운행날
            interval_factor := interval_factor * 1.5;
        WHEN 1 THEN  -- 운행날+시간외
            interval_factor := interval_factor * 1.2;
        WHEN 2 THEN  -- 운행날+시간내
            -- 기본값 유지
            NULL;
        ELSE
            NULL;
    END CASE;
    
    -- 4. 시간대 보정 (연속값)
    time_factor := CASE
        WHEN hour_of_day BETWEEN 7 AND 9 OR hour_of_day BETWEEN 17 AND 19 THEN 1.0
        WHEN hour_of_day BETWEEN 10 AND 16 THEN 0.8
        WHEN hour_of_day BETWEEN 20 AND 22 THEN 0.6
        ELSE 0.4
    END;
    
    -- 5. 휴일 보정
    rest_day_factor := CASE
        WHEN is_weekend OR is_holiday THEN 1.2
        ELSE 1.0
    END;
    
    -- 최종 확률 계산 (개선된 가중평균)
    base_prob := interval_factor * 0.5 + demand_factor * 0.3 + time_factor * 0.2;
    final_prob := base_prob * rest_day_factor;
    
    -- 0~1 범위로 클리핑
    final_prob := GREATEST(0.0, LEAST(1.0, final_prob));
    
    RETURN final_prob;
END;
$$ LANGUAGE plpgsql;

-- 룩업 테이블을 단순화 (참고용으로만 사용)
INSERT INTO drt_probability_lookup (interval_range, demand_level, time_category, is_weekend, base_drt_probability, min_interval, max_interval, min_demand, max_demand) VALUES
-- 참고용 기준값들 (실제로는 위 함수 사용)
('very_long', 'zero', 'peak', false, 0.90, 300, 999, 0, 0),
('long', 'zero', 'peak', false, 0.70, 120, 299, 0, 0),
('medium', 'zero', 'peak', false, 0.50, 60, 119, 0, 0),
('short', 'zero', 'peak', false, 0.30, 0, 59, 0, 0),
('very_long', 'low', 'peak', false, 0.72, 300, 999, 1, 2),
('long', 'low', 'peak', false, 0.56, 120, 299, 1, 2),
('medium', 'low', 'peak', false, 0.40, 60, 119, 1, 2),
('short', 'low', 'peak', false, 0.24, 0, 59, 1, 2);

-- =================================
-- MST-GCN 시계열 조회 최적화 함수
-- =================================

-- MST-GCN 다중 스케일 시계열 데이터 조회 함수 (4개 입력 피처 MVP)
CREATE OR REPLACE FUNCTION get_mstgcn_features(
    target_time TIMESTAMP,
    hour_window INTEGER DEFAULT 6,
    day_window INTEGER DEFAULT 24,
    week_window INTEGER DEFAULT 24
) 
RETURNS TABLE (
    scale_type TEXT,
    stop_id TEXT,
    time_sequence TIMESTAMP[],
    -- 4개 입력 피처 시퀀스 (MVP 최적화)
    normalized_log_boarding_count_sequence DECIMAL[],
    service_availability_sequence INTEGER[],
    is_rest_day_sequence BOOLEAN[],
    normalized_interval_sequence DECIMAL[]
) AS $$
BEGIN
    -- Hour scale (최근 6시간)
    RETURN QUERY
    SELECT 
        'hour'::TEXT as scale_type,
        f.stop_id::TEXT,
        array_agg(f.recorded_at ORDER BY f.recorded_at) as time_sequence,
        array_agg(f.normalized_log_boarding_count ORDER BY f.recorded_at) as normalized_log_boarding_count_sequence,
        array_agg(f.service_availability ORDER BY f.recorded_at) as service_availability_sequence,
        array_agg(f.is_rest_day ORDER BY f.recorded_at) as is_rest_day_sequence,
        array_agg(f.normalized_interval ORDER BY f.recorded_at) as normalized_interval_sequence
        -- array_agg(f.poi_density_score ORDER BY f.recorded_at) as poi_density_score_sequence  -- 향후 추가
    FROM drt_features_mstgcn f
    WHERE f.recorded_at >= target_time - interval '1 hour' * hour_window
      AND f.recorded_at < target_time
    GROUP BY f.stop_id;
    
    -- Day scale (과거 24시간)
    RETURN QUERY
    SELECT 
        'day'::TEXT as scale_type,
        f.stop_id::TEXT,
        array_agg(f.recorded_at ORDER BY f.recorded_at) as time_sequence,
        array_agg(f.normalized_log_boarding_count ORDER BY f.recorded_at) as normalized_log_boarding_count_sequence,
        array_agg(f.service_availability ORDER BY f.recorded_at) as service_availability_sequence,
        array_agg(f.is_rest_day ORDER BY f.recorded_at) as is_rest_day_sequence,
        array_agg(f.normalized_interval ORDER BY f.recorded_at) as normalized_interval_sequence
        -- array_agg(f.poi_density_score ORDER BY f.recorded_at) as poi_density_score_sequence  -- 향후 추가
    FROM drt_features_mstgcn f
    WHERE f.recorded_at >= target_time - interval '1 hour' * day_window
      AND f.recorded_at < target_time
    GROUP BY f.stop_id;
    
    -- Week scale (1주일 전 24시간)
    RETURN QUERY
    SELECT 
        'week'::TEXT as scale_type,
        f.stop_id::TEXT,
        array_agg(f.recorded_at ORDER BY f.recorded_at) as time_sequence,
        array_agg(f.normalized_log_boarding_count ORDER BY f.recorded_at) as normalized_log_boarding_count_sequence,
        array_agg(f.service_availability ORDER BY f.recorded_at) as service_availability_sequence,
        array_agg(f.is_rest_day ORDER BY f.recorded_at) as is_rest_day_sequence,
        array_agg(f.normalized_interval ORDER BY f.recorded_at) as normalized_interval_sequence
        -- array_agg(f.poi_density_score ORDER BY f.recorded_at) as poi_density_score_sequence  -- 향후 추가
    FROM drt_features_mstgcn f
    WHERE f.recorded_at >= target_time - interval '7 days' - interval '1 hour' * week_window
      AND f.recorded_at < target_time - interval '7 days'
    GROUP BY f.stop_id;
END;
$$ LANGUAGE plpgsql;

-- 추가: DRT 예측 타겟 라벨 조회 함수 (학습용)
CREATE OR REPLACE FUNCTION get_mstgcn_targets(
    target_time TIMESTAMP,
    prediction_window INTEGER DEFAULT 24
) 
RETURNS TABLE (
    stop_id TEXT,
    time_sequence TIMESTAMP[],
    drt_probability_sequence DECIMAL[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        f.stop_id::TEXT,
        array_agg(f.recorded_at ORDER BY f.recorded_at) as time_sequence,
        array_agg(f.drt_probability ORDER BY f.recorded_at) as drt_probability_sequence
    FROM drt_features_mstgcn f
    WHERE f.recorded_at >= target_time
      AND f.recorded_at < target_time + interval '1 hour' * prediction_window
    GROUP BY f.stop_id;
END;
$$ LANGUAGE plpgsql;