-- ===============================================
-- 06-traffic-history-schema.sql - 교통 이력 데이터 스키마
-- TimescaleDB 기반 시계열 교통 데이터 최적화 스키마
-- ===============================================

-- ===============================================
-- 1. 정류장별 승하차 인원 이력 (API 1) - Tall Table 구조
-- ===============================================

CREATE TABLE station_passenger_history (
    record_date DATE NOT NULL,                     -- 기준일자
    route_id VARCHAR(50) NOT NULL,                 -- 노선ID
    node_id VARCHAR(50) NOT NULL,                  -- 정류장ID (bus_stops.node_id 참조)
    hour INTEGER NOT NULL,                         -- 시간 (0-23)
    
    -- 메타데이터
    route_name VARCHAR(100),                       -- 노선명
    station_name VARCHAR(200),                     -- 정류장명
    station_sequence INTEGER,                      -- 정류장순번
    
    -- 시간당 운행 데이터
    dispatch_count INTEGER DEFAULT 0,              -- 배차수 (시간당)
    ride_passenger INTEGER DEFAULT 0,              -- 승차인원 (시간당)
    alight_passenger INTEGER DEFAULT 0,            -- 하차인원 (시간당)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 복합키 (시간 포함)
    PRIMARY KEY (record_date, route_id, node_id, hour)
);

-- TimescaleDB 하이퍼테이블 생성 (날짜 기준 파티셔닝)
SELECT create_hypertable('station_passenger_history', 'record_date', chunk_time_interval => INTERVAL '7 days');

-- 압축 정책 (시간별 데이터 고려)
ALTER TABLE station_passenger_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id, node_id, hour'
);

SELECT add_compression_policy('station_passenger_history', INTERVAL '7 days');

-- ===============================================
-- 2. 구간별 교통수요 이력 (API 2) - DRT 분석 최적화 (Tall Table 구조)
-- ===============================================

CREATE TABLE section_passenger_history (
    record_date DATE NOT NULL,                     -- 기준일자
    route_id VARCHAR(50) NOT NULL,                 -- 노선ID
    from_node_id VARCHAR(50) NOT NULL,             -- 출발정류장ID (bus_stops.node_id 참조)
    to_node_id VARCHAR(50) NOT NULL,               -- 도착정류장ID (bus_stops.node_id 참조)
    hour INTEGER NOT NULL,                         -- 시간 (0-23)
    station_sequence INTEGER,                      -- 정류장순번
    
    -- ===========================================
    -- API 2 실제 유효 필드들 (Tall Table 구조)
    -- ===========================================
    -- 시간당 승객수 (API2 검증 완료: a18SumLoadPsngNum{hour}h 필드)
    passenger_count INTEGER DEFAULT NULL,          -- 해당 시간대 승객수
    
    -- 일일 총합 참조용 (중복 저장하지 않고 집계로 계산)
    daily_total_passengers INTEGER DEFAULT NULL,   -- a18SumLoadPsng: 일일 구간별 총 승객수 (참조용)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 복합키 (시간 포함)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('section_passenger_history', 'record_date', chunk_time_interval => INTERVAL '7 days');

-- 압축 정책 (시간별 데이터 고려)
ALTER TABLE section_passenger_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id, from_node_id, to_node_id, hour'
);

SELECT add_compression_policy('section_passenger_history', INTERVAL '7 days');

-- ===============================================
-- 3. 행정동별 OD 통행량 이력 (API 3)
-- ===============================================

CREATE TABLE od_traffic_history (
    record_date DATE NOT NULL,                     -- 기준일자
    start_district VARCHAR(50) NOT NULL,           -- 출발 시군구
    start_admin_dong VARCHAR(50) NOT NULL,         -- 출발 행정동
    end_district VARCHAR(50) NOT NULL,             -- 도착 시군구
    end_admin_dong VARCHAR(50) NOT NULL,           -- 도착 행정동
    
    total_passenger_count INTEGER DEFAULT 0,       -- 총 통행량
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (record_date, start_district, start_admin_dong, end_district, end_admin_dong)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('od_traffic_history', 'record_date', chunk_time_interval => INTERVAL '7 days');

-- 압축 정책
ALTER TABLE od_traffic_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'start_district, start_admin_dong, end_district, end_admin_dong'
);

SELECT add_compression_policy('od_traffic_history', INTERVAL '7 days');

-- ===============================================
-- 4. 구간별 운행시간 이력 (API 4) - Tall Table 구조
-- ===============================================

