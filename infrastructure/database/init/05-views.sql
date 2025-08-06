-- ===============================================
-- database/init/05-views.sql (뷰 & 함수)
-- ===============================================

-- View: 정류장별 최근 7일 평균 이용량
CREATE MATERIALIZED VIEW mv_stop_weekly_avg AS
SELECT 
    s.stop_id,
    s.stop_name,
    AVG(su.boarding_count) as avg_boarding,
    AVG(su.alighting_count) as avg_alighting,
    COUNT(DISTINCT DATE(su.recorded_at)) as days_with_data
FROM bus_stops s
LEFT JOIN stop_usage su ON s.stop_id = su.stop_id
WHERE su.recorded_at >= CURRENT_DATE - INTERVAL '7 days'
    AND su.is_operational = true
GROUP BY s.stop_id, s.stop_name;

-- Materialized View 인덱스
CREATE UNIQUE INDEX idx_mv_stop_weekly_avg ON mv_stop_weekly_avg (stop_id);

-- MST-GCN 학습용 뷰 (drt_features_mstgcn 테이블 기반)
CREATE OR REPLACE VIEW mst_gcn_training_data AS
SELECT 
    df.stop_id,
    bs.stop_name,
    bs.latitude,
    bs.longitude,
    df.recorded_at,
    df.hour_of_day,
    df.day_of_week,
    df.is_weekend,
    df.drt_probability as target_value,
    df.normalized_log_boarding_count,
    df.applicable_interval,
    
    -- 시간 순환 특성
    SIN(2 * PI() * df.hour_of_day / 24.0) as hour_sin,
    COS(2 * PI() * df.hour_of_day / 24.0) as hour_cos,
    SIN(2 * PI() * df.day_of_week / 7.0) as day_sin,
    COS(2 * PI() * df.day_of_week / 7.0) as day_cos
    
FROM drt_features_mstgcn df
JOIN bus_stops bs ON df.stop_id = bs.stop_id
WHERE bs.latitude IS NOT NULL 
  AND bs.longitude IS NOT NULL
ORDER BY df.stop_id, df.recorded_at;

-- 함수: 두 지점 간 거리 계산 (미터 단위)
CREATE OR REPLACE FUNCTION calculate_distance(
    lat1 DECIMAL, lon1 DECIMAL,
    lat2 DECIMAL, lon2 DECIMAL
) RETURNS DECIMAL AS $$
BEGIN
    RETURN ST_Distance(
        ST_MakePoint(lon1, lat1)::geography,
        ST_MakePoint(lon2, lat2)::geography
    );
END;
$$ LANGUAGE plpgsql;