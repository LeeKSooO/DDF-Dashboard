-- ============================================
-- 출퇴근형 DRT Score 집계 테이블 생성
-- 월평균 기준 Feature 계산 및 집계
-- ============================================

-- 출퇴근형 DRT Score 집계 테이블
CREATE TABLE IF NOT EXISTS drt_commuter_scores (
    station_id VARCHAR(20) NOT NULL,
    district_name VARCHAR(50) NOT NULL,  -- 구명 (API 필터링용)
    analysis_month DATE NOT NULL,  -- YYYY-MM-01 형식
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    
    -- Feature Scores (0-1 정규화)
    tc_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 시간 집중도 (특정시간 배차수 / 일일최대 배차수)
    pdr_score DECIMAL(8,6) NOT NULL DEFAULT 0,   -- 피크 수요 비율 (특정시간 승하차수 / 일일최대 승하차수)
    ru_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 노선 활용도 (구간승객수 Min-Max 정규화)
    pcw_score DECIMAL(8,6) NOT NULL DEFAULT 1.0, -- POI 카테고리 가중치 (하드코딩 예정)
    
    -- Raw Data (참조용)
    avg_dispatch_count DECIMAL(10,2) DEFAULT 0,     -- 월평균 시간대별 배차수
    max_daily_dispatch DECIMAL(10,2) DEFAULT 0,     -- 월평균 일일 최대 배차수
    avg_traffic_count DECIMAL(10,2) DEFAULT 0,      -- 월평균 시간대별 승하차수  
    max_daily_traffic DECIMAL(10,2) DEFAULT 0,      -- 월평균 일일 최대 승하차수
    section_passenger_sum BIGINT DEFAULT 0,         -- 월간 구간별 승객수 합계
    
    -- Total DRT Score (0-100)
    total_drt_score DECIMAL(8,4) NOT NULL DEFAULT 0, -- (TC*0.4 + PDR*0.4 + RU*0.2) * PCW * 100
    
    -- 메타데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (station_id, analysis_month, hour_of_day),
    FOREIGN KEY (station_id) REFERENCES bus_stops(node_id)
);