CREATE TABLE section_speed_history (
    record_date DATE NOT NULL,                     -- 기준일자
    route_id VARCHAR(50) NOT NULL,                 -- 노선ID
    from_node_id VARCHAR(50) NOT NULL,             -- 출발정류장ID (bus_stops.node_id 참조)
    to_node_id VARCHAR(50) NOT NULL,               -- 도착정류장ID (bus_stops.node_id 참조)
    hour INTEGER NOT NULL,                         -- 시간 (0-23)
    
    -- API 4 메타데이터 (구간 식별용)
    from_station_sequence INTEGER,                 -- 출발정류장순번
    to_station_sequence INTEGER,                   -- 도착정류장순번
    
    -- 유효한 운행 데이터 (73.9% 유효율 확인)
    trip_time INTEGER DEFAULT 0,                   -- 운행시간 (시간당, 분) - 유일한 유효 데이터
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 복합키 (시간 포함)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('section_speed_history', 'record_date', chunk_time_interval => INTERVAL '7 days');

-- 압축 정책 (시간별 데이터 고려)
ALTER TABLE section_speed_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id, from_node_id, to_node_id, hour'
);

SELECT add_compression_policy('section_speed_history', INTERVAL '7 days');

-- ===============================================
-- 5. 도로 교통 패턴 이력 (API 5) - DRT 분석 특화
-- ===============================================

CREATE TABLE road_traffic_history (
    record_date DATE NOT NULL,                     -- 기준일자
    link_id VARCHAR(50) NOT NULL,                  -- 구간ID(링크ID)
    link_sequence INTEGER NOT NULL,                -- 구간순서
    
    -- DRT 분석 핵심 정보
    road_name VARCHAR(200),                        -- 도로명
    start_point VARCHAR(200),                      -- 시점명
    end_point VARCHAR(200),                        -- 종점명
    avg_speed DECIMAL(5,2) DEFAULT 0,              -- 평균속도 (버스 속도와 비교용)
    
    -- 시간/패턴 분석
    time_code VARCHAR(10),                         -- 시간코드
    weekday_code VARCHAR(10),                      -- 요일코드
    weekday_group_code VARCHAR(10),                -- 요일그룹코드  
    peak_time_type VARCHAR(20),                    -- 첨두시구분 (오전/낮/오후)
    direction_code VARCHAR(10),                    -- 도로방향구분코드
    direction_name VARCHAR(50),                    -- 도로방향구분명
    
    -- 데이터 품질 관리 (업데이트 이슈 대응)
    data_quality_flag INTEGER DEFAULT 1,           -- 1: 정상, 0: 지연/문제
    days_delayed INTEGER DEFAULT 0,                -- 지연 일수 추적
    last_updated TIMESTAMP,                        -- 실제 업데이트 시점
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (record_date, link_id, link_sequence)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('road_traffic_history', 'record_date', chunk_time_interval => INTERVAL '7 days');

-- 압축 정책 (임시 주석처리 - link_sequence 키 충돌 문제)
-- ALTER TABLE road_traffic_history SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'link_id, link_sequence, peak_time_type, weekday_group_code'
-- );

-- SELECT add_compression_policy('road_traffic_history', INTERVAL '7 days');

-- ===============================================
-- 6. 실시간 인구 캐시 테이블 (API 6)
-- ===============================================

CREATE TABLE population_cache (
    admin_dong_code VARCHAR(10) NOT NULL,          -- 행정동코드
    time_zone INTEGER NOT NULL,                    -- 시간대 (0-23)
    
    -- 기본 인구 정보
    total_population INTEGER DEFAULT 0,            -- 총 생활인구
    
    -- 성별 연령대별 세부 데이터
    male_0_9 INTEGER DEFAULT 0, male_10_14 INTEGER DEFAULT 0,
    male_15_19 INTEGER DEFAULT 0, male_20_24 INTEGER DEFAULT 0,
    male_25_29 INTEGER DEFAULT 0, male_30_34 INTEGER DEFAULT 0,
    male_35_39 INTEGER DEFAULT 0, male_40_44 INTEGER DEFAULT 0,
    male_45_49 INTEGER DEFAULT 0, male_50_54 INTEGER DEFAULT 0,
    male_55_59 INTEGER DEFAULT 0, male_60_64 INTEGER DEFAULT 0,
    male_65_69 INTEGER DEFAULT 0, male_70_plus INTEGER DEFAULT 0,
    
    female_0_9 INTEGER DEFAULT 0, female_10_14 INTEGER DEFAULT 0,
    female_15_19 INTEGER DEFAULT 0, female_20_24 INTEGER DEFAULT 0,
    female_25_29 INTEGER DEFAULT 0, female_30_34 INTEGER DEFAULT 0,
    female_35_39 INTEGER DEFAULT 0, female_40_44 INTEGER DEFAULT 0,
    female_45_49 INTEGER DEFAULT 0, female_50_54 INTEGER DEFAULT 0,
    female_55_59 INTEGER DEFAULT 0, female_60_64 INTEGER DEFAULT 0,
    female_65_69 INTEGER DEFAULT 0, female_70_plus INTEGER DEFAULT 0,
    
    -- 캐시 메타데이터
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    
    PRIMARY KEY (admin_dong_code, time_zone)
);

