-- ============================================
-- 교통취약지형 DRT Score 집계 테이블 생성
-- 월평균 기준 Feature 계산 및 집계
-- 취약시간대 가중치 및 전일 기준
-- ============================================

-- 교통취약지형 DRT Score 집계 테이블
CREATE TABLE IF NOT EXISTS drt_vulnerable_scores (
    station_id VARCHAR(20) NOT NULL,
    district_name VARCHAR(50) NOT NULL,  -- 구명 (API 필터링용)
    analysis_month DATE NOT NULL,  -- YYYY-MM-01 형식
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    
    -- Feature Scores (0-1 정규화, 취약시간 가중치 적용)
    var_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 취약 접근성 비율 (t시 배차수/취약시간대 총배차수, 09-11시 1.5x, 14-16시 1.3x, 18-20시 1.2x)
    sed_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 사회 형평성 수요 (t시 승하차수/취약시간대 총승하차수, 100명미만 1.4x, 핵심시간 1.2x)
    mdi_t_score DECIMAL(8,6) NOT NULL DEFAULT 0,    -- 이동성 불리 지수 ((1000-구간승객수)/1000, 취약30%/일반70%)
    avs_score DECIMAL(8,6) NOT NULL DEFAULT 1.0,    -- 지역 취약성 점수 (하드코딩 예정)
    
    -- Raw Data (참조용)
    avg_dispatch_count DECIMAL(10,2) DEFAULT 0,     -- 월평균 시간대별 배차수 (전일)
    vulnerable_total_dispatch DECIMAL(10,2) DEFAULT 0, -- 취약시간대 총 배차수
    avg_traffic_count DECIMAL(10,2) DEFAULT 0,      -- 월평균 시간대별 승하차수 (전일)
    vulnerable_total_traffic DECIMAL(10,2) DEFAULT 0,  -- 취약시간대 총 승하차수
    section_passenger_count BIGINT DEFAULT 0,       -- 시간대별 구간승객수
    is_vulnerable_time BOOLEAN DEFAULT FALSE,       -- 취약시간대 여부 (09-11, 14-16, 18-20시)
    vulnerable_category VARCHAR(20),                 -- 취약시간 카테고리 (medical, welfare, evening)
    
    -- Total DRT Score (0-100)
    total_drt_score DECIMAL(8,4) NOT NULL DEFAULT 0, -- (VAR_t*0.3 + SED_t*0.3 + MDI_t*0.4) * AVS * 100
    
    -- 메타데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (station_id, analysis_month, hour_of_day)
);

