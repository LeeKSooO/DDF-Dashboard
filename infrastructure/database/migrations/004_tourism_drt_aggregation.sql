-- ============================================
-- 관광특화형 DRT Score 집계 테이블 생성
-- 월평균 기준 Feature 계산 및 집계
-- 관광시간대 가중치 및 주말/공휴일 기준
-- ============================================

-- 관광특화형 DRT Score 집계 테이블
CREATE TABLE IF NOT EXISTS drt_tourism_scores (
    station_id VARCHAR(20) NOT NULL,
    district_name VARCHAR(50) NOT NULL,  -- 구명 (API 필터링용)
    analysis_month DATE NOT NULL,  -- YYYY-MM-01 형식
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    
    -- Feature Scores (0-1 정규화, 관광시간 가중치 적용)
    tc_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 관광 집중도 (t시 배차수/일일최대배차수, 10-16시 1.2배)
    tdr_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,   -- 관광 수요 비율 (t시 승하차수/일일최대승하차수, 10-16시 1.1배)
    ru_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 구간 이용률 (t시 구간승객밀도/1000, 관광시간 60%/비관광시간 40%)
    pcw_score DECIMAL(8,6) NOT NULL DEFAULT 1.0,   -- POI 관광 가중치 (하드코딩 예정)
    
    -- Raw Data (참조용)
    avg_dispatch_count DECIMAL(10,2) DEFAULT 0,     -- 월평균 시간대별 배차수 (주말/공휴일)
    max_daily_dispatch DECIMAL(10,2) DEFAULT 0,     -- 월평균 일일 최대 배차수 (주말/공휴일)
    avg_traffic_count DECIMAL(10,2) DEFAULT 0,      -- 월평균 시간대별 승하차수 (주말/공휴일)
    max_daily_traffic DECIMAL(10,2) DEFAULT 0,      -- 월평균 일일 최대 승하차수 (주말/공휴일)
    section_passenger_density DECIMAL(10,2) DEFAULT 0, -- 시간대별 구간승객밀도 (승객수/1000)
    is_tourism_time BOOLEAN DEFAULT FALSE,          -- 관광시간대 여부 (10-16시)
    
    -- Total DRT Score (0-100)
    total_drt_score DECIMAL(8,4) NOT NULL DEFAULT 0, -- (TC_t*0.35 + TDR_t*0.35 + RU_t*0.3) * PCW * 100
    
    -- 메타데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (station_id, analysis_month, hour_of_day),
    FOREIGN KEY (station_id) REFERENCES bus_stops(node_id)
);