-- 만료된 캐시 자동 삭제 (매시간)
CREATE INDEX idx_population_cache_expires ON population_cache (expires_at);

-- Population 캐시 UPSERT 함수 (덮어쓰기 방식)
CREATE OR REPLACE FUNCTION upsert_population_cache(
    p_admin_dong_code VARCHAR(10),
    p_time_zone INTEGER,
    p_total_population INTEGER,
    p_male_0_9 INTEGER DEFAULT 0, p_male_10_14 INTEGER DEFAULT 0,
    p_male_15_19 INTEGER DEFAULT 0, p_male_20_24 INTEGER DEFAULT 0,
    p_male_25_29 INTEGER DEFAULT 0, p_male_30_34 INTEGER DEFAULT 0,
    p_male_35_39 INTEGER DEFAULT 0, p_male_40_44 INTEGER DEFAULT 0,
    p_male_45_49 INTEGER DEFAULT 0, p_male_50_54 INTEGER DEFAULT 0,
    p_male_55_59 INTEGER DEFAULT 0, p_male_60_64 INTEGER DEFAULT 0,
    p_male_65_69 INTEGER DEFAULT 0, p_male_70_plus INTEGER DEFAULT 0,
    p_female_0_9 INTEGER DEFAULT 0, p_female_10_14 INTEGER DEFAULT 0,
    p_female_15_19 INTEGER DEFAULT 0, p_female_20_24 INTEGER DEFAULT 0,
    p_female_25_29 INTEGER DEFAULT 0, p_female_30_34 INTEGER DEFAULT 0,
    p_female_35_39 INTEGER DEFAULT 0, p_female_40_44 INTEGER DEFAULT 0,
    p_female_45_49 INTEGER DEFAULT 0, p_female_50_54 INTEGER DEFAULT 0,
    p_female_55_59 INTEGER DEFAULT 0, p_female_60_64 INTEGER DEFAULT 0,
    p_female_65_69 INTEGER DEFAULT 0, p_female_70_plus INTEGER DEFAULT 0
)
RETURNS void AS $$
BEGIN
    INSERT INTO population_cache (
        admin_dong_code, time_zone, total_population,
        male_0_9, male_10_14, male_15_19, male_20_24, male_25_29, male_30_34,
        male_35_39, male_40_44, male_45_49, male_50_54, male_55_59, male_60_64,
        male_65_69, male_70_plus,
        female_0_9, female_10_14, female_15_19, female_20_24, female_25_29, female_30_34,
        female_35_39, female_40_44, female_45_49, female_50_54, female_55_59, female_60_64,
        female_65_69, female_70_plus,
        cached_at, expires_at
    ) VALUES (
        p_admin_dong_code, p_time_zone, p_total_population,
        p_male_0_9, p_male_10_14, p_male_15_19, p_male_20_24, p_male_25_29, p_male_30_34,
        p_male_35_39, p_male_40_44, p_male_45_49, p_male_50_54, p_male_55_59, p_male_60_64,
        p_male_65_69, p_male_70_plus,
        p_female_0_9, p_female_10_14, p_female_15_19, p_female_20_24, p_female_25_29, p_female_30_34,
        p_female_35_39, p_female_40_44, p_female_45_49, p_female_50_54, p_female_55_59, p_female_60_64,
        p_female_65_69, p_female_70_plus,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 hour'
    )
    ON CONFLICT (admin_dong_code, time_zone) 
    DO UPDATE SET
        total_population = EXCLUDED.total_population,
        male_0_9 = EXCLUDED.male_0_9, male_10_14 = EXCLUDED.male_10_14,
        male_15_19 = EXCLUDED.male_15_19, male_20_24 = EXCLUDED.male_20_24,
        male_25_29 = EXCLUDED.male_25_29, male_30_34 = EXCLUDED.male_30_34,
        male_35_39 = EXCLUDED.male_35_39, male_40_44 = EXCLUDED.male_40_44,
        male_45_49 = EXCLUDED.male_45_49, male_50_54 = EXCLUDED.male_50_54,
        male_55_59 = EXCLUDED.male_55_59, male_60_64 = EXCLUDED.male_60_64,
        male_65_69 = EXCLUDED.male_65_69, male_70_plus = EXCLUDED.male_70_plus,
        female_0_9 = EXCLUDED.female_0_9, female_10_14 = EXCLUDED.female_10_14,
        female_15_19 = EXCLUDED.female_15_19, female_20_24 = EXCLUDED.female_20_24,
        female_25_29 = EXCLUDED.female_25_29, female_30_34 = EXCLUDED.female_30_34,
        female_35_39 = EXCLUDED.female_35_39, female_40_44 = EXCLUDED.female_40_44,
        female_45_49 = EXCLUDED.female_45_49, female_50_54 = EXCLUDED.female_50_54,
        female_55_59 = EXCLUDED.female_55_59, female_60_64 = EXCLUDED.female_60_64,
        female_65_69 = EXCLUDED.female_65_69, female_70_plus = EXCLUDED.female_70_plus,
        cached_at = CURRENT_TIMESTAMP,
        expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- 만료된 캐시 정리 함수
