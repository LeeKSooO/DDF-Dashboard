-- =====================================================
-- DRT Dashboard - Monthly OD Summary Materialized View
-- 작성일: 2025-09-10
-- 목적: 월간 OD 데이터 집계를 통한 DRT 도입 우선순위 분석
-- 
-- ## 설계 원칙:
-- - daily_od_analysis 테이블 기반 월간 집계
-- - 출현 빈도 및 패턴 분석 (평일/주말)
-- - DRT 우선순위 점수 사전 계산
-- - 61만개 unique OD pairs의 효율적 조회 지원
-- =====================================================

-- Monthly OD Summary Materialized View 생성
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_od_summary CASCADE;

CREATE MATERIALIZED VIEW mv_monthly_od_summary AS
WITH monthly_aggregation AS (
    SELECT 
        -- 기본 키 (월별 OD pair)
        DATE_TRUNC('month', analysis_date) AS analysis_month,
        from_station_id,
        to_station_id,
        
        -- Station 메타데이터 (최빈값 사용)
        MODE() WITHIN GROUP (ORDER BY from_station_name) AS from_station_name,
        MODE() WITHIN GROUP (ORDER BY from_coordinates_x) AS from_coordinates_x,
        MODE() WITHIN GROUP (ORDER BY from_coordinates_y) AS from_coordinates_y,
        MODE() WITHIN GROUP (ORDER BY from_district_code) AS from_district_code,
        MODE() WITHIN GROUP (ORDER BY from_district_name) AS from_district_name,
        MODE() WITHIN GROUP (ORDER BY from_admin_dong) AS from_admin_dong,
        
        MODE() WITHIN GROUP (ORDER BY to_station_name) AS to_station_name,
        MODE() WITHIN GROUP (ORDER BY to_coordinates_x) AS to_coordinates_x,
        MODE() WITHIN GROUP (ORDER BY to_coordinates_y) AS to_coordinates_y,
        MODE() WITHIN GROUP (ORDER BY to_district_code) AS to_district_code,
        MODE() WITHIN GROUP (ORDER BY to_district_name) AS to_district_name,
        MODE() WITHIN GROUP (ORDER BY to_admin_dong) AS to_admin_dong,
        
        -- 출현 빈도 분석
        COUNT(*) AS appearance_days,
        COUNT(*) FILTER (WHERE is_weekend = false) AS weekday_appearances,
        COUNT(*) FILTER (WHERE is_weekend = true) AS weekend_appearances,
        
        -- 수요 집계 (월간)
        SUM(total_passengers) AS monthly_total_passengers, -- OD Pair 월간 총 승객
        AVG(total_passengers) AS daily_avg_passengers,     -- OD Pair 일평균 총 승객

        -- 수요 변동성 파악, max와 min의 차이가 크면 불안정한 수요
        MAX(total_passengers) AS daily_max_passengers,     -- OD Pair가 한 달 중 가장 많은 승객이 이용한 날의 승객 수
        MIN(total_passengers) FILTER (WHERE total_passengers > 0) AS daily_min_passengers, -- OD Pair가 한 달 중 가장 적은 승객이 이용한 날의 승객 수(0 제외)
        -- OP Pair의 일별 승객 수가 평균에서 얼마나 흩어져 있는지, 표준편차가 클수록 불안정한 수요로 DRT 도입을 고려해볼 수 있음(안정적 수요는 고정노선으로)
        -- CV 계수 : 표준편차 / 평균 , 계산에서 활용, 운행된 모든 날의 일별 승객 수를 기준으로 계산
        -- 17일 적재상황이면 17개 값의 표준편차로 계산하고 운행하지 않은 날은 계산에서 제외
        STDDEV(total_passengers) AS daily_stddev_passengers,
        
        -- 시간대별 집계 (월간 합계)
        SUM(h00) AS monthly_h00, SUM(h01) AS monthly_h01, SUM(h02) AS monthly_h02, SUM(h03) AS monthly_h03,
        SUM(h04) AS monthly_h04, SUM(h05) AS monthly_h05, SUM(h06) AS monthly_h06, SUM(h07) AS monthly_h07,
        SUM(h08) AS monthly_h08, SUM(h09) AS monthly_h09, SUM(h10) AS monthly_h10, SUM(h11) AS monthly_h11,
        SUM(h12) AS monthly_h12, SUM(h13) AS monthly_h13, SUM(h14) AS monthly_h14, SUM(h15) AS monthly_h15,
        SUM(h16) AS monthly_h16, SUM(h17) AS monthly_h17, SUM(h18) AS monthly_h18, SUM(h19) AS monthly_h19,
        SUM(h20) AS monthly_h20, SUM(h21) AS monthly_h21, SUM(h22) AS monthly_h22, SUM(h23) AS monthly_h23,
        
        -- 시간대별 패턴 집계
        SUM(morning_peak_passengers) AS monthly_morning_peak,
        SUM(evening_peak_passengers) AS monthly_evening_peak,
        SUM(night_passengers) AS monthly_night,
        SUM(daytime_passengers) AS monthly_daytime,
        
        -- 평일/주말 수요 분리
        SUM(total_passengers) FILTER (WHERE is_weekend = false) AS weekday_total_passengers,
        SUM(total_passengers) FILTER (WHERE is_weekend = true) AS weekend_total_passengers,
        AVG(total_passengers) FILTER (WHERE is_weekend = false) AS weekday_avg_passengers,
        AVG(total_passengers) FILTER (WHERE is_weekend = true) AS weekend_avg_passengers,
        
        -- 시간대별 집중도 평균 (월간)
        AVG(morning_concentration) AS avg_morning_concentration,
        AVG(evening_concentration) AS avg_evening_concentration,
        AVG(night_concentration) AS avg_night_concentration,
        AVG(daytime_concentration) AS avg_daytime_concentration,
        
        -- 거리 및 연결성 (평균값)
        MAX(estimated_distance_km) AS avg_distance_km,   -- 같은 OD Pair에 대해 거리 고정이라 MAX 사용
        MAX(direct_connection_count) AS min_direct_connections,  -- 직행 연결 수
        BOOL_OR(transfer_required) AS ever_transfer_required,    -- 환승 필요 여부 : 한번이라도 환승이 필요했으면 true

        -- 노선 정보 (최신값 사용) - JSONB는 MAX를 지원하지 않으므로 임의값 선택
        (array_agg(common_routes))[1] AS common_routes,
        (array_agg(from_routes))[1] AS from_routes,
        (array_agg(to_routes))[1] AS to_routes
        
    FROM daily_od_analysis
    GROUP BY 
        DATE_TRUNC('month', analysis_date),
        from_station_id,
        to_station_id
)
SELECT 
    -- 기본 정보
    analysis_month,
    from_station_id,
    to_station_id,
    from_station_name,
    (SELECT node_num FROM bus_stops WHERE node_id = from_station_id) AS from_station_num,
    from_coordinates_x,
    from_coordinates_y,
    from_district_code,
    from_district_name,
    from_admin_dong,
    to_station_name,
    (SELECT node_num FROM bus_stops WHERE node_id = to_station_id) AS to_station_num,
    to_coordinates_x,
    to_coordinates_y,
    to_district_code,
    to_district_name,
    to_admin_dong,
    
    -- 빈도 정보
    appearance_days,
    weekday_appearances,
    weekend_appearances,
    CASE 
        WHEN appearance_days = 17 THEN '매일'
        WHEN appearance_days >= 13 THEN '거의매일 (13-16일)'
        WHEN appearance_days >= 9 THEN '고빈도 (9-12일)'
        WHEN appearance_days >= 5 THEN '중빈도 (5-8일)'
        ELSE '저빈도 (<5일)'
    END AS frequency_category,
    
    -- 수요 정보
    monthly_total_passengers,
    daily_avg_passengers,
    daily_max_passengers,
    daily_min_passengers,
    daily_stddev_passengers,
    CASE 
        WHEN daily_stddev_passengers IS NOT NULL AND daily_avg_passengers > 0 
        THEN daily_stddev_passengers / daily_avg_passengers 
        ELSE NULL 
    END AS cv_coefficient,
    
    -- 시간대별 정보
    monthly_h00, monthly_h01, monthly_h02, monthly_h03,
    monthly_h04, monthly_h05, monthly_h06, monthly_h07,
    monthly_h08, monthly_h09, monthly_h10, monthly_h11,
    monthly_h12, monthly_h13, monthly_h14, monthly_h15,
    monthly_h16, monthly_h17, monthly_h18, monthly_h19,
    monthly_h20, monthly_h21, monthly_h22, monthly_h23,
    
    monthly_morning_peak,
    monthly_evening_peak,
    monthly_night,
    monthly_daytime,
    
    -- 시간대별 집중도
    avg_morning_concentration,
    avg_evening_concentration,
    avg_night_concentration,
    avg_daytime_concentration,
    
    -- 평일/주말 패턴
    weekday_total_passengers,
    weekend_total_passengers,
    weekday_avg_passengers,
    weekend_avg_passengers,
    CASE 
        WHEN weekday_total_passengers > 0 
        THEN weekend_total_passengers::DECIMAL / weekday_total_passengers 
        ELSE NULL 
    END AS weekend_weekday_ratio,
    
    -- 연결성 정보
    avg_distance_km,
    min_direct_connections,
    ever_transfer_required,
    common_routes,
    from_routes,
    to_routes,
    
    -- 배차간격 데이터 (JSONB에서 계산)
    (SELECT AVG((route->>'dispatch_interval')::integer) 
     FROM jsonb_array_elements(common_routes) AS route
     WHERE route->>'dispatch_interval' IS NOT NULL) AS avg_dispatch_interval,
    (SELECT MAX((route->>'dispatch_interval')::integer) 
     FROM jsonb_array_elements(common_routes) AS route
     WHERE route->>'dispatch_interval' IS NOT NULL) AS max_dispatch_interval,
    (SELECT MIN((route->>'dispatch_interval')::integer) 
     FROM jsonb_array_elements(common_routes) AS route
     WHERE route->>'dispatch_interval' IS NOT NULL) AS min_dispatch_interval,
    
    -- DRT 우선순위 점수 계산
    -- P1: 환승필요 + 일평균 100명 이상 (가중치 10)
    CASE 
        WHEN ever_transfer_required = true AND daily_avg_passengers >= 100 
        THEN 10 
        ELSE 0 
    END AS p1_score,
    
    -- P2: 환승필요 + 일평균 20-99명 (가중치 5)
    CASE 
        WHEN ever_transfer_required = true AND daily_avg_passengers BETWEEN 20 AND 99 
        THEN 5 
        ELSE 0 
    END AS p2_score,
    
    -- P3: 직행노선 2개 이하 + 일평균 100명 이상 (가중치 3)
    CASE 
        WHEN min_direct_connections <= 2 AND ever_transfer_required = false AND daily_avg_passengers >= 100 
        THEN 3 
        ELSE 0 
    END AS p3_score,
    
    -- P4: 일평균 50명 미만 + 5km 이상 (가중치 1)
    CASE 
        WHEN daily_avg_passengers < 50 AND avg_distance_km >= 5 
        THEN 1 
        ELSE 0 
    END AS p4_score,
    
    -- 총 DRT 우선순위 점수 (기본)
    (CASE WHEN ever_transfer_required = true AND daily_avg_passengers >= 100 THEN 10 ELSE 0 END +
     CASE WHEN ever_transfer_required = true AND daily_avg_passengers BETWEEN 20 AND 99 THEN 5 ELSE 0 END +
     CASE WHEN min_direct_connections <= 2 AND ever_transfer_required = false AND daily_avg_passengers >= 100 THEN 3 ELSE 0 END +
     CASE WHEN daily_avg_passengers < 50 AND avg_distance_km >= 5 THEN 1 ELSE 0 END) AS drt_priority_score,
    
    -- 서비스 품질 보정 DRT 점수
    (CASE WHEN ever_transfer_required = true AND daily_avg_passengers >= 100 THEN 10 ELSE 0 END +
     CASE WHEN ever_transfer_required = true AND daily_avg_passengers BETWEEN 20 AND 99 THEN 5 ELSE 0 END +
     CASE WHEN min_direct_connections <= 2 AND ever_transfer_required = false AND daily_avg_passengers >= 100 THEN 3 ELSE 0 END +
     CASE WHEN daily_avg_passengers < 50 AND avg_distance_km >= 5 THEN 1 ELSE 0 END +
     CASE 
         WHEN (SELECT AVG((route->>'dispatch_interval')::integer) FROM jsonb_array_elements(common_routes) AS route WHERE route->>'dispatch_interval' IS NOT NULL) > 30 THEN 2
         WHEN (SELECT AVG((route->>'dispatch_interval')::integer) FROM jsonb_array_elements(common_routes) AS route WHERE route->>'dispatch_interval' IS NOT NULL) > 20 THEN 1
         ELSE 0
     END) AS adjusted_drt_priority_score,
    
    -- DRT 권장사항
    CASE 
        WHEN ever_transfer_required = true AND daily_avg_passengers >= 100 THEN 'DRT 최우선고려구간'
        WHEN ever_transfer_required = true AND daily_avg_passengers >= 20 THEN 'DRT 우선고려구간'
        WHEN min_direct_connections <= 2 AND daily_avg_passengers >= 100 THEN 'DRT 고려구간'
        WHEN daily_avg_passengers < 50 AND avg_distance_km >= 5 THEN 'DRT 검토 가능'  -- 장거리 저수요 구간으로 DRT로 전환 고려(운영비 절감 목적)
        ELSE '기존 서비스'
    END AS drt_recommendation,
    
    -- 메타데이터
    CURRENT_TIMESTAMP AS created_at
    