-- 성능 최적화 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_drt_commuter_scores_analysis_month ON drt_commuter_scores(analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_commuter_scores_station_month ON drt_commuter_scores(station_id, analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_commuter_scores_total_score ON drt_commuter_scores(analysis_month, total_drt_score DESC);

-- DRT API용 복합 인덱스 추가 (히트맵 조회 최적화)
CREATE INDEX IF NOT EXISTS idx_drt_commuter_district_heatmap 
ON drt_commuter_scores(analysis_month, station_id)
INCLUDE (hour_of_day, total_drt_score);

-- 정류장 상세 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_drt_commuter_station_detail
ON drt_commuter_scores(station_id, analysis_month, hour_of_day);

-- 집계 테이블 채우기 프로시저
CREATE OR REPLACE FUNCTION calculate_commuter_drt_scores(target_month DATE)
RETURNS INTEGER AS $$
DECLARE
    rec RECORD;
    station_count INTEGER := 0;
    month_start DATE;
    month_end DATE;
BEGIN
    -- 월 범위 설정
    month_start := DATE_TRUNC('month', target_month);
    month_end := month_start + INTERVAL '1 month';
    
    RAISE NOTICE 'Calculating Commuter DRT scores for: % to %', month_start, month_end;
    
    -- 기존 데이터 삭제
    DELETE FROM drt_commuter_scores WHERE analysis_month = month_start;
    
    -- 임시 테이블: TC Score 계산 (시간 집중도) - 원본 테이블에서 실제 배차수 사용
    DROP TABLE IF EXISTS temp_tc_scores;
    CREATE TEMP TABLE temp_tc_scores AS
    WITH date_classification AS (
        SELECT DISTINCT
            record_date,
            CASE 
                WHEN EXTRACT(DOW FROM record_date) BETWEEN 1 AND 5 THEN 'weekday'
                ELSE 'weekend'
            END as day_type
        FROM station_passenger_history
        WHERE record_date >= month_start AND record_date < month_end
    ),
    monthly_dispatch AS (
        -- 원본 station_passenger_history에서 실제 배차수 월평균 계산
        SELECT 
            sph.node_id as station_id,
            sph.hour as hour_of_day,
            AVG(sph.dispatch_count) as avg_dispatch_count,  -- 실제 배차수 사용
            COUNT(DISTINCT sph.record_date) as operating_days
        FROM station_passenger_history sph
        JOIN date_classification dc ON sph.record_date = dc.record_date
        WHERE sph.record_date >= month_start 
            AND sph.record_date < month_end
            AND dc.day_type = 'weekday'  -- 출퇴근형이므로 평일만
        GROUP BY sph.node_id, sph.hour
    ),
    daily_max_dispatch AS (
        SELECT 
            station_id,
            MAX(avg_dispatch_count) as max_daily_dispatch
        FROM monthly_dispatch
        GROUP BY station_id
    )
    SELECT 
        md.station_id,
        md.hour_of_day,
        md.avg_dispatch_count,
        dmd.max_daily_dispatch,
        md.operating_days, -- Raw 데이터 참조용
        CASE 
            WHEN dmd.max_daily_dispatch > 0 THEN 
                md.avg_dispatch_count::DECIMAL / dmd.max_daily_dispatch
            ELSE 0
        END as tc_score
    FROM monthly_dispatch md
    JOIN daily_max_dispatch dmd ON md.station_id = dmd.station_id;
    
    RAISE NOTICE 'TC scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_tc_scores);
    
    -- 임시 테이블: PDR Score 계산 (피크 수요 비율) - mv_station_hourly_patterns 활용  
    DROP TABLE IF EXISTS temp_pdr_scores;
    CREATE TEMP TABLE temp_pdr_scores AS
    WITH monthly_traffic AS (
        -- mv_station_hourly_patterns에서 직접 활용 (이미 월별 집계됨)
        SELECT 
            station_id,
            hour as hour_of_day,
            -- PDR은 승하차 수요 기준이므로 총 승하차수를 운영일수로 나눠 일평균 계산
            (total_ride + total_alight) / GREATEST(operating_days, 1) as avg_traffic_count,
            operating_days -- 디버깅용
        FROM mv_station_hourly_patterns
        WHERE month_date = month_start
            AND day_type = 'weekday' -- 출퇴근형이므로 평일 기준
    ),
    daily_max_traffic AS (
        SELECT 
            station_id,
            MAX(avg_traffic_count) as max_daily_traffic
        FROM monthly_traffic
        GROUP BY station_id
    )
    SELECT 
        mt.station_id,
        mt.hour_of_day,
        mt.avg_traffic_count,
        dmt.max_daily_traffic,
        mt.operating_days, -- Raw 데이터 참조용
        CASE 
            WHEN dmt.max_daily_traffic > 0 THEN 
                mt.avg_traffic_count::DECIMAL / dmt.max_daily_traffic
            ELSE 0
        END as pdr_score
    FROM monthly_traffic mt
    JOIN daily_max_traffic dmt ON mt.station_id = dmt.station_id;
    
    RAISE NOTICE 'PDR scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_pdr_scores);
    
    -- 임시 테이블: RU Score 계산 (노선 활용도 - FROM+TO 방식)
    DROP TABLE IF EXISTS temp_ru_scores;
    CREATE TEMP TABLE temp_ru_scores AS
    WITH station_section_traffic AS (
        -- 구간별 승객수: FROM+TO 방식으로 정류장이 포함된 모든 구간의 승객수 합계
        SELECT 
            sm.node_id as station_id,
            SUM(sph.passenger_count) as section_passenger_sum
        FROM spatial_mapping sm
        JOIN section_passenger_history sph ON (
            sm.node_id = sph.from_node_id OR sm.node_id = sph.to_node_id
        )
        WHERE sph.record_date >= month_start
            AND sph.record_date < month_end
        GROUP BY sm.node_id
    ),
    -- 구간별 승객수가 없는 정류장은 승하차합 기준 계산 - mv_station_hourly_patterns 활용
    station_ride_traffic AS (
        SELECT 
            station_id,
            -- 평일 기준 월간 총 승하차수 (출퇴근형이므로)
            SUM(total_ride + total_alight) as ride_traffic_sum
        FROM mv_station_hourly_patterns
        WHERE month_date = month_start
            AND day_type = 'weekday'
        GROUP BY station_id
    ),
    -- 구간별 승객수 Min-Max 값
    section_min_max AS (
        SELECT 
            MIN(section_passenger_sum) as section_min,
            MAX(section_passenger_sum) as section_max
        FROM station_section_traffic
        WHERE section_passenger_sum > 0
    ),
    -- 승하차합 Min-Max 값 (구간별 데이터 없는 경우 대비)
    ride_min_max AS (
        SELECT 
            MIN(ride_traffic_sum) as ride_min,
            MAX(ride_traffic_sum) as ride_max
        FROM station_ride_traffic
        WHERE ride_traffic_sum > 0
    )
    SELECT 
        sm.node_id as station_id,
        COALESCE(sst.section_passenger_sum, 0) as section_passenger_sum,
        COALESCE(srt.ride_traffic_sum, 0) as ride_traffic_sum,
        CASE 
            -- 구간별 승객수가 있는 경우: 구간별 Min-Max 정규화
            WHEN sst.section_passenger_sum IS NOT NULL AND smm.section_max > smm.section_min THEN
                (sst.section_passenger_sum - smm.section_min)::DECIMAL / (smm.section_max - smm.section_min)
            -- 구간별 승객수가 없고 승하차합이 있는 경우: 승하차합 Min-Max 정규화  
            WHEN sst.section_passenger_sum IS NULL AND srt.ride_traffic_sum IS NOT NULL 
                 AND rmm.ride_max > rmm.ride_min THEN
                (srt.ride_traffic_sum - rmm.ride_min)::DECIMAL / (rmm.ride_max - rmm.ride_min)
            -- 데이터가 없는 경우: 0점
            ELSE 0
        END as ru_score
    FROM spatial_mapping sm
    CROSS JOIN section_min_max smm
    CROSS JOIN ride_min_max rmm
    LEFT JOIN station_section_traffic sst ON sm.node_id = sst.station_id
    LEFT JOIN station_ride_traffic srt ON sm.node_id = srt.station_id;
    
    RAISE NOTICE 'RU scores calculated for % stations', (SELECT COUNT(*) FROM temp_ru_scores);
    
    -- 최종 집계 테이블에 데이터 삽입
    INSERT INTO drt_commuter_scores (
        station_id, district_name, analysis_month, hour_of_day,
        tc_score, pdr_score, ru_score, pcw_score,
        avg_dispatch_count, max_daily_dispatch, avg_traffic_count, max_daily_traffic,
        section_passenger_sum, total_drt_score, created_at
    )
    SELECT 
        all_stations.station_id,
        COALESCE(mv.district_name, '기타') as district_name,
        month_start as analysis_month,
        generate_series.hour_of_day,
        COALESCE(tc.tc_score, 0) as tc_score,
        COALESCE(pdr.pdr_score, 0) as pdr_score,
        COALESCE(ru.ru_score, 0) as ru_score,
        1.0 as pcw_score, -- POI 가중치는 나중에 서비스레이어에서 하드코딩
        COALESCE(tc.avg_dispatch_count, 0) as avg_dispatch_count,
        COALESCE(tc.max_daily_dispatch, 0) as max_daily_dispatch,
        COALESCE(pdr.avg_traffic_count, 0) as avg_traffic_count,
        COALESCE(pdr.max_daily_traffic, 0) as max_daily_traffic,
        COALESCE(ru.section_passenger_sum, 0) as section_passenger_sum,
        -- Total DRT Score = (TC*0.4 + PDR*0.4 + RU*0.2) * PCW * 100
        (COALESCE(tc.tc_score, 0) * 0.4 + 
         COALESCE(pdr.pdr_score, 0) * 0.4 + 
         COALESCE(ru.ru_score, 0) * 0.2) * 1.0 * 100 as total_drt_score,
        CURRENT_TIMESTAMP as created_at
    FROM (
        -- 24시간 모든 시간대 생성 (mv_station_hourly_patterns 평일 데이터가 있는 정류장만)
        SELECT DISTINCT station_id FROM mv_station_hourly_patterns
        WHERE month_date = month_start AND day_type = 'weekday'
    ) all_stations
    CROSS JOIN generate_series(0, 23) as generate_series(hour_of_day)
    LEFT JOIN temp_tc_scores tc ON all_stations.station_id = tc.station_id 
                                   AND generate_series.hour_of_day = tc.hour_of_day
    LEFT JOIN temp_pdr_scores pdr ON all_stations.station_id = pdr.station_id
                                     AND generate_series.hour_of_day = pdr.hour_of_day  
    LEFT JOIN temp_ru_scores ru ON all_stations.station_id = ru.station_id
    LEFT JOIN mv_station_hourly_patterns mv ON all_stations.station_id = mv.station_id 
                                               AND mv.month_date = month_start 
                                               AND mv.day_type = 'weekday' 
                                               AND mv.hour = generate_series.hour_of_day;
    
    -- 결과 카운트
    GET DIAGNOSTICS station_count = ROW_COUNT;
    
    RAISE NOTICE 'Commuter DRT scores calculated for % records', station_count;
    
    RETURN station_count;
END;
$$ LANGUAGE plpgsql;

-- 테이블 설명 추가
COMMENT ON TABLE drt_commuter_scores IS '출퇴근형 DRT Score 월별 시간대별 집계 테이블';
COMMENT ON COLUMN drt_commuter_scores.tc_score IS 'TC 시간 집중도: 특정시간 배차수 / 일일최대 배차수 (월평균)';
COMMENT ON COLUMN drt_commuter_scores.pdr_score IS 'PDR 피크 수요 비율: 특정시간 승하차수 / 일일최대 승하차수 (월평균)';
COMMENT ON COLUMN drt_commuter_scores.ru_score IS 'RU 노선 활용도: 구간별 승객수 Min-Max 정규화 또는 승하차합 Min-Max';
COMMENT ON COLUMN drt_commuter_scores.pcw_score IS 'PCW POI 카테고리 가중치: 서비스레이어에서 하드코딩 예정';
COMMENT ON COLUMN drt_commuter_scores.total_drt_score IS '출퇴근형 총 DRT 점수: (TC*0.4 + PDR*0.4 + RU*0.2) * PCW * 100';

-- 사용 예시 쿼리 (주석)
/*
-- 2024년 7월 집계 실행
SELECT calculate_commuter_drt_scores('2024-07-01'::DATE);

-- 특정 구의 DRT 점수 조회 (히트맵용)
SELECT 
    dcs.station_id,
    si.station_name,
    si.latitude,
    si.longitude, 
    MAX(dcs.total_drt_score) as peak_drt_score,
    (ARRAY_AGG(dcs.hour_of_day ORDER BY dcs.total_drt_score DESC))[1] as peak_hour
FROM drt_commuter_scores dcs
JOIN station_info si ON dcs.station_id = si.node_id
WHERE si.district_name = '강남구'
    AND dcs.analysis_month = '2024-07-01'
GROUP BY dcs.station_id, si.station_name, si.latitude, si.longitude
ORDER BY peak_drt_score DESC;
*/