-- 성능 최적화 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_drt_tourism_scores_analysis_month ON drt_tourism_scores(analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_tourism_scores_station_month ON drt_tourism_scores(station_id, analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_tourism_scores_total_score ON drt_tourism_scores(analysis_month, total_drt_score DESC);
CREATE INDEX IF NOT EXISTS idx_drt_tourism_scores_tourism_time ON drt_tourism_scores(analysis_month, is_tourism_time, total_drt_score DESC);

-- DRT API용 복합 인덱스 추가 (히트맵 조회 최적화)
CREATE INDEX IF NOT EXISTS idx_drt_tourism_district_heatmap 
ON drt_tourism_scores(analysis_month, station_id)
INCLUDE (hour_of_day, total_drt_score, is_tourism_time);

-- 정류장 상세 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_drt_tourism_station_detail
ON drt_tourism_scores(station_id, analysis_month, hour_of_day);

-- 집계 테이블 채우기 프로시저
CREATE OR REPLACE FUNCTION calculate_tourism_drt_scores(target_month DATE)
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
    
    RAISE NOTICE 'Calculating Tourism DRT scores for: % to %', month_start, month_end;
    
    -- 기존 데이터 삭제
    DELETE FROM drt_tourism_scores WHERE analysis_month = month_start;
    
    -- 임시 테이블: TC_t Score 계산 (관광 집중도) - 주말/공휴일 기준
    DROP TABLE IF EXISTS temp_tc_t_scores;
    CREATE TEMP TABLE temp_tc_t_scores AS
    WITH date_classification AS (
        SELECT DISTINCT
            record_date,
            CASE 
                WHEN EXTRACT(DOW FROM record_date) IN (0, 6) THEN 'weekend'  -- 토요일(6), 일요일(0)
                ELSE 'weekday'
            END as day_type
        FROM station_passenger_history
        WHERE record_date >= month_start AND record_date < month_end
    ),
    monthly_dispatch AS (
        -- 주말/공휴일 기준 배차수 월평균 계산
        SELECT 
            sph.node_id as station_id,
            sph.hour as hour_of_day,
            AVG(sph.dispatch_count) as avg_dispatch_count,
            COUNT(DISTINCT sph.record_date) as operating_days,
            -- 관광시간대 여부 (10-16시)
            (sph.hour BETWEEN 10 AND 16) as is_tourism_time
        FROM station_passenger_history sph
        JOIN date_classification dc ON sph.record_date = dc.record_date
        WHERE sph.record_date >= month_start 
            AND sph.record_date < month_end
            AND dc.day_type = 'weekend'  -- 관광특화형이므로 주말만
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
        md.operating_days,
        md.is_tourism_time,
        CASE 
            WHEN dmd.max_daily_dispatch > 0 THEN 
                -- 관광시간대(10-16시)는 1.2배 가중치 적용
                CASE 
                    WHEN md.is_tourism_time THEN
                        LEAST((md.avg_dispatch_count::DECIMAL / dmd.max_daily_dispatch) * 1.2, 1.0)
                    ELSE 
                        md.avg_dispatch_count::DECIMAL / dmd.max_daily_dispatch
                END
            ELSE 0
        END as tc_t_score
    FROM monthly_dispatch md
    JOIN daily_max_dispatch dmd ON md.station_id = dmd.station_id;
    
    RAISE NOTICE 'TC_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_tc_t_scores);
    
    -- 임시 테이블: TDR_t Score 계산 (관광 수요 비율) - 주말/공휴일 기준
    DROP TABLE IF EXISTS temp_tdr_t_scores;
    CREATE TEMP TABLE temp_tdr_t_scores AS
    WITH monthly_traffic AS (
        -- mv_station_hourly_patterns에서 주말 데이터 활용
        SELECT 
            station_id,
            hour as hour_of_day,
            -- TDR은 승하차 수요 기준이므로 총 승하차수를 운영일수로 나눠 일평균 계산
            (total_ride + total_alight) / GREATEST(operating_days, 1) as avg_traffic_count,
            operating_days,
            -- 관광시간대 여부 (10-16시)
            (hour BETWEEN 10 AND 16) as is_tourism_time
        FROM mv_station_hourly_patterns
        WHERE month_date = month_start
            AND day_type = 'weekend' -- 관광특화형이므로 주말 기준
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
        mt.operating_days,
        mt.is_tourism_time,
        CASE 
            WHEN dmt.max_daily_traffic > 0 THEN 
                -- 관광시간대(10-16시)는 1.1배 가중치 적용
                CASE 
                    WHEN mt.is_tourism_time THEN
                        LEAST((mt.avg_traffic_count::DECIMAL / dmt.max_daily_traffic) * 1.1, 1.0)
                    ELSE 
                        mt.avg_traffic_count::DECIMAL / dmt.max_daily_traffic
                END
            ELSE 0
        END as tdr_t_score
    FROM monthly_traffic mt
    JOIN daily_max_traffic dmt ON mt.station_id = dmt.station_id;
    
    RAISE NOTICE 'TDR_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_tdr_t_scores);
    
    -- 임시 테이블: RU_t Score 계산 (구간 이용률) - 시간대별 구간승객밀도
    DROP TABLE IF EXISTS temp_ru_t_scores;
    CREATE TEMP TABLE temp_ru_t_scores AS
    WITH hourly_section_traffic AS (
        -- 시간대별 구간별 승객수 집계 (주말 기준)
        SELECT 
            sm.node_id as station_id,
            sph.hour as hour_of_day,
            -- 구간별 승객수: FROM+TO 방식으로 정류장이 포함된 모든 구간의 승객수 합계
            SUM(sph.passenger_count) as hourly_section_passengers,
            -- 관광시간대 여부 (10-16시)
            (sph.hour BETWEEN 10 AND 16) as is_tourism_time
        FROM spatial_mapping sm
        JOIN section_passenger_history sph ON (
            sm.node_id = sph.from_node_id OR sm.node_id = sph.to_node_id
        )
        JOIN (
            SELECT DISTINCT record_date
            FROM station_passenger_history
            WHERE record_date >= month_start 
                AND record_date < month_end
                AND EXTRACT(DOW FROM record_date) IN (0, 6) -- 주말만
        ) weekend_dates ON sph.record_date = weekend_dates.record_date
        WHERE sph.record_date >= month_start
            AND sph.record_date < month_end
        GROUP BY sm.node_id, sph.hour
    ),
    -- 구간별 승객수가 없는 정류장은 승하차합으로 대체
    hourly_ride_traffic AS (
        SELECT 
            sph.node_id as station_id,
            sph.hour as hour_of_day,
            AVG(sph.ride_passenger + sph.alight_passenger) as hourly_ride_traffic,
            (sph.hour BETWEEN 10 AND 16) as is_tourism_time
        FROM station_passenger_history sph
        WHERE sph.record_date >= month_start
            AND sph.record_date < month_end
            AND EXTRACT(DOW FROM sph.record_date) IN (0, 6) -- 주말만
        GROUP BY sph.node_id, sph.hour
    )
    SELECT 
        sm.node_id as station_id,
        gs.hour_of_day,
        COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0) as raw_passenger_data,
        (gs.hour_of_day BETWEEN 10 AND 16) as is_tourism_time,
        -- RU_t Score: 구간승객밀도/1000 기준, 관광시간 60% / 비관광시간 40% 분배
        CASE 
            WHEN COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0) > 0 THEN
                CASE 
                    WHEN gs.hour_of_day BETWEEN 10 AND 16 THEN
                        -- 관광시간: 60% 분배
                        LEAST((COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0) / 1000.0) * 0.6, 1.0)
                    ELSE 
                        -- 비관광시간: 40% 분배
                        LEAST((COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0) / 1000.0) * 0.4, 1.0)
                END
            ELSE 0
        END as ru_t_score
    FROM spatial_mapping sm
    CROSS JOIN generate_series(0, 23) as gs(hour_of_day)
    LEFT JOIN hourly_section_traffic hst ON sm.node_id = hst.station_id 
                                           AND gs.hour_of_day = hst.hour_of_day
    LEFT JOIN hourly_ride_traffic hrt ON sm.node_id = hrt.station_id 
                                        AND gs.hour_of_day = hrt.hour_of_day;
    
    RAISE NOTICE 'RU_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_ru_t_scores);
    
    -- 최종 집계 테이블에 데이터 삽입
    INSERT INTO drt_tourism_scores (
        station_id, district_name, analysis_month, hour_of_day,
        tc_t_score, tdr_t_score, ru_t_score, pcw_score,
        avg_dispatch_count, max_daily_dispatch, avg_traffic_count, max_daily_traffic,
        section_passenger_density, is_tourism_time, total_drt_score, created_at
    )
    SELECT 
        all_stations.station_id,
        COALESCE(mv.district_name, '기타') as district_name,
        month_start as analysis_month,
        generate_series.hour_of_day,
        COALESCE(tc.tc_t_score, 0) as tc_t_score,
        COALESCE(tdr.tdr_t_score, 0) as tdr_t_score,
        COALESCE(ru.ru_t_score, 0) as ru_t_score,
        1.0 as pcw_score, -- POI 가중치는 나중에 서비스레이어에서 하드코딩
        COALESCE(tc.avg_dispatch_count, 0) as avg_dispatch_count,
        COALESCE(tc.max_daily_dispatch, 0) as max_daily_dispatch,
        COALESCE(tdr.avg_traffic_count, 0) as avg_traffic_count,
        COALESCE(tdr.max_daily_traffic, 0) as max_daily_traffic,
        COALESCE(ru.raw_passenger_data / 1000.0, 0) as section_passenger_density,
        COALESCE(tc.is_tourism_time, tdr.is_tourism_time, ru.is_tourism_time, FALSE) as is_tourism_time,
        -- Total DRT Score = (TC_t*0.35 + TDR_t*0.35 + RU_t*0.3) * PCW * 100
        (COALESCE(tc.tc_t_score, 0) * 0.35 + 
         COALESCE(tdr.tdr_t_score, 0) * 0.35 + 
         COALESCE(ru.ru_t_score, 0) * 0.3) * 1.0 * 100 as total_drt_score,
        CURRENT_TIMESTAMP as created_at
    FROM (
        -- 24시간 모든 시간대 생성 (mv_station_hourly_patterns 주말 데이터가 있는 정류장만)
        SELECT DISTINCT station_id FROM mv_station_hourly_patterns
        WHERE month_date = month_start AND day_type = 'weekend'
    ) all_stations
    CROSS JOIN generate_series(0, 23) as generate_series(hour_of_day)
    LEFT JOIN temp_tc_t_scores tc ON all_stations.station_id = tc.station_id 
                                    AND generate_series.hour_of_day = tc.hour_of_day
    LEFT JOIN temp_tdr_t_scores tdr ON all_stations.station_id = tdr.station_id
                                      AND generate_series.hour_of_day = tdr.hour_of_day  
    LEFT JOIN temp_ru_t_scores ru ON all_stations.station_id = ru.station_id
                                    AND generate_series.hour_of_day = ru.hour_of_day
    LEFT JOIN mv_station_hourly_patterns mv ON all_stations.station_id = mv.station_id 
                                               AND mv.month_date = month_start 
                                               AND mv.day_type = 'weekend' 
                                               AND mv.hour = generate_series.hour_of_day;
    
    -- 결과 카운트
    GET DIAGNOSTICS station_count = ROW_COUNT;
    
    RAISE NOTICE 'Tourism DRT scores calculated for % records', station_count;
    
    RETURN station_count;
