-- ==============================================
-- Materialized Views for DRT System Performance Optimization
-- 대용량 교통 데이터 집계 테이블 (사전 계산된 집계)
-- ==============================================

-- 1. 일별 교통량 집계 (가장 자주 사용되는 집계)
CREATE MATERIALIZED VIEW mv_daily_traffic_summary AS
SELECT
    record_date,
    COUNT(*) as total_records,
    SUM(ride_passenger) as total_boarding,
    SUM(alight_passenger) as total_alighting,
    SUM(ride_passenger + alight_passenger) as total_traffic,
    AVG(ride_passenger) as avg_boarding,
    AVG(alight_passenger) as avg_alighting,
    MAX(ride_passenger) as max_boarding,
    MAX(alight_passenger) as max_alighting,
    COUNT(DISTINCT node_id) as active_stations,
    COUNT(DISTINCT route_id) as active_routes
FROM station_passenger_history
GROUP BY record_date
ORDER BY record_date;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_daily_traffic_date ON mv_daily_traffic_summary(record_date);

-- 2. 일별 + 시간대별 교통량 집계 (시간대별 패턴 분석용)
CREATE MATERIALIZED VIEW mv_daily_hourly_traffic AS
SELECT
    record_date,
    hour,
    SUM(ride_passenger) as total_boarding,
    SUM(alight_passenger) as total_alighting,
    SUM(ride_passenger + alight_passenger) as total_traffic,
    AVG(ride_passenger) as avg_boarding,
    AVG(alight_passenger) as avg_alighting,
    COUNT(DISTINCT node_id) as active_stations,
    COUNT(DISTINCT route_id) as active_routes
FROM station_passenger_history
GROUP BY record_date, hour
ORDER BY record_date, hour;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_daily_hourly_date_hour ON mv_daily_hourly_traffic(record_date, hour);
CREATE INDEX idx_mv_daily_hourly_date ON mv_daily_hourly_traffic(record_date);
CREATE INDEX idx_mv_daily_hourly_hour ON mv_daily_hourly_traffic(hour);

-- 3. 일별 + 지역별(구별) 교통량 집계 (지역별 분석용)
CREATE MATERIALIZED VIEW mv_daily_district_traffic AS
SELECT
    sph.record_date,
    sm.sgg_name as district_name,
    SUM(sph.ride_passenger) as total_boarding,
    SUM(sph.alight_passenger) as total_alighting,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    AVG(sph.ride_passenger) as avg_boarding,
    AVG(sph.alight_passenger) as avg_alighting,
    COUNT(DISTINCT sph.node_id) as active_stations,
    COUNT(DISTINCT sph.route_id) as active_routes
FROM station_passenger_history sph
JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sm.is_seoul = true
GROUP BY sph.record_date, sm.sgg_name
ORDER BY sph.record_date, sm.sgg_name;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_daily_district_date_district ON mv_daily_district_traffic(record_date, district_name);
CREATE INDEX idx_mv_daily_district_date ON mv_daily_district_traffic(record_date);
CREATE INDEX idx_mv_daily_district_name ON mv_daily_district_traffic(district_name);

-- 4. 주요 정류장별 일별 집계 (TOP 정류장 성능 분석용)
CREATE MATERIALIZED VIEW mv_daily_station_traffic AS
SELECT
    sph.record_date,
    sph.node_id,
    sph.station_name,
    sm.sgg_name as district_name,
    SUM(sph.ride_passenger) as total_boarding,
    SUM(sph.alight_passenger) as total_alighting,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    COUNT(DISTINCT sph.route_id) as route_count
FROM station_passenger_history sph
LEFT JOIN spatial_mapping sm ON sph.node_id = sm.node_id
GROUP BY sph.record_date, sph.node_id, sph.station_name, sm.sgg_name
HAVING SUM(sph.ride_passenger + sph.alight_passenger) > 100 -- 일일 100명 이상만 포함
ORDER BY sph.record_date, total_traffic DESC;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_daily_station_date_node ON mv_daily_station_traffic(record_date, node_id);
CREATE INDEX idx_mv_daily_station_date ON mv_daily_station_traffic(record_date);
CREATE INDEX idx_mv_daily_station_traffic_desc ON mv_daily_station_traffic(record_date, total_traffic DESC);
CREATE INDEX idx_mv_daily_station_district ON mv_daily_station_traffic(district_name);

-- 5. 전체 기간 요약 통계 (빠른 전체 조회용)
CREATE MATERIALIZED VIEW mv_period_summary AS
SELECT
    MIN(record_date) as period_start,
    MAX(record_date) as period_end,
    COUNT(DISTINCT record_date) as total_days,
    SUM(total_boarding) as total_boarding,
    SUM(total_alighting) as total_alighting,
    SUM(total_traffic) as total_traffic,
    AVG(total_traffic) as avg_daily_traffic,
    MAX(total_traffic) as max_daily_traffic,
    MIN(total_traffic) as min_daily_traffic,
    SUM(active_stations) / COUNT(*) as avg_active_stations,
    SUM(active_routes) / COUNT(*) as avg_active_routes
FROM mv_daily_traffic_summary;