CREATE OR REPLACE FUNCTION cleanup_expired_population_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM population_cache WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ===============================================
-- 7. ETL 메타데이터 및 로그 추적 테이블
-- ===============================================

-- ETL 작업 상태 추적 테이블
CREATE TABLE etl_job_status (
    job_name VARCHAR(50) PRIMARY KEY,                 -- API1, API2, API3, API4, API5, API6, API7
    job_description VARCHAR(200),                     -- 작업 설명
    last_run_start TIMESTAMP,                         -- 마지막 실행 시작 시간
    last_run_end TIMESTAMP,                           -- 마지막 실행 완료 시간
    last_success TIMESTAMP,                           -- 마지막 성공 시간
    status VARCHAR(20) DEFAULT 'PENDING',             -- PENDING, RUNNING, SUCCESS, FAILED
    records_processed INTEGER DEFAULT 0,              -- 처리된 레코드 수
    records_inserted INTEGER DEFAULT 0,               -- 삽입된 레코드 수
    records_updated INTEGER DEFAULT 0,                -- 업데이트된 레코드 수
    error_message TEXT,                               -- 오류 메시지
    data_date DATE,                                   -- 처리된 데이터의 기준일자
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ETL 작업 상세 로그 테이블
CREATE TABLE etl_job_logs (
    id SERIAL,
    job_name VARCHAR(50) NOT NULL,                    -- etl_job_status.job_name 참조
    log_level VARCHAR(10) NOT NULL,                   -- INFO, WARN, ERROR, DEBUG
    log_message TEXT NOT NULL,                        -- 로그 메시지
    execution_step VARCHAR(100),                      -- 실행 단계 (API_CALL, DATA_TRANSFORM, DB_INSERT 등)
    additional_data JSONB,                            -- 추가 데이터 (오류 상세, API 응답 등)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 하이퍼테이블용 복합 기본키 (partitioning column 포함)
    PRIMARY KEY (id, created_at),
    
    -- 외래키 제약조건
    FOREIGN KEY (job_name) REFERENCES etl_job_status(job_name) ON DELETE CASCADE
);

-- TimescaleDB 하이퍼테이블 생성 (로그 테이블)
SELECT create_hypertable('etl_job_logs', 'created_at', chunk_time_interval => INTERVAL '7 days');

-- ETL 테이블 인덱스
CREATE INDEX idx_etl_job_status_last_success ON etl_job_status (last_success DESC);
CREATE INDEX idx_etl_job_status_status ON etl_job_status (status);
CREATE INDEX idx_etl_job_logs_job_name ON etl_job_logs (job_name, created_at DESC);
CREATE INDEX idx_etl_job_logs_level ON etl_job_logs (log_level, created_at DESC);

-- ETL 초기 데이터 삽입
INSERT INTO etl_job_status (job_name, job_description, status) VALUES
('API1_STATION_PASSENGER', 'API1: 정류장별 승하차 인원수 수집', 'PENDING'),
('API2_SECTION_PASSENGER', 'API2: 구간별 승객수 수집', 'PENDING'),
('API3_EMD_OD', 'API3: 행정동별 OD 통행량 수집', 'PENDING'),
('API4_SECTION_SPEED', 'API4: 구간별 운행시간 수집', 'PENDING'),
('API5_ROAD_TRAFFIC', 'API5: 도로 교통 패턴 수집', 'PENDING'),
('API6_POPULATION', 'API6: 실시간 인구 데이터 수집', 'PENDING');

-- ===============================================
-- 8. 데이터 품질 모니터링 뷰
-- ===============================================

-- API 5 데이터 품질 전용 모니터링 뷰 (업데이트 이슈 대응)
CREATE VIEW api5_data_quality_monitor AS
SELECT 
    MAX(record_date) as latest_data_date,
    COUNT(*) as total_records,
    AVG(CASE WHEN data_quality_flag = 1 THEN 1.0 ELSE 0.0 END) * 100 as quality_percentage,
    AVG(days_delayed) as avg_delay_days,
    CURRENT_DATE - MAX(record_date) as current_delay_days,
    CASE 
        WHEN CURRENT_DATE - MAX(record_date) <= 5 THEN 'NORMAL'
        WHEN CURRENT_DATE - MAX(record_date) <= 10 THEN 'WARNING' 
        ELSE 'DEGRADED'
    END as data_status,
    COUNT(DISTINCT road_name) as unique_roads,
    COUNT(DISTINCT CASE WHEN data_quality_flag = 1 THEN road_name END) as reliable_roads
FROM road_traffic_history;

CREATE VIEW traffic_data_quality AS
SELECT 
    'station_passenger_history' as table_name,
    COUNT(*) as total_records,
    MIN(record_date) as earliest_date,
    MAX(record_date) as latest_date,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT node_id) as unique_stations
