-- =====================================================
-- DRT Dashboard - Station Hourly Patterns MV
-- 작성일: 2025-08-30
-- 목적: Anomaly Pattern API 성능 최적화용 정류장별 시간대별 집계
-- 
-- ## 설계 원칙:
-- - 정류장별 + 시간별 + 요일구분별 집계
-- - TOP N 정류장 선별 및 시간대별 분석 동시 지원
-- - 기존 station_passenger_history 직접 조회 대체
-- =====================================================

-- 정류장별 시간대별 교통량 패턴 MV
DROP MATERIALIZED VIEW IF EXISTS mv_station_hourly_patterns CASCADE;

CREATE MATERIALIZED VIEW mv_station_hourly_patterns AS
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
    sm.sgg_name as district_name,
    
    -- 정류장 정보
    sm.node_id as station_id,
    bs.node_name as station_name,
    bs.coordinates_y as latitude,
    bs.coordinates_x as longitude,
    COALESCE(sm.adm_name, '정보없음') as administrative_dong,
    
    -- 시간대
    sph.hour,
    
    -- 집계값 (총합)
    SUM(sph.ride_passenger) as total_ride,
    SUM(sph.alight_passenger) as total_alight,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    
    -- 메타 정보
    COUNT(DISTINCT sph.record_date) as operating_days,
    COUNT(DISTINCT sph.route_id) as route_count,
    COUNT(*) as record_count

FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
INNER JOIN bus_stops bs ON sm.node_id = bs.node_id
INNER JOIN date_classification dc ON sph.record_date = dc.record_date
WHERE sm.is_seoul = TRUE
GROUP BY 
    DATE_TRUNC('month', sph.record_date),
    dc.day_type,
    sm.sgg_code,
    sm.sgg_name,
    sm.node_id,
    bs.node_name,
    bs.coordinates_y,
    bs.coordinates_x,
    sm.adm_name,
    sph.hour;

-- =====================================================
-- 인덱스 생성 (조회 최적화)
-- =====================================================

-- 1. Anomaly Pattern API용 주요 인덱스
CREATE INDEX idx_mv_station_hourly_anomaly_lookup 
ON mv_station_hourly_patterns(month_date, district_name, day_type);

-- 2. 정류장별 조회용 인덱스  
CREATE INDEX idx_mv_station_hourly_station_lookup
ON mv_station_hourly_patterns(month_date, district_name, station_id);

-- 3. 시간대별 조회용 인덱스 (심야, 러시아워 등)
CREATE INDEX idx_mv_station_hourly_time_lookup
ON mv_station_hourly_patterns(month_date, district_name, hour)
WHERE hour IN (6,7,8,11,12,13,17,18,19,23,0,1,2,3);

-- 4. TOP N 정류장 선별용 인덱스 (total_ride 내림차순)
CREATE INDEX idx_mv_station_hourly_top_ride
ON mv_station_hourly_patterns(month_date, district_name, total_ride DESC)
WHERE total_ride > 0;

-- =====================================================
-- 갱신 함수 (ETL 완료 후 실행)
-- =====================================================

CREATE OR REPLACE FUNCTION refresh_station_hourly_patterns()
RETURNS void AS $$
BEGIN
    RAISE NOTICE 'Refreshing station hourly patterns...';
    REFRESH MATERIALIZED VIEW mv_station_hourly_patterns;
    RAISE NOTICE 'Station hourly patterns refreshed successfully!';
    RAISE NOTICE 'Total records: %', (SELECT COUNT(*) FROM mv_station_hourly_patterns);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 상태 확인 함수
-- =====================================================

