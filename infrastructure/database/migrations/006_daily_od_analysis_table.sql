-- =====================================================
-- DRT Dashboard - Daily OD Analysis Table
-- 작성일: 2025-09-09
-- 목적: 일별 Origin-Destination 분석을 통한 DRT 적합성 분석 지원
-- 
-- ## 설계 원칙:
-- - 일별 OD pair 단위 집계 (비정규화 구조)
-- - 시간대별 패턴 분석 (24시간 JSONB)
-- - 노선 연결성 및 DRT 적합성 사전 계산
-- - 기존 bus_stops, bus_routes 테이블과 연동
-- - 월별/요일별 집계 분석 지원
-- =====================================================

-- Daily OD Analysis 테이블 생성
DROP TABLE IF EXISTS daily_od_analysis CASCADE;

CREATE TABLE daily_od_analysis (
    -- 기본 키 (일별 OD pair)
    analysis_date DATE NOT NULL,
    from_station_id VARCHAR(50) NOT NULL,
    to_station_id VARCHAR(50) NOT NULL,
    
    -- 요일 분석 지원
    day_of_week INTEGER GENERATED ALWAYS AS (EXTRACT(DOW FROM analysis_date)) STORED,
    is_weekend BOOLEAN GENERATED ALWAYS AS (EXTRACT(DOW FROM analysis_date) IN (0,6)) STORED,
    week_of_month INTEGER GENERATED ALWAYS AS (
        CEILING(EXTRACT(DAY FROM analysis_date) / 7.0)
    ) STORED,
    
    -- From Station 메타데이터 (bus_stops 테이블 기준)
    from_station_name VARCHAR(200) NOT NULL,
    from_coordinates_x DECIMAL(15,8) NOT NULL,
    from_coordinates_y DECIMAL(15,8) NOT NULL,
    from_district_code VARCHAR(10),
    from_district_name VARCHAR(100),
    from_admin_dong VARCHAR(100),
    from_routes JSONB NOT NULL DEFAULT '[]',
    
    -- To Station 메타데이터 (bus_stops 테이블 기준)  
    to_station_name VARCHAR(200) NOT NULL,
    to_coordinates_x DECIMAL(15,8) NOT NULL,
    to_coordinates_y DECIMAL(15,8) NOT NULL,
    to_district_code VARCHAR(10),
    to_district_name VARCHAR(100),
    to_admin_dong VARCHAR(100),
    to_routes JSONB NOT NULL DEFAULT '[]',
    
    -- 시간대별 승객 수 (24시간 개별 컬럼)
    h00 INTEGER DEFAULT 0, h01 INTEGER DEFAULT 0, h02 INTEGER DEFAULT 0, h03 INTEGER DEFAULT 0,
    h04 INTEGER DEFAULT 0, h05 INTEGER DEFAULT 0, h06 INTEGER DEFAULT 0, h07 INTEGER DEFAULT 0,
    h08 INTEGER DEFAULT 0, h09 INTEGER DEFAULT 0, h10 INTEGER DEFAULT 0, h11 INTEGER DEFAULT 0,
    h12 INTEGER DEFAULT 0, h13 INTEGER DEFAULT 0, h14 INTEGER DEFAULT 0, h15 INTEGER DEFAULT 0,
    h16 INTEGER DEFAULT 0, h17 INTEGER DEFAULT 0, h18 INTEGER DEFAULT 0, h19 INTEGER DEFAULT 0,
    h20 INTEGER DEFAULT 0, h21 INTEGER DEFAULT 0, h22 INTEGER DEFAULT 0, h23 INTEGER DEFAULT 0,
    
    -- OD 핵심 데이터 (자동 계산)
    total_passengers INTEGER GENERATED ALWAYS AS (
        h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
        h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23
    ) STORED,
    estimated_distance_km DECIMAL(8,2) NOT NULL CHECK (estimated_distance_km >= 0),
    
    -- 노선 연결성 분석 (bus_routes 테이블 연동)
    common_routes JSONB NOT NULL DEFAULT '[]',
    from_only_routes JSONB NOT NULL DEFAULT '[]',
    to_only_routes JSONB NOT NULL DEFAULT '[]',
    direct_connection_count INTEGER DEFAULT 0 CHECK (direct_connection_count >= 0),
    transfer_required BOOLEAN DEFAULT TRUE,
    
    -- 시간대별 승객 수 (4개 구간)
    morning_peak_passengers INTEGER GENERATED ALWAYS AS (h07 + h08 + h09) STORED,      -- 출근 (7-9시)
    evening_peak_passengers INTEGER GENERATED ALWAYS AS (h17 + h18 + h19) STORED,      -- 퇴근 (17-19시)
    night_passengers INTEGER GENERATED ALWAYS AS (h22 + h23 + h00 + h01 + h02 + h03 + h04 + h05) STORED,  -- 심야 (22-5시)
    daytime_passengers INTEGER GENERATED ALWAYS AS (h10 + h11 + h12 + h13 + h14 + h15 + h16) STORED,      -- 주간 (10-16시)
    
    -- 시간대별 집중도 (h00~h23 직접 참조로 계산)
    morning_concentration DECIMAL(5,4) GENERATED ALWAYS AS (
        CASE WHEN (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                   h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23) > 0 
             THEN (h07 + h08 + h09)::DECIMAL / (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                                                h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23)
             ELSE 0 
        END
    ) STORED,
    evening_concentration DECIMAL(5,4) GENERATED ALWAYS AS (
        CASE WHEN (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                   h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23) > 0 
             THEN (h17 + h18 + h19)::DECIMAL / (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                                                h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23)
             ELSE 0 
        END
    ) STORED,
    night_concentration DECIMAL(5,4) GENERATED ALWAYS AS (
        CASE WHEN (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                   h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23) > 0 
             THEN (h22 + h23 + h00 + h01 + h02 + h03 + h04 + h05)::DECIMAL / (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                                                                              h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23)
             ELSE 0 
        END
    ) STORED,
    daytime_concentration DECIMAL(5,4) GENERATED ALWAYS AS (
        CASE WHEN (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                   h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23) > 0 
             THEN (h10 + h11 + h12 + h13 + h14 + h15 + h16)::DECIMAL / (h00 + h01 + h02 + h03 + h04 + h05 + h06 + h07 + h08 + h09 + h10 + h11 +
                                                                         h12 + h13 + h14 + h15 + h16 + h17 + h18 + h19 + h20 + h21 + h22 + h23)
             ELSE 0 
        END
    ) STORED,
    
    -- 시스템 메타데이터 (기존 테이블 패턴 준수)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (analysis_date, from_station_id, to_station_id)
);

