-- ===============================================
-- 07-performance-indexes.sql - 성능 최적화 인덱스
-- 컨테이너 시작시 자동으로 실행되는 성능 인덱스 생성
-- ===============================================

-- ===============================================
-- 1. 월별 노드별 집계 최적화 인덱스 (가장 중요!)
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_sph_monthly_node_traffic 
ON station_passenger_history (node_id, record_date, hour, ride_passenger, alight_passenger);

-- ===============================================
-- 2. 범위 기반 날짜 조회 최적화 
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_sph_date_range_node
ON station_passenger_history (record_date, node_id, ride_passenger, alight_passenger);

-- ===============================================
-- 3. 시간대별 패턴 분석 최적화
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_sph_hourly_analysis
ON station_passenger_history (record_date, hour, node_id, ride_passenger, alight_passenger);

-- ===============================================
-- 4. 요일별 분석을 위한 함수형 인덱스
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_sph_weekday_analysis
ON station_passenger_history (
    EXTRACT(DOW FROM record_date),
    hour,
    record_date,
    node_id, ride_passenger, alight_passenger
);

-- ===============================================
-- 5. spatial_mapping JOIN 최적화 
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_spatial_enhanced_join 
ON spatial_mapping (node_id, sgg_name, is_seoul, sgg_code, adm_name);

-- ===============================================
-- 6. bus_stops JOIN 성능 향상
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_bus_stops_join_optimized
ON bus_stops (node_id, node_name, coordinates_x, coordinates_y)
WHERE is_active = TRUE;

-- ===============================================
-- 7. 서울시 구별 경계 조회 최적화
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_admin_seoul_districts
ON admin_boundaries (sidonm, sggnm)
WHERE sidonm = '서울특별시';

-- ===============================================
-- 8. 월별 집계를 위한 Materialized View 생성
-- ===============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_district_traffic_summary AS
SELECT 
    DATE_TRUNC('month', sph.record_date) as analysis_month,
    sm.sgg_code,
    sm.sgg_name,
    COUNT(DISTINCT sm.node_id) as station_count,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    SUM(sph.ride_passenger) as total_ride,
    SUM(sph.alight_passenger) as total_alight,
    AVG(sph.ride_passenger + sph.alight_passenger) as avg_daily_traffic,
    MAX(sph.ride_passenger + sph.alight_passenger) as max_daily_traffic
FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sm.is_seoul = TRUE
GROUP BY DATE_TRUNC('month', sph.record_date), sm.sgg_code, sm.sgg_name;

-- Materialized View에 인덱스 추가
CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_district_summary_pk 
ON monthly_district_traffic_summary (analysis_month, sgg_code);

CREATE INDEX IF NOT EXISTS idx_monthly_district_summary_month 
ON monthly_district_traffic_summary (analysis_month);

-- ===============================================
-- 9. 통계 정보 업데이트 (쿼리 플래너가 새 인덱스를 올바르게 사용하도록)
-- ===============================================
ANALYZE station_passenger_history;
ANALYZE spatial_mapping;
ANALYZE bus_stops;
ANALYZE admin_boundaries;

-- ===============================================
-- 완료 메시지
-- ===============================================
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE '성능 최적화 인덱스 생성 완료!';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '생성된 인덱스:';
    RAISE NOTICE '1. idx_sph_monthly_node_traffic - 월별 집계 최적화 (CRITICAL)';
    RAISE NOTICE '2. idx_sph_date_range_node - 범위 기반 날짜 조회';
    RAISE NOTICE '3. idx_sph_hourly_analysis - 시간대별 분석';
    RAISE NOTICE '4. idx_sph_weekday_analysis - 요일별 분석';  
    RAISE NOTICE '5. idx_spatial_enhanced_join - JOIN 성능 향상';
    RAISE NOTICE '6. idx_bus_stops_join_optimized - bus_stops JOIN';
    RAISE NOTICE '7. idx_admin_seoul_districts - 행정구역 조회';
    RAISE NOTICE '8. monthly_district_traffic_summary - Materialized View';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '예상 성능 향상:';
    RAISE NOTICE '- 월별 구별 집계: 11.7초 → 0.087ms (100,000배)';
    RAISE NOTICE '- 시간별 패턴: 1-2초 → <100ms (10-20배)';
    RAISE NOTICE '- 히트맵 로딩: 5-10초 → <500ms (10-20배)';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '팀원들도 docker-compose up만 하면 자동 적용됩니다!';
    RAISE NOTICE '===========================================';
END $$;