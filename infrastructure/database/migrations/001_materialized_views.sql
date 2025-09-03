-- =====================================================
-- DRT Dashboard Materialized Views
-- 작성일: 2025-08-29
-- 목적: API 성능 최적화를 위한 집계 테이블
-- 
-- ## 집계하고 있는 주요 지표들:
-- 1. 시간대별 교통 패턴 (승차/하차 인원수, 시간별 분포)
-- 2. 구별 월간 교통량 총계 (일평균, 히트맵용 분위수)
-- 3. 정류장별 월간 교통량 (운행정보, 노선수)
-- 4. 서울시 전체 시간대별 패턴 (전체 집계)
-- 5. 성능 통계 (디스크 사용량, 갱신 상태)
-- =====================================================

-- 1. 시간대별 교통량 패턴 (Traffic API용)
-- 용도: /api/v1/traffic/hourly
-- 집계 수준: 구별 + 시간대별 + 요일구분별
-- 
-- ## 집계 지표:
-- - 평균 승차/하차 인원 (시간대별)
-- - 최대/최소 승차/하차 인원 (피크 시간 분석용)
-- - 총 승객 수 (승차 + 하차)
-- - 정류장 수, 운영일수 (샘플 메타데이터)
DROP MATERIALIZED VIEW IF EXISTS mv_hourly_traffic_patterns CASCADE;

CREATE MATERIALIZED VIEW mv_hourly_traffic_patterns AS
WITH date_classification AS (
    SELECT DISTINCT
        record_date,
        CASE 
            WHEN EXTRACT(DOW FROM record_date) BETWEEN 1 AND 5 THEN 'weekday'
            ELSE 'weekend'
        END as day_type
    FROM station_passenger_history
)
SELECT 
    -- 기간 정보
    DATE_TRUNC('month', sph.record_date)::date as month_date,
    dc.day_type,
    
    -- 지역 정보
    sm.sgg_code,
    sm.sgg_name,
    
    -- 시간대
    sph.hour,
    
    -- 집계값 (평균)
    AVG(sph.ride_passenger)::numeric(10,2) as avg_ride_passengers,
    AVG(sph.alight_passenger)::numeric(10,2) as avg_alight_passengers,
    AVG(sph.ride_passenger + sph.alight_passenger)::numeric(10,2) as avg_total_passengers,
    
    -- 추가 통계 (최대/최소 - 피크 시간 계산용)
    MAX(sph.ride_passenger) as max_ride_passengers,
    MAX(sph.alight_passenger) as max_alight_passengers,
    MIN(sph.ride_passenger) as min_ride_passengers,
    MIN(sph.alight_passenger) as min_alight_passengers,
    
    -- 메타 정보
    COUNT(*) as sample_count,
    COUNT(DISTINCT sph.node_id) as station_count,
    COUNT(DISTINCT sph.record_date) as day_count
FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
INNER JOIN date_classification dc ON sph.record_date = dc.record_date
WHERE sm.is_seoul = TRUE
GROUP BY 
    DATE_TRUNC('month', sph.record_date),
    dc.day_type,
    sm.sgg_code,
    sm.sgg_name,
    sph.hour;

-- 인덱스 생성
CREATE INDEX idx_mv_hourly_traffic_lookup 
ON mv_hourly_traffic_patterns(month_date, sgg_name, day_type, hour);

CREATE INDEX idx_mv_hourly_traffic_seoul
ON mv_hourly_traffic_patterns(month_date, day_type, hour)
WHERE sgg_name IS NOT NULL;

-- =====================================================

-- 2. 구별 교통량 총계 (Heatmap API용)
-- 용도: /api/v1/heatmap/seoul, /districts/{name}
-- 집계 수준: 구별 월간 총계
-- 
-- ## 집계 지표:
-- - 총 교통량 (월간 합계: 승차 + 하차 + 전체)
-- - 일평균 교통량 (월간 평균)
-- - 분위수 (Q1, Q2, Q3, 최대/최소) → 히트맵 색상 계산용
-- - 정류장 수, 운영일수 (인프라 현황)
DROP MATERIALIZED VIEW IF EXISTS mv_district_monthly_traffic CASCADE;