FROM station_passenger_history
UNION ALL
SELECT 
    'section_passenger_history' as table_name,
    COUNT(*) as total_records,
    MIN(record_date) as earliest_date,
    MAX(record_date) as latest_date,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT from_node_id || '-' || to_node_id) as unique_stations
FROM section_passenger_history
UNION ALL
SELECT 
    'od_traffic_history' as table_name,
    COUNT(*) as total_records,
    MIN(record_date) as earliest_date,
    MAX(record_date) as latest_date,
    COUNT(DISTINCT start_district) as unique_routes,
    COUNT(DISTINCT end_district) as unique_stations
FROM od_traffic_history
UNION ALL
SELECT 
    'section_speed_history' as table_name,
    COUNT(*) as total_records,
    MIN(record_date) as earliest_date,
    MAX(record_date) as latest_date,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT from_node_id || '-' || to_node_id) as unique_stations
FROM section_speed_history
UNION ALL
SELECT 
    'road_traffic_history' as table_name,
    COUNT(*) as total_records,
    MIN(record_date) as earliest_date,
    MAX(record_date) as latest_date,
    COUNT(DISTINCT link_id) as unique_routes,
    AVG(days_delayed) as avg_delay_days
FROM road_traffic_history;

-- ===============================================
-- 8. 인덱스 최적화
-- ===============================================

-- 정류장별 승하차 인원 이력 (Tall Table 구조에 맞게 수정)
CREATE INDEX idx_station_passenger_route_date ON station_passenger_history (route_id, record_date);
CREATE INDEX idx_station_passenger_node_date ON station_passenger_history (node_id, record_date);
CREATE INDEX idx_station_passenger_hour ON station_passenger_history (hour);
CREATE INDEX idx_station_passenger_route_hour ON station_passenger_history (route_id, hour);
CREATE INDEX idx_station_passenger_ridership ON station_passenger_history (ride_passenger DESC, alight_passenger DESC);

-- 구간별 승객수 이력 (Tall Table 구조에 맞게 수정)
CREATE INDEX idx_section_passenger_route_date ON section_passenger_history (route_id, record_date);
CREATE INDEX idx_section_passenger_section_date ON section_passenger_history (from_node_id, to_node_id, record_date);
CREATE INDEX idx_section_passenger_hour ON section_passenger_history (hour);
CREATE INDEX idx_section_passenger_route_hour ON section_passenger_history (route_id, hour);
CREATE INDEX idx_section_passenger_count ON section_passenger_history (passenger_count DESC) WHERE passenger_count > 0;