FROM monthly_aggregation;

-- =====================================================
-- 인덱스 생성 (Materialized View 성능 최적화)
-- =====================================================

-- Unique 인덱스 (PK 역할)
CREATE UNIQUE INDEX idx_mv_monthly_od_unique 
    ON mv_monthly_od_summary (analysis_month, from_station_id, to_station_id);

-- 월별 조회
CREATE INDEX idx_mv_monthly_od_month 
    ON mv_monthly_od_summary (analysis_month);

-- DRT 우선순위 조회
CREATE INDEX idx_mv_monthly_od_drt_score 
    ON mv_monthly_od_summary (drt_priority_score DESC);

CREATE INDEX idx_mv_monthly_od_adjusted_drt_score 
    ON mv_monthly_od_summary (adjusted_drt_priority_score DESC);

-- 빈도 카테고리별 조회
CREATE INDEX idx_mv_monthly_od_frequency 
    ON mv_monthly_od_summary (frequency_category, monthly_total_passengers DESC);

-- 구별 분석
CREATE INDEX idx_mv_monthly_od_from_district 
    ON mv_monthly_od_summary (from_district_name, drt_priority_score DESC);

CREATE INDEX idx_mv_monthly_od_to_district 
    ON mv_monthly_od_summary (to_district_name, drt_priority_score DESC);