-- 6. 시간대별 전체 집계 (피크 시간 분석용)
CREATE MATERIALIZED VIEW mv_hourly_pattern AS
SELECT
    hour,
    SUM(total_boarding) as total_boarding,
    SUM(total_alighting) as total_alighting,
    SUM(total_traffic) as total_traffic,
    AVG(total_traffic) as avg_traffic,
    COUNT(*) as data_points
FROM mv_daily_hourly_traffic
GROUP BY hour
ORDER BY hour;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_hourly_pattern_hour ON mv_hourly_pattern(hour);

-- 7. 구별 전체 집계 (지역별 순위용)
CREATE MATERIALIZED VIEW mv_district_ranking AS
SELECT
    district_name,
    SUM(total_boarding) as total_boarding,
    SUM(total_alighting) as total_alighting,
    SUM(total_traffic) as total_traffic,
    AVG(total_traffic) as avg_daily_traffic,
    COUNT(*) as data_points,
    RANK() OVER (ORDER BY SUM(total_traffic) DESC) as traffic_rank
FROM mv_daily_district_traffic
GROUP BY district_name
ORDER BY traffic_rank;

-- 인덱스 생성
CREATE UNIQUE INDEX idx_mv_district_ranking_name ON mv_district_ranking(district_name);
CREATE INDEX idx_mv_district_ranking_rank ON mv_district_ranking(traffic_rank);

-- ==============================================
-- Materialized View 새로고침 함수
-- ==============================================

-- 모든 Materialized View를 새로고침하는 함수
CREATE OR REPLACE FUNCTION refresh_all_traffic_mvs()
RETURNS TEXT AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    result TEXT;
BEGIN
    start_time := clock_timestamp();

    -- 의존성 순서에 따라 새로고침
    REFRESH MATERIALIZED VIEW mv_daily_traffic_summary;
    REFRESH MATERIALIZED VIEW mv_daily_hourly_traffic;
    REFRESH MATERIALIZED VIEW mv_daily_district_traffic;
    REFRESH MATERIALIZED VIEW mv_daily_station_traffic;
    REFRESH MATERIALIZED VIEW mv_period_summary;
    REFRESH MATERIALIZED VIEW mv_hourly_pattern;
    REFRESH MATERIALIZED VIEW mv_district_ranking;

    end_time := clock_timestamp();
    result := 'All materialized views refreshed successfully in ' ||
              EXTRACT(EPOCH FROM (end_time - start_time)) || ' seconds';

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ==============================================
-- 집계 테이블 메타데이터
-- ==============================================

-- 집계 테이블 정보를 저장하는 메타테이블
CREATE TABLE IF NOT EXISTS mv_metadata (
    mv_name VARCHAR(100) PRIMARY KEY,
    description TEXT,
    base_tables TEXT[],
    refresh_frequency VARCHAR(50),
    last_refresh_time TIMESTAMP,
    row_count BIGINT,
    size_mb NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 메타데이터 삽입
INSERT INTO mv_metadata (mv_name, description, base_tables, refresh_frequency) VALUES
('mv_daily_traffic_summary', '일별 교통량 전체 집계 - 가장 기본적인 집계', ARRAY['station_passenger_history'], 'daily'),
('mv_daily_hourly_traffic', '일별 + 시간대별 교통량 집계', ARRAY['station_passenger_history'], 'daily'),
('mv_daily_district_traffic', '일별 + 구별 교통량 집계', ARRAY['station_passenger_history', 'spatial_mapping'], 'daily'),
('mv_daily_station_traffic', '일별 + 정류장별 교통량 집계 (주요 정류장만)', ARRAY['station_passenger_history', 'spatial_mapping'], 'daily'),
('mv_period_summary', '전체 기간 요약 통계', ARRAY['mv_daily_traffic_summary'], 'after_daily_refresh'),
('mv_hourly_pattern', '시간대별 패턴 분석용 집계', ARRAY['mv_daily_hourly_traffic'], 'after_daily_refresh'),
('mv_district_ranking', '구별 교통량 순위', ARRAY['mv_daily_district_traffic'], 'after_daily_refresh')
ON CONFLICT (mv_name) DO UPDATE SET
    description = EXCLUDED.description,
    base_tables = EXCLUDED.base_tables,
    refresh_frequency = EXCLUDED.refresh_frequency;

-- ==============================================
-- 성능 확인 쿼리들
-- ==============================================

-- 1. 원본 vs Materialized View 성능 비교용 쿼리 세트
/*
-- 원본 쿼리 (느림)
SELECT record_date, SUM(ride_passenger + alight_passenger) as total_traffic
FROM station_passenger_history
WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'
GROUP BY record_date
ORDER BY record_date;

-- Materialized View 쿼리 (빠름)
SELECT record_date, total_traffic
FROM mv_daily_traffic_summary
WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'
ORDER BY record_date;
*/

-- 2. 집계 테이블 크기 및 성능 모니터링
CREATE OR REPLACE VIEW mv_performance_stats AS
SELECT
    schemaname,
    tablename as mv_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
    n_tup_ins as rows_inserted,
    n_tup_upd as rows_updated,
    n_tup_del as rows_deleted
FROM pg_stat_user_tables
WHERE tablename LIKE 'mv_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;