CREATE MATERIALIZED VIEW mv_district_monthly_traffic AS
SELECT 
    -- 기간 정보
    DATE_TRUNC('month', sph.record_date)::date as month_date,
    
    -- 지역 정보
    sm.sgg_code as district_code,
    sm.sgg_name as district_name,
    
    -- 총 교통량
    SUM(sph.ride_passenger) as total_ride,
    SUM(sph.alight_passenger) as total_alight,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    
    -- 일평균
    AVG(sph.ride_passenger + sph.alight_passenger)::numeric(10,2) as avg_daily_traffic,
    
    -- 정류장 정보
    COUNT(DISTINCT sm.node_id) as station_count,
    COUNT(DISTINCT sph.record_date) as operating_days,
    
    -- 시간대별 분포 (히트맵 색상 계산용)
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY sph.ride_passenger + sph.alight_passenger) as q1_traffic,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY sph.ride_passenger + sph.alight_passenger) as q2_traffic,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY sph.ride_passenger + sph.alight_passenger) as q3_traffic,
    MAX(sph.ride_passenger + sph.alight_passenger) as max_hourly_traffic,
    MIN(sph.ride_passenger + sph.alight_passenger) as min_hourly_traffic
FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sm.is_seoul = TRUE
GROUP BY 
    DATE_TRUNC('month', sph.record_date),
    sm.sgg_code,
    sm.sgg_name;

-- 인덱스 생성
CREATE INDEX idx_mv_district_traffic_lookup
ON mv_district_monthly_traffic(month_date, district_name);

CREATE INDEX idx_mv_district_traffic_rank
ON mv_district_monthly_traffic(month_date, total_traffic DESC);

-- =====================================================

-- 3. 정류장별 교통량 (Heatmap 상세용)
-- 용도: /api/v1/heatmap/districts/{name} stations 배열
-- 집계 수준: 정류장별 월간 총계
-- 
-- ## 집계 지표:
-- - 정류장별 월간 교통량 (승차/하차/전체)
-- - 일평균 교통량 (월간 평균)
-- - 위치 정보 (위도, 경도)
-- - 운영 메타데이터 (운영일수, 노선수, 운행시간수)
DROP MATERIALIZED VIEW IF EXISTS mv_station_monthly_traffic CASCADE;

CREATE MATERIALIZED VIEW mv_station_monthly_traffic AS
SELECT 
    -- 기간 정보
    DATE_TRUNC('month', sph.record_date)::date as month_date,
    
    -- 지역 정보
    sm.sgg_code,
    sm.sgg_name as district_name,
    
    -- 정류장 정보
    sm.node_id as station_id,
    bs.node_name as station_name,
    bs.coordinates_y as latitude,
    bs.coordinates_x as longitude,
    
    -- 교통량
    SUM(sph.ride_passenger) as total_ride,
    SUM(sph.alight_passenger) as total_alight,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    AVG(sph.ride_passenger + sph.alight_passenger)::numeric(10,2) as daily_average,
    
    -- 운행 정보
    COUNT(DISTINCT sph.record_date) as operating_days,
    COUNT(DISTINCT sph.route_id) as route_count,
    COUNT(DISTINCT sph.hour) as operating_hours
FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
INNER JOIN bus_stops bs ON sm.node_id = bs.node_id
WHERE sm.is_seoul = TRUE
GROUP BY 
    DATE_TRUNC('month', sph.record_date),
    sm.sgg_code,
    sm.sgg_name,
    sm.node_id,
    bs.node_name,
    bs.coordinates_y,
    bs.coordinates_x;

-- 인덱스 생성
CREATE INDEX idx_mv_station_traffic_lookup
ON mv_station_monthly_traffic(month_date, district_name, station_id);

CREATE INDEX idx_mv_station_traffic_rank
ON mv_station_monthly_traffic(month_date, district_name, total_traffic DESC);