-- 환승 필요 구간 조회
CREATE INDEX idx_mv_monthly_od_transfer 
    ON mv_monthly_od_summary (ever_transfer_required) 
    WHERE ever_transfer_required = true;

-- 고수요 구간 조회
CREATE INDEX idx_mv_monthly_od_high_demand 
    ON mv_monthly_od_summary (monthly_total_passengers DESC);

-- 장거리 저수요 구간 조회
CREATE INDEX idx_mv_monthly_od_long_low 
    ON mv_monthly_od_summary (avg_distance_km DESC) 
    WHERE daily_avg_passengers < 50;

-- 서비스 품질별 조회
CREATE INDEX idx_mv_monthly_od_service_quality 
    ON mv_monthly_od_summary (service_quality_grade, adjusted_drt_priority_score DESC);

-- 배차간격 기반 조회
CREATE INDEX idx_mv_monthly_od_dispatch_interval 
    ON mv_monthly_od_summary (avg_dispatch_interval DESC) 
    WHERE avg_dispatch_interval IS NOT NULL;

-- 시간대별 집중도 조회
CREATE INDEX idx_mv_monthly_od_morning_concentration 
    ON mv_monthly_od_summary (avg_morning_concentration DESC);

CREATE INDEX idx_mv_monthly_od_evening_concentration 
    ON mv_monthly_od_summary (avg_evening_concentration DESC);