END;
$$ LANGUAGE plpgsql;

-- POI 관광 가중치 참조 테이블 (하드코딩용)
CREATE TABLE IF NOT EXISTS poi_tourism_weights (
    poi_category VARCHAR(50) PRIMARY KEY,
    weight_value DECIMAL(3,2) NOT NULL CHECK (weight_value >= 0 AND weight_value <= 1.0),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 초기 POI 가중치 데이터 삽입
INSERT INTO poi_tourism_weights (poi_category, weight_value, description) VALUES
    ('관광특구', 1.0, '관광특구 지역 최고 가중치'),
    ('고궁', 0.9, '고궁, 문화유적지 높은 관광가치'),
    ('상권', 0.8, '상업지구, 쇼핑지역 중간 관광가치'),
    ('공원', 0.7, '공원, 레저시설 기본 관광가치'),
    ('기타', 0.5, '일반지역 기본값')
ON CONFLICT (poi_category) DO UPDATE SET 
    weight_value = EXCLUDED.weight_value,
    description = EXCLUDED.description;

-- 테이블 설명 추가
COMMENT ON TABLE drt_tourism_scores IS '관광특화형 DRT Score 월별 시간대별 집계 테이블 (주말/공휴일 기준)';
COMMENT ON COLUMN drt_tourism_scores.tc_t_score IS 'TC_t 관광 집중도: t시 배차수/일일최대배차수 (10-16시 1.2배 가중)';
COMMENT ON COLUMN drt_tourism_scores.tdr_t_score IS 'TDR_t 관광 수요 비율: t시 승하차수/일일최대승하차수 (10-16시 1.1배 가중)';
COMMENT ON COLUMN drt_tourism_scores.ru_t_score IS 'RU_t 구간 이용률: t시 구간승객밀도/1000 (관광시간 60%, 비관광시간 40% 분배)';
COMMENT ON COLUMN drt_tourism_scores.pcw_score IS 'PCW POI 관광 가중치: poi_tourism_weights 테이블 참조';
COMMENT ON COLUMN drt_tourism_scores.total_drt_score IS '관광특화형 총 DRT 점수: (TC_t*0.35 + TDR_t*0.35 + RU_t*0.3) * PCW * 100';
COMMENT ON COLUMN drt_tourism_scores.is_tourism_time IS '관광시간대 여부: 10시-16시 구간';

COMMENT ON TABLE poi_tourism_weights IS 'POI 관광 가중치 참조 테이블 (서비스레이어에서 활용)';

-- 사용 예시 쿼리 (주석)
/*
-- 2024년 7월 관광특화형 집계 실행
SELECT calculate_tourism_drt_scores('2024-07-01'::DATE);

-- 특정 구의 관광 DRT 점수 조회 (히트맵용)
SELECT 
    dts.station_id,
    si.station_name,
    si.latitude,
    si.longitude, 
    MAX(dts.total_drt_score) as peak_tourism_drt_score,
    (ARRAY_AGG(dts.hour_of_day ORDER BY dts.total_drt_score DESC))[1] as peak_hour,
    SUM(CASE WHEN dts.is_tourism_time THEN 1 ELSE 0 END) as tourism_hours_count
FROM drt_tourism_scores dts
JOIN station_info si ON dts.station_id = si.node_id
WHERE si.district_name = '종로구'
    AND dts.analysis_month = '2024-07-01'
GROUP BY dts.station_id, si.station_name, si.latitude, si.longitude
ORDER BY peak_tourism_drt_score DESC;

-- 관광시간대별 DRT 점수 비교
SELECT 
    dts.hour_of_day,
    dts.is_tourism_time,
    AVG(dts.total_drt_score) as avg_drt_score,
    COUNT(*) as station_count
FROM drt_tourism_scores dts
WHERE dts.analysis_month = '2024-07-01'
GROUP BY dts.hour_of_day, dts.is_tourism_time
ORDER BY dts.hour_of_day;
*/