-- =====================================================

-- 4. 서울시 전체 시간대별 패턴 (Traffic API 서울시 전체용)
-- 용도: region_type='seoul'일 때 빠른 조회
-- 
-- ## 집계 지표:
-- - 서울시 전체 시간별 평균 승하차 인원
-- - 시간별 최대 승하차 인원 (피크 분석용)
-- - 전체 샘플 수, 정류장 수 (데이터 품질 확인용)
-- - 가중평균 계산 (구별 데이터를 서울시 전체로 집계)
DROP MATERIALIZED VIEW IF EXISTS mv_seoul_hourly_patterns CASCADE;

CREATE MATERIALIZED VIEW mv_seoul_hourly_patterns AS
SELECT 
    month_date,
    day_type,
    hour,
    SUM(avg_ride_passengers * sample_count) / SUM(sample_count) as avg_ride_passengers,
    SUM(avg_alight_passengers * sample_count) / SUM(sample_count) as avg_alight_passengers,
    SUM(avg_total_passengers * sample_count) / SUM(sample_count) as avg_total_passengers,
    MAX(max_ride_passengers) as max_ride_passengers,
    MAX(max_alight_passengers) as max_alight_passengers,
    SUM(sample_count) as total_samples,
    SUM(station_count) as total_stations
FROM mv_hourly_traffic_patterns
GROUP BY month_date, day_type, hour;

-- 인덱스 생성
CREATE INDEX idx_mv_seoul_hourly_lookup
ON mv_seoul_hourly_patterns(month_date, day_type, hour);

-- =====================================================

-- 5. 갱신 함수 (ETL 완료 후 실행)
-- 
-- ## Materialized View 갱신 순서:
-- 1) mv_hourly_traffic_patterns (기본 시간별 패턴)
-- 2) mv_district_monthly_traffic (구별 월간 집계)
-- 3) mv_station_monthly_traffic (정류장별 월간 집계)
-- 4) mv_seoul_hourly_patterns (서울시 전체 집계 - 의존성 있음)
CREATE OR REPLACE FUNCTION refresh_all_traffic_views()
RETURNS void AS $$
BEGIN
    -- 순서 중요: 의존성 있는 뷰는 나중에 갱신
    RAISE NOTICE 'Refreshing hourly traffic patterns...';
    REFRESH MATERIALIZED VIEW mv_hourly_traffic_patterns;
    
    RAISE NOTICE 'Refreshing district monthly traffic...';
    REFRESH MATERIALIZED VIEW mv_district_monthly_traffic;
    
    RAISE NOTICE 'Refreshing station monthly traffic...';
    REFRESH MATERIALIZED VIEW mv_station_monthly_traffic;
    
    RAISE NOTICE 'Refreshing Seoul hourly patterns...';
    REFRESH MATERIALIZED VIEW mv_seoul_hourly_patterns;
    
    RAISE NOTICE 'All views refreshed successfully!';
    
    -- NOTE: mv_station_hourly_patterns는 별도 관리
    -- 필요시: SELECT refresh_station_hourly_patterns();
END;
$$ LANGUAGE plpgsql;

-- =====================================================

-- 6. 뷰 통계 확인 함수 (단순화)
-- 
-- ## 모니터링 지표:
-- - 각 Materialized View의 디스크 사용량
-- - 갱신 상태 및 성능 확인용
CREATE OR REPLACE FUNCTION check_mv_statistics()
RETURNS TABLE(
    view_name text,
    disk_size text
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        matviewname::text as view_name,
        pg_size_pretty(pg_total_relation_size((schemaname||'.'||matviewname)::regclass)) as disk_size
    FROM pg_matviews
    WHERE schemaname = 'public' 
        AND matviewname LIKE 'mv_%'
    ORDER BY matviewname;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 사용 예시:
-- SELECT refresh_all_traffic_views();  -- ETL 후 실행
-- SELECT * FROM check_mv_statistics(); -- 상태 확인
-- =====================================================