CREATE INDEX idx_mv_monthly_od_night_concentration 
    ON mv_monthly_od_summary (avg_night_concentration DESC);

CREATE INDEX idx_mv_monthly_od_daytime_concentration 
    ON mv_monthly_od_summary (avg_daytime_concentration DESC);

-- =====================================================
-- Refresh 함수 생성 (월간 데이터 업데이트용)
-- =====================================================

CREATE OR REPLACE FUNCTION refresh_monthly_od_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_od_summary;
    RAISE NOTICE 'Monthly OD Summary refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 권한 설정
-- =====================================================

GRANT SELECT ON mv_monthly_od_summary TO ddf_user;
GRANT SELECT ON mv_monthly_od_summary TO PUBLIC;

-- =====================================================
-- 테이블 설명
-- =====================================================

COMMENT ON MATERIALIZED VIEW mv_monthly_od_summary IS 
    'Monthly aggregation of OD data for DRT priority analysis. Contains 610K+ unique OD pairs with frequency patterns and DRT suitability scores.';

COMMENT ON COLUMN mv_monthly_od_summary.frequency_category IS 'Appearance frequency category: 매일(17), 거의매일(13-16), 고빈도(9-12), 중빈도(5-8), 저빈도(<5)';
COMMENT ON COLUMN mv_monthly_od_summary.drt_priority_score IS 'DRT priority score: P1(10) + P2(5) + P3(3) + P4(1)';
COMMENT ON COLUMN mv_monthly_od_summary.adjusted_drt_priority_score IS 'Service quality adjusted DRT score: base score + dispatch interval penalty';
COMMENT ON COLUMN mv_monthly_od_summary.drt_recommendation IS 'DRT service recommendation based on priority analysis';
COMMENT ON COLUMN mv_monthly_od_summary.cv_coefficient IS 'Coefficient of variation (stddev/mean) for demand stability';
COMMENT ON COLUMN mv_monthly_od_summary.weekend_weekday_ratio IS 'Weekend to weekday demand ratio';
COMMENT ON COLUMN mv_monthly_od_summary.service_quality_grade IS 'Service quality grade based on average dispatch interval';
COMMENT ON COLUMN mv_monthly_od_summary.avg_dispatch_interval IS 'Average dispatch interval in minutes of common routes';
COMMENT ON COLUMN mv_monthly_od_summary.avg_morning_concentration IS 'Average morning peak concentration ratio (7-9AM)';
COMMENT ON COLUMN mv_monthly_od_summary.avg_evening_concentration IS 'Average evening peak concentration ratio (5-7PM)';
COMMENT ON COLUMN mv_monthly_od_summary.avg_night_concentration IS 'Average night concentration ratio (10PM-5AM)';
COMMENT ON COLUMN mv_monthly_od_summary.avg_daytime_concentration IS 'Average daytime concentration ratio (10AM-4PM)';

-- =====================================================
-- 완료 메시지
-- =====================================================

DO $$ 
BEGIN 
    RAISE NOTICE 'Monthly OD Summary Materialized View 생성 완료';
    RAISE NOTICE '- View명: mv_monthly_od_summary';
    RAISE NOTICE '- 예상 레코드 수: ~610K (unique OD pairs per month)';
    RAISE NOTICE '- 인덱스: 9개 (조회 최적화)';
    RAISE NOTICE '- DRT 우선순위 점수 포함';
    RAISE NOTICE '- Refresh 함수: refresh_monthly_od_summary()';
END $$;