-- 성능 최적화 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_scores_analysis_month ON drt_vulnerable_scores(analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_scores_station_month ON drt_vulnerable_scores(station_id, analysis_month);
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_scores_total_score ON drt_vulnerable_scores(analysis_month, total_drt_score DESC);
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_scores_vulnerable_time ON drt_vulnerable_scores(analysis_month, is_vulnerable_time, total_drt_score DESC);

-- DRT API용 복합 인덱스 추가 (히트맵 조회 최적화)
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_district_heatmap 
ON drt_vulnerable_scores(analysis_month, station_id)
INCLUDE (hour_of_day, total_drt_score, is_vulnerable_time, vulnerable_category);

-- 정류장 상세 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_station_detail
ON drt_vulnerable_scores(station_id, analysis_month, hour_of_day);

-- 취약시간대별 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_drt_vulnerable_category_lookup
ON drt_vulnerable_scores(analysis_month, vulnerable_category, total_drt_score DESC);

-- 집계 테이블 채우기 프로시저
CREATE OR REPLACE FUNCTION calculate_vulnerable_drt_scores(target_month DATE)
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
    
    RAISE NOTICE 'Calculating Vulnerable DRT scores for: % to %', month_start, month_end;
    
    -- 기존 데이터 삭제
    DELETE FROM drt_vulnerable_scores WHERE analysis_month = month_start;
    
    -- 임시 테이블: VAR_t Score 계산 (취약 접근성 비율) - 전일 기준
    DROP TABLE IF EXISTS temp_var_t_scores;
    CREATE TEMP TABLE temp_var_t_scores AS
    WITH monthly_dispatch AS (
        -- 전일 기준 배차수 월평균 계산
        SELECT 
            sph.node_id as station_id,
            sph.hour as hour_of_day,
            AVG(sph.dispatch_count) as avg_dispatch_count,
            COUNT(DISTINCT sph.record_date) as operating_days,
            -- 취약시간대 분류
            CASE 
                WHEN sph.hour BETWEEN 9 AND 11 THEN 'medical'    -- 의료시간 09-11시
                WHEN sph.hour BETWEEN 14 AND 16 THEN 'welfare'   -- 복지시간 14-16시  
                WHEN sph.hour BETWEEN 18 AND 20 THEN 'evening'   -- 저녁시간 18-20시
                ELSE 'normal'
            END as vulnerable_category,
            (sph.hour BETWEEN 9 AND 11 OR sph.hour BETWEEN 14 AND 16 OR sph.hour BETWEEN 18 AND 20) as is_vulnerable_time
        FROM station_passenger_history sph
        WHERE sph.record_date >= month_start 
            AND sph.record_date < month_end
        GROUP BY sph.node_id, sph.hour
    ),
    vulnerable_total_dispatch AS (
        -- 정류장별 취약시간대 총 배차수 계산
        SELECT 
            station_id,
            SUM(avg_dispatch_count) as vulnerable_total_dispatch
        FROM monthly_dispatch
        WHERE is_vulnerable_time = TRUE
        GROUP BY station_id
    )
    SELECT 
        md.station_id,
        md.hour_of_day,
        md.avg_dispatch_count,
        vtd.vulnerable_total_dispatch,
        md.operating_days,
        md.vulnerable_category,
        md.is_vulnerable_time,
        CASE 
            WHEN vtd.vulnerable_total_dispatch > 0 THEN 
                -- 취약시간대별 가중치 적용
                CASE 
                    WHEN md.vulnerable_category = 'medical' THEN
                        LEAST((md.avg_dispatch_count::DECIMAL / vtd.vulnerable_total_dispatch) * 1.5, 1.0)  -- 의료시간 1.5배
                    WHEN md.vulnerable_category = 'welfare' THEN
                        LEAST((md.avg_dispatch_count::DECIMAL / vtd.vulnerable_total_dispatch) * 1.3, 1.0)  -- 복지시간 1.3배
                    WHEN md.vulnerable_category = 'evening' THEN
                        LEAST((md.avg_dispatch_count::DECIMAL / vtd.vulnerable_total_dispatch) * 1.2, 1.0)  -- 저녁시간 1.2배
                    ELSE 
                        md.avg_dispatch_count::DECIMAL / vtd.vulnerable_total_dispatch  -- 일반시간
                END
            ELSE 0
        END as var_t_score
    FROM monthly_dispatch md
    LEFT JOIN vulnerable_total_dispatch vtd ON md.station_id = vtd.station_id;
    
    RAISE NOTICE 'VAR_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_var_t_scores);
    
    -- 임시 테이블: SED_t Score 계산 (사회 형평성 수요) - 전일 기준
    DROP TABLE IF EXISTS temp_sed_t_scores;
    CREATE TEMP TABLE temp_sed_t_scores AS
    WITH monthly_traffic AS (
        -- mv_station_hourly_patterns에서 전일 데이터 활용 (weekday + weekend 합계)
        SELECT 
            station_id,
            hour as hour_of_day,
            -- SED는 승하차 수요 기준이므로 총 승하차수를 운영일수로 나눠 일평균 계산
            (SUM(total_ride + total_alight) / SUM(operating_days)) as avg_traffic_count,
            SUM(operating_days) as total_operating_days,
            -- 취약시간대 분류
            CASE 
                WHEN hour BETWEEN 9 AND 11 THEN 'medical'
                WHEN hour BETWEEN 14 AND 16 THEN 'welfare'
                WHEN hour BETWEEN 18 AND 20 THEN 'evening'
                ELSE 'normal'
            END as vulnerable_category,
            (hour BETWEEN 9 AND 11 OR hour BETWEEN 14 AND 16 OR hour BETWEEN 18 AND 20) as is_vulnerable_time,
            -- 저이용 구간 여부 (100명 미만)
            ((SUM(total_ride + total_alight) / SUM(operating_days)) < 100) as is_low_usage
        FROM mv_station_hourly_patterns
        WHERE month_date = month_start  -- 전일 데이터 (weekday + weekend)
        GROUP BY station_id, hour
    ),
    vulnerable_total_traffic AS (
        -- 정류장별 취약시간대 총 승하차수 계산
        SELECT 
            station_id,
            SUM(avg_traffic_count) as vulnerable_total_traffic
        FROM monthly_traffic
        WHERE is_vulnerable_time = TRUE
        GROUP BY station_id
    )
    SELECT 
        mt.station_id,
        mt.hour_of_day,
        mt.avg_traffic_count,
        vtt.vulnerable_total_traffic,
        mt.total_operating_days,
        mt.vulnerable_category,
        mt.is_vulnerable_time,
        mt.is_low_usage,
        CASE 
            WHEN vtt.vulnerable_total_traffic > 0 THEN 
                -- 가중치 적용: 저이용구간 1.4배, 핵심취약시간(09,14,18시) 1.2배
                CASE 
                    WHEN mt.is_low_usage AND mt.hour_of_day IN (9, 14, 18) THEN
                        LEAST((mt.avg_traffic_count::DECIMAL / vtt.vulnerable_total_traffic) * 1.4 * 1.2, 1.0)  -- 저이용 + 핵심시간
                    WHEN mt.is_low_usage THEN
                        LEAST((mt.avg_traffic_count::DECIMAL / vtt.vulnerable_total_traffic) * 1.4, 1.0)      -- 저이용만
                    WHEN mt.hour_of_day IN (9, 14, 18) THEN
                        LEAST((mt.avg_traffic_count::DECIMAL / vtt.vulnerable_total_traffic) * 1.2, 1.0)      -- 핵심시간만
                    ELSE 
                        mt.avg_traffic_count::DECIMAL / vtt.vulnerable_total_traffic                          -- 일반
                END
            ELSE 0
        END as sed_t_score
    FROM monthly_traffic mt
    LEFT JOIN vulnerable_total_traffic vtt ON mt.station_id = vtt.station_id;
    
    RAISE NOTICE 'SED_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_sed_t_scores);
    
    -- 임시 테이블: MDI_t Score 계산 (이동성 불리 지수) - 역전 지수
    DROP TABLE IF EXISTS temp_mdi_t_scores;
    CREATE TEMP TABLE temp_mdi_t_scores AS
    WITH hourly_section_traffic AS (
        -- 시간대별 구간별 승객수 집계 (전일 기준)
        SELECT 
            sm.node_id as station_id,
            sph.hour as hour_of_day,
            -- 구간별 승객수: FROM+TO 방식으로 정류장이 포함된 모든 구간의 승객수 합계
            SUM(sph.passenger_count) as hourly_section_passengers,
            -- 취약시간대 분류
            CASE 
                WHEN sph.hour BETWEEN 9 AND 11 THEN 'medical'
                WHEN sph.hour BETWEEN 14 AND 16 THEN 'welfare'
                WHEN sph.hour BETWEEN 18 AND 20 THEN 'evening'
                ELSE 'normal'
            END as vulnerable_category,
            (sph.hour BETWEEN 9 AND 11 OR sph.hour BETWEEN 14 AND 16 OR sph.hour BETWEEN 18 AND 20) as is_vulnerable_time
        FROM spatial_mapping sm
        JOIN section_passenger_history sph ON (
            sm.node_id = sph.from_node_id OR sm.node_id = sph.to_node_id
        )
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
            CASE 
                WHEN sph.hour BETWEEN 9 AND 11 THEN 'medical'
                WHEN sph.hour BETWEEN 14 AND 16 THEN 'welfare'
                WHEN sph.hour BETWEEN 18 AND 20 THEN 'evening'
                ELSE 'normal'
            END as vulnerable_category,
            (sph.hour BETWEEN 9 AND 11 OR sph.hour BETWEEN 14 AND 16 OR sph.hour BETWEEN 18 AND 20) as is_vulnerable_time
        FROM station_passenger_history sph
        WHERE sph.record_date >= month_start
            AND sph.record_date < month_end
        GROUP BY sph.node_id, sph.hour
    )
    SELECT 
        sm.node_id as station_id,
        gs.hour_of_day,
        COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0) as raw_passenger_data,
        CASE 
            WHEN gs.hour_of_day BETWEEN 9 AND 11 THEN 'medical'
            WHEN gs.hour_of_day BETWEEN 14 AND 16 THEN 'welfare'
            WHEN gs.hour_of_day BETWEEN 18 AND 20 THEN 'evening'
            ELSE 'normal'
        END as vulnerable_category,
        (gs.hour_of_day BETWEEN 9 AND 11 OR gs.hour_of_day BETWEEN 14 AND 16 OR gs.hour_of_day BETWEEN 18 AND 20) as is_vulnerable_time,
        -- MDI_t Score: 역전 지수 (1000 - 구간승객수) / 1000, 취약시간 30% / 일반시간 70%
        CASE 
            WHEN gs.hour_of_day BETWEEN 9 AND 11 OR gs.hour_of_day BETWEEN 14 AND 16 OR gs.hour_of_day BETWEEN 18 AND 20 THEN
                -- 취약시간: 30% 분배 (낮을수록 높은 점수)
                ((1000 - LEAST(COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0), 1000)) / 1000.0) * 0.3
            ELSE 
                -- 일반시간: 70% 분배
                ((1000 - LEAST(COALESCE(hst.hourly_section_passengers, hrt.hourly_ride_traffic, 0), 1000)) / 1000.0) * 0.7
        END as mdi_t_score
    FROM spatial_mapping sm
    CROSS JOIN generate_series(0, 23) as gs(hour_of_day)
    LEFT JOIN hourly_section_traffic hst ON sm.node_id = hst.station_id 
                                           AND gs.hour_of_day = hst.hour_of_day
    LEFT JOIN hourly_ride_traffic hrt ON sm.node_id = hrt.station_id 
                                        AND gs.hour_of_day = hrt.hour_of_day
    WHERE EXISTS (
        -- mv_station_hourly_patterns에 데이터가 있는 정류장만
        SELECT 1 FROM mv_station_hourly_patterns mv 
        WHERE mv.station_id = sm.node_id AND mv.month_date = month_start
    );
    
    RAISE NOTICE 'MDI_t scores calculated for % station-hour combinations', (SELECT COUNT(*) FROM temp_mdi_t_scores);
    
    -- 최종 집계 테이블에 데이터 삽입
    INSERT INTO drt_vulnerable_scores (
        station_id, district_name, analysis_month, hour_of_day,
        var_t_score, sed_t_score, mdi_t_score, avs_score,
        avg_dispatch_count, vulnerable_total_dispatch, avg_traffic_count, vulnerable_total_traffic,
        section_passenger_count, is_vulnerable_time, vulnerable_category, total_drt_score, created_at
    )
    SELECT 
        all_stations.station_id,
        COALESCE(mv.district_name, '기타') as district_name,
        month_start as analysis_month,
        generate_series.hour_of_day,
        COALESCE(var.var_t_score, 0) as var_t_score,
        COALESCE(sed.sed_t_score, 0) as sed_t_score,
        COALESCE(mdi.mdi_t_score, 0) as mdi_t_score,
        1.0 as avs_score, -- AVS 가중치는 나중에 서비스레이어에서 하드코딩
        COALESCE(var.avg_dispatch_count, 0) as avg_dispatch_count,
        COALESCE(var.vulnerable_total_dispatch, 0) as vulnerable_total_dispatch,
        COALESCE(sed.avg_traffic_count, 0) as avg_traffic_count,
        COALESCE(sed.vulnerable_total_traffic, 0) as vulnerable_total_traffic,
        COALESCE(mdi.raw_passenger_data, 0) as section_passenger_count,
        COALESCE(var.is_vulnerable_time, sed.is_vulnerable_time, mdi.is_vulnerable_time, FALSE) as is_vulnerable_time,
        COALESCE(var.vulnerable_category, sed.vulnerable_category, mdi.vulnerable_category, 'normal') as vulnerable_category,
        -- Total DRT Score = (VAR_t*0.3 + SED_t*0.3 + MDI_t*0.4) * AVS * 100
        (COALESCE(var.var_t_score, 0) * 0.3 + 
         COALESCE(sed.sed_t_score, 0) * 0.3 + 
         COALESCE(mdi.mdi_t_score, 0) * 0.4) * 1.0 * 100 as total_drt_score,
        CURRENT_TIMESTAMP as created_at
    FROM (
        -- 24시간 모든 시간대 생성 (mv_station_hourly_patterns 전일 데이터가 있는 정류장만)
        SELECT DISTINCT station_id FROM mv_station_hourly_patterns
        WHERE month_date = month_start AND day_type = 'weekday'
        UNION
        SELECT DISTINCT station_id FROM mv_station_hourly_patterns  
        WHERE month_date = month_start AND day_type = 'weekend'
    ) all_stations
    CROSS JOIN generate_series(0, 23) as generate_series(hour_of_day)
    LEFT JOIN temp_var_t_scores var ON all_stations.station_id = var.station_id 
                                      AND generate_series.hour_of_day = var.hour_of_day
    LEFT JOIN temp_sed_t_scores sed ON all_stations.station_id = sed.station_id
                                      AND generate_series.hour_of_day = sed.hour_of_day  
    LEFT JOIN temp_mdi_t_scores mdi ON all_stations.station_id = mdi.station_id
                                      AND generate_series.hour_of_day = mdi.hour_of_day
    LEFT JOIN (
        SELECT DISTINCT station_id, hour, MAX(district_name) as district_name 
        FROM mv_station_hourly_patterns 
        WHERE month_date = month_start
        GROUP BY station_id, hour
    ) mv ON all_stations.station_id = mv.station_id AND mv.hour = generate_series.hour_of_day;
    
    -- 결과 카운트
    GET DIAGNOSTICS station_count = ROW_COUNT;
    
    RAISE NOTICE 'Vulnerable DRT scores calculated for % records', station_count;
    
    RETURN station_count;