CREATE OR REPLACE FUNCTION check_station_hourly_stats()
RETURNS TABLE(
    record_count BIGINT,
    latest_month DATE,
    districts_count BIGINT,
    stations_count BIGINT,
    sample_district VARCHAR(50),
    sample_station VARCHAR(100),
    avg_records_per_station NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as record_count,
        MAX(month_date) as latest_month,
        COUNT(DISTINCT district_name) as districts_count,
        COUNT(DISTINCT station_id) as stations_count,
        (SELECT district_name FROM mv_station_hourly_patterns LIMIT 1) as sample_district,
        (SELECT station_name FROM mv_station_hourly_patterns LIMIT 1) as sample_station,
        ROUND(COUNT(*)::numeric / COUNT(DISTINCT station_id), 2) as avg_records_per_station
    FROM mv_station_hourly_patterns;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Anomaly Pattern API 전용 헬퍼 함수들
-- =====================================================

-- 심야시간 고수요 정류장 TOP N (단일 쿼리로 최적화)
CREATE OR REPLACE FUNCTION get_night_demand_top_stations(
    p_district VARCHAR(50),
    p_month DATE,
    p_top_n INTEGER DEFAULT 5
)
RETURNS TABLE(
    station_id VARCHAR(20),
    station_name VARCHAR(100),
    latitude FLOAT,
    longitude FLOAT,
    district_name VARCHAR(50),
    administrative_dong VARCHAR(50),
    total_night_ride BIGINT,
    hour_23 BIGINT,
    hour_0 BIGINT,
    hour_1 BIGINT,
    hour_2 BIGINT,
    hour_3 BIGINT,
    peak_hour INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH night_stats AS (
        SELECT 
            shp.station_id,
            shp.station_name,
            shp.latitude,
            shp.longitude,
            shp.district_name,
            shp.administrative_dong,
            SUM(CASE WHEN shp.hour IN (23,0,1,2,3) THEN shp.total_ride ELSE 0 END) as total_night_ride,
            SUM(CASE WHEN shp.hour = 23 THEN shp.total_ride ELSE 0 END) as hour_23,
            SUM(CASE WHEN shp.hour = 0 THEN shp.total_ride ELSE 0 END) as hour_0,
            SUM(CASE WHEN shp.hour = 1 THEN shp.total_ride ELSE 0 END) as hour_1,
            SUM(CASE WHEN shp.hour = 2 THEN shp.total_ride ELSE 0 END) as hour_2,
            SUM(CASE WHEN shp.hour = 3 THEN shp.total_ride ELSE 0 END) as hour_3
        FROM mv_station_hourly_patterns shp
        WHERE shp.month_date = p_month
          AND shp.district_name = p_district
          AND shp.hour IN (23,0,1,2,3)
        GROUP BY shp.station_id, shp.station_name, shp.latitude, shp.longitude, 
                 shp.district_name, shp.administrative_dong
        HAVING SUM(CASE WHEN shp.hour IN (23,0,1,2,3) THEN shp.total_ride ELSE 0 END) > 0
        ORDER BY total_night_ride DESC
        LIMIT p_top_n
    )
    SELECT 
        ns.*,
        CASE 
            WHEN ns.hour_23 >= GREATEST(ns.hour_0, ns.hour_1, ns.hour_2, ns.hour_3) THEN 23
            WHEN ns.hour_0 >= GREATEST(ns.hour_1, ns.hour_2, ns.hour_3) THEN 0
            WHEN ns.hour_1 >= GREATEST(ns.hour_2, ns.hour_3) THEN 1
            WHEN ns.hour_2 >= ns.hour_3 THEN 2
            ELSE 3
        END as peak_hour
    FROM night_stats ns;
END;
$$ LANGUAGE plpgsql;

-- 러시아워 정류장 TOP N (추후 구현용)
CREATE OR REPLACE FUNCTION get_rush_hour_top_stations(
    p_district VARCHAR(50),
    p_month DATE,
    p_top_n INTEGER DEFAULT 5
)
RETURNS TABLE(
    station_id VARCHAR(20),
    station_name VARCHAR(100),
    latitude FLOAT,
    longitude FLOAT,
    district_name VARCHAR(50),
    administrative_dong VARCHAR(50),
    total_rush_ride BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        shp.station_id,
        shp.station_name,
        shp.latitude,
        shp.longitude,
        shp.district_name,
        shp.administrative_dong,
        SUM(CASE WHEN shp.hour IN (7,8,17,18,19) THEN shp.total_ride ELSE 0 END) as total_rush_ride
    FROM mv_station_hourly_patterns shp
    WHERE shp.month_date = p_month
      AND shp.district_name = p_district
      AND shp.day_type = 'weekday'
      AND shp.hour IN (7,8,17,18,19)
    GROUP BY shp.station_id, shp.station_name, shp.latitude, shp.longitude, 
             shp.district_name, shp.administrative_dong
    HAVING SUM(CASE WHEN shp.hour IN (7,8,17,18,19) THEN shp.total_ride ELSE 0 END) > 0
    ORDER BY total_rush_ride DESC
    LIMIT p_top_n;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 사용 예시:
-- 
-- ## ETL 완료 후 실행:
-- SELECT refresh_station_hourly_patterns();
-- 
-- ## 심야시간 고수요 정류장 TOP 5:
-- SELECT * FROM get_night_demand_top_stations('마포구', '2025-07-01', 5);
-- 
-- ## 러시아워 정류장 TOP 5:
-- SELECT * FROM get_rush_hour_top_stations('강남구', '2025-07-01', 5);
-- 
-- ## 상태 확인:
-- SELECT * FROM check_station_hourly_stats();
-- =====================================================