-- =====================================================
-- 성능 최적화 인덱스
-- =====================================================

-- 날짜별 조회 최적화 (기본 분석용)
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_date 
    ON daily_od_analysis (analysis_date);

-- 요일별 패턴 분석용
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_weekend_date 
    ON daily_od_analysis (is_weekend, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_day_of_week 
    ON daily_od_analysis (day_of_week, analysis_date);

-- 승객량 기준 TOP-N 조회용
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_passengers_desc 
    ON daily_od_analysis (total_passengers DESC, analysis_date);

-- 시간대별 패턴 분석용
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_morning_concentration 
    ON daily_od_analysis (morning_concentration DESC, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_evening_concentration 
    ON daily_od_analysis (evening_concentration DESC, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_night_concentration 
    ON daily_od_analysis (night_concentration DESC, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_daytime_concentration 
    ON daily_od_analysis (daytime_concentration DESC, analysis_date);

-- 지역별 분석용 (구/군별)
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_from_district 
    ON daily_od_analysis (from_district_code, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_to_district 
    ON daily_od_analysis (to_district_code, analysis_date);

-- 정류장 기준 OD 분석용
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_from_station 
    ON daily_od_analysis (from_station_id, analysis_date);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_to_station 
    ON daily_od_analysis (to_station_id, analysis_date);

-- JSONB 필드 GIN 인덱스 (패턴 검색 최적화)
CREATE INDEX CONCURRENTLY idx_daily_od_analysis_hourly_gin 
    ON daily_od_analysis USING GIN (hourly_distribution);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_common_routes_gin 
    ON daily_od_analysis USING GIN (common_routes);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_from_routes_gin 
    ON daily_od_analysis USING GIN (from_routes);

CREATE INDEX CONCURRENTLY idx_daily_od_analysis_to_routes_gin 
    ON daily_od_analysis USING GIN (to_routes);

-- =====================================================
-- 데이터 일관성 및 업데이트 트리거
-- =====================================================

-- updated_at 자동 업데이트 (기존 패턴 준수)
CREATE OR REPLACE FUNCTION update_daily_od_analysis_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

CREATE TRIGGER trigger_daily_od_analysis_updated_at 
    BEFORE UPDATE ON daily_od_analysis 
    FOR EACH ROW 
    EXECUTE FUNCTION update_daily_od_analysis_updated_at();

-- =====================================================
-- 테이블 및 컬럼 설명 (문서화)
-- =====================================================

COMMENT ON TABLE daily_od_analysis IS 
    'Daily Origin-Destination analysis table for DRT suitability analysis. Aggregates passenger flow patterns between bus stops with route connectivity and temporal analysis.';

COMMENT ON COLUMN daily_od_analysis.analysis_date IS 'Target analysis date (daily granularity)';
COMMENT ON COLUMN daily_od_analysis.from_station_id IS 'Origin bus stop ID (FK to bus_stops.node_id)';
COMMENT ON COLUMN daily_od_analysis.to_station_id IS 'Destination bus stop ID (FK to bus_stops.node_id)';
COMMENT ON COLUMN daily_od_analysis.total_passengers IS 'Total passenger count for this OD pair on analysis_date';
COMMENT ON COLUMN daily_od_analysis.hourly_distribution IS 'JSON object with 24-hour passenger distribution and peak analysis';
COMMENT ON COLUMN daily_od_analysis.common_routes IS 'JSON array of bus routes serving both origin and destination';
COMMENT ON COLUMN daily_od_analysis.morning_peak_passengers IS 'Passenger count during morning peak hours (7-9 AM)';
COMMENT ON COLUMN daily_od_analysis.evening_peak_passengers IS 'Passenger count during evening peak hours (5-7 PM)';
COMMENT ON COLUMN daily_od_analysis.night_passengers IS 'Passenger count during night hours (10PM-5AM)';
COMMENT ON COLUMN daily_od_analysis.daytime_passengers IS 'Passenger count during daytime hours (10AM-4PM)';
COMMENT ON COLUMN daily_od_analysis.morning_concentration IS 'Morning peak concentration ratio (0-1)';
COMMENT ON COLUMN daily_od_analysis.evening_concentration IS 'Evening peak concentration ratio (0-1)';
COMMENT ON COLUMN daily_od_analysis.night_concentration IS 'Night time concentration ratio (0-1)';
COMMENT ON COLUMN daily_od_analysis.daytime_concentration IS 'Daytime concentration ratio (0-1)';

-- =====================================================
-- 외래키 제약조건 (참조 무결성)
-- =====================================================

-- bus_stops 테이블과의 연동 (존재하는 정류장만 허용)
ALTER TABLE daily_od_analysis 
ADD CONSTRAINT fk_daily_od_analysis_from_station 
FOREIGN KEY (from_station_id) REFERENCES bus_stops(node_id) 
ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE daily_od_analysis 
ADD CONSTRAINT fk_daily_od_analysis_to_station 
FOREIGN KEY (to_station_id) REFERENCES bus_stops(node_id) 
ON DELETE CASCADE ON UPDATE CASCADE;

-- =====================================================
-- 권한 설정 (기존 사용자 권한과 일관성)
-- =====================================================

-- DRT 분석용 읽기 권한
GRANT SELECT ON daily_od_analysis TO ddf_user;
GRANT SELECT ON daily_od_analysis TO PUBLIC;

-- 데이터 적재용 권한 (ETL 프로세스)
GRANT INSERT, UPDATE, DELETE ON daily_od_analysis TO ddf_user;

-- =====================================================
-- 완료 메시지
-- =====================================================

DO $$ 
BEGIN 
    RAISE NOTICE 'Daily OD Analysis 테이블이 성공적으로 생성되었습니다.';
    RAISE NOTICE '- 테이블명: daily_od_analysis';
    RAISE NOTICE '- 예상 레코드 수: ~10M (일별 OD pairs)';
    RAISE NOTICE '- 인덱스: 11개 (성능 최적화)';
    RAISE NOTICE '- FK 제약: bus_stops 테이블 연동';
    RAISE NOTICE '- 분석 지표: 데이터 제공 중심 (의사결정은 사용자)';
END $$;