END;
$$ LANGUAGE plpgsql;

-- 지역 취약성 점수 참조 테이블 (하드코딩용)
CREATE TABLE IF NOT EXISTS area_vulnerability_scores (
    poi_category VARCHAR(50) PRIMARY KEY,
    vulnerability_score DECIMAL(3,2) NOT NULL CHECK (vulnerability_score >= 0 AND vulnerability_score <= 1.0),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 초기 취약성 점수 데이터 삽입 (취약할수록 높은 점수)
INSERT INTO area_vulnerability_scores (poi_category, vulnerability_score, description) VALUES
    ('인구밀집', 0.9, '인구 밀집 지역 - 교통 수요 대비 서비스 부족'),
    ('공원', 0.8, '공원, 레저시설 - 접근성 제약 지역'),
    ('고궁문화유산', 0.7, '고궁, 문화유산 - 관광객 vs 지역민 접근성 격차'),
    ('발달상권', 0.6, '발달 상권 - 상대적 교통 편의성 양호'),
    ('관광특구', 0.5, '관광 특구 - 교통 인프라 잘 갖춰진 지역'),
    ('기타', 0.7, '일반지역 기본값')
ON CONFLICT (poi_category) DO UPDATE SET 
    vulnerability_score = EXCLUDED.vulnerability_score,
    description = EXCLUDED.description;

-- 테이블 설명 추가
COMMENT ON TABLE drt_vulnerable_scores IS '교통취약지형 DRT Score 월별 시간대별 집계 테이블 (전일 기준)';
COMMENT ON COLUMN drt_vulnerable_scores.var_t_score IS 'VAR_t 취약 접근성 비율: t시 배차수/취약시간대 총배차수 (09-11시 1.5x, 14-16시 1.3x, 18-20시 1.2x)';
COMMENT ON COLUMN drt_vulnerable_scores.sed_t_score IS 'SED_t 사회 형평성 수요: t시 승하차수/취약시간대 총승하차수 (100명미만 1.4x, 핵심시간 1.2x)';
COMMENT ON COLUMN drt_vulnerable_scores.mdi_t_score IS 'MDI_t 이동성 불리 지수: (1000-구간승객수)/1000 (취약시간 30%, 일반시간 70% 분배)';
COMMENT ON COLUMN drt_vulnerable_scores.avs_score IS 'AVS 지역 취약성 점수: area_vulnerability_scores 테이블 참조';
COMMENT ON COLUMN drt_vulnerable_scores.total_drt_score IS '교통취약지형 총 DRT 점수: (VAR_t*0.3 + SED_t*0.3 + MDI_t*0.4) * AVS * 100';
COMMENT ON COLUMN drt_vulnerable_scores.is_vulnerable_time IS '취약시간대 여부: 09-11시(의료), 14-16시(복지), 18-20시(저녁)';
COMMENT ON COLUMN drt_vulnerable_scores.vulnerable_category IS '취약시간 카테고리: medical, welfare, evening, normal';

COMMENT ON TABLE area_vulnerability_scores IS '지역 취약성 점수 참조 테이블 (서비스레이어에서 활용)';

-- 사용 예시 쿼리 (주석)
/*
-- 2025년 7월 교통취약지형 집계 실행
SELECT calculate_vulnerable_drt_scores('2025-07-01'::DATE);

-- 특정 구의 교통취약지형 DRT 점수 조회 (히트맵용)
SELECT 
    dvs.station_id,
    dvs.district_name,
    MAX(dvs.total_drt_score) as peak_vulnerable_drt_score,
    (ARRAY_AGG(dvs.hour_of_day ORDER BY dvs.total_drt_score DESC))[1] as peak_hour,
    (ARRAY_AGG(dvs.vulnerable_category ORDER BY dvs.total_drt_score DESC))[1] as peak_category,
    SUM(CASE WHEN dvs.is_vulnerable_time THEN 1 ELSE 0 END) as vulnerable_hours_count
FROM drt_vulnerable_scores dvs
WHERE dvs.district_name = '마포구'
    AND dvs.analysis_month = '2025-07-01'
GROUP BY dvs.station_id, dvs.district_name
ORDER BY peak_vulnerable_drt_score DESC;

-- 취약시간대별 DRT 점수 비교
SELECT 
    dvs.hour_of_day,
    dvs.vulnerable_category,
    dvs.is_vulnerable_time,
    ROUND(AVG(dvs.total_drt_score), 2) as avg_drt_score,
    COUNT(*) as station_count
FROM drt_vulnerable_scores dvs
WHERE dvs.analysis_month = '2025-07-01'
GROUP BY dvs.hour_of_day, dvs.vulnerable_category, dvs.is_vulnerable_time
ORDER BY dvs.hour_of_day;

-- 취약시간대 카테고리별 통계
SELECT 
    vulnerable_category,
    COUNT(*) as total_records,
    ROUND(AVG(total_drt_score), 2) as avg_score,
    ROUND(MAX(total_drt_score), 2) as max_score
FROM drt_vulnerable_scores 
WHERE analysis_month = '2025-07-01'
GROUP BY vulnerable_category
ORDER BY avg_score DESC;
*/