-- OD 통행량 이력
CREATE INDEX idx_od_traffic_start_date ON od_traffic_history (start_district, start_admin_dong, record_date);
CREATE INDEX idx_od_traffic_end_date ON od_traffic_history (end_district, end_admin_dong, record_date);

-- 구간별 운행시간 이력 (Tall Table 구조에 맞게 수정)
CREATE INDEX idx_section_speed_route_date ON section_speed_history (route_id, record_date);
CREATE INDEX idx_section_speed_section_date ON section_speed_history (from_node_id, to_node_id, record_date);
CREATE INDEX idx_section_speed_hour ON section_speed_history (hour);
CREATE INDEX idx_section_speed_route_hour ON section_speed_history (route_id, hour);
CREATE INDEX idx_section_speed_trip_time ON section_speed_history (trip_time DESC) WHERE trip_time > 0;

-- 도로 교통 패턴 이력 (DRT 분석 최적화)
CREATE INDEX idx_road_traffic_link_date ON road_traffic_history (link_id, record_date);
CREATE INDEX idx_road_traffic_road_date ON road_traffic_history (road_name, record_date);
CREATE INDEX idx_road_traffic_peak_time ON road_traffic_history (peak_time_type, weekday_group_code);
CREATE INDEX idx_road_traffic_speed ON road_traffic_history (avg_speed DESC);
CREATE INDEX idx_road_traffic_quality ON road_traffic_history (data_quality_flag, days_delayed);
CREATE INDEX idx_road_traffic_direction ON road_traffic_history (direction_code, direction_name);

-- ===============================================
-- 9. 데이터 보존 정책 (선택적)
-- ===============================================

-- 1년 이후 데이터 자동 삭제 정책 (필요시 활성화)
-- SELECT add_retention_policy('station_passenger_history', INTERVAL '1 year');
-- SELECT add_retention_policy('section_passenger_history', INTERVAL '1 year');
-- SELECT add_retention_policy('od_traffic_history', INTERVAL '1 year');
-- SELECT add_retention_policy('section_speed_history', INTERVAL '1 year');
-- SELECT add_retention_policy('traffic_link_history', INTERVAL '1 year');


-- ===============================================
-- 완료 메시지
-- ===============================================

DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE '교통 이력 데이터 스키마 생성 완료';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '생성된 하이퍼테이블:';
    RAISE NOTICE '  - station_passenger_history (정류장별 승하차 - Tall Table)';
    RAISE NOTICE '  - section_passenger_history (구간별 교통수요 - Tall Table)';
    RAISE NOTICE '  - od_traffic_history (OD 통행량)';
    RAISE NOTICE '  - section_speed_history (구간별 운행시간 - Tall Table)';
    RAISE NOTICE '  - road_traffic_history (도로 교통 패턴 - 데이터 품질 모니터링 포함)';
    RAISE NOTICE '  - population_cache (실시간 인구 캐시)';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Tall Table 구조 적용:';
    RAISE NOTICE '  - station_passenger_history: hour 필드 추가, 7개 핵심 필드';
    RAISE NOTICE '  - section_passenger_history: hour 필드 추가, 6개 핵심 필드';
    RAISE NOTICE '  - section_speed_history: hour 필드 추가, 5개 핵심 필드';
    RAISE NOTICE '  - 레코드 수: 24배 증가 (시간대별)';
    RAISE NOTICE '  - 시계열 분석 및 ML 최적화';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '압축 및 파티셔닝 정책 적용 완료';
    RAISE NOTICE '예상 월간 압축 후 용량: ~6GB';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '다음 단계: 실제 데이터 적재 후 조회 패턴 분석';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'ETL 파이프라인 준비 완료:';
    RAISE NOTICE '  - ETL 작업 상태 추적: etl_job_status, etl_job_logs';
    RAISE NOTICE '  - 필드명 통일: station_id → node_id (01-schema 일치)';
    RAISE NOTICE '  - Population UPSERT: upsert_population_cache() 함수';
    RAISE NOTICE '  - 캐시 정리: cleanup_expired_population_cache() 함수';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'API 5 데이터 품질 관리:';
    RAISE NOTICE '  - 실시간 명세이지만 13일 지연 상황 감지';
    RAISE NOTICE '  - SELECT * FROM api5_data_quality_monitor; 로 상태 확인';
    RAISE NOTICE '  - NORMAL/WARNING/DEGRADED 상태 분류';
    RAISE NOTICE '  - DRT 분석 가치: 버스 vs 도로 속도 비교, 신규 노선 계획';
    RAISE NOTICE '===========================================';
END $$;