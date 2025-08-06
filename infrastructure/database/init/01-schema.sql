-- ===============================================
-- database/init/01-schema.sql (Raw Data 적재용, master table)
-- ===============================================

-- TimescaleDB 및 PostGIS 확장 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. 버스 노선 테이블
CREATE TABLE bus_routes (
    route_id VARCHAR(50) PRIMARY KEY,
    route_number VARCHAR(20) NOT NULL,
    route_type VARCHAR(50),
    start_point VARCHAR(100),
    end_point VARCHAR(100),
    first_bus_time TIME,
    last_bus_time TIME,
    weekday_interval INTEGER, -- 분 단위
    saturday_interval INTEGER,
    sunday_interval INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 정류장 테이블
CREATE TABLE bus_stops (
    stop_id VARCHAR(50) PRIMARY KEY,
    stop_number VARCHAR(20),
    stop_name VARCHAR(100) NOT NULL,
    location GEOGRAPHY(POINT, 4326), -- PostGIS 지리 데이터 타입
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    district VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 공간 인덱스 생성
CREATE INDEX idx_bus_stops_location ON bus_stops USING GIST (location);

-- 3. 노선-정류장 매핑 테이블
CREATE TABLE route_stops (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(50) REFERENCES bus_routes(route_id),
    stop_id VARCHAR(50) REFERENCES bus_stops(stop_id),
    stop_sequence INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(route_id, stop_sequence)
);

-- 4. 정류장별 승하차 이용량 (시계열 데이터)
CREATE TABLE stop_usage (
    stop_id VARCHAR(50) REFERENCES bus_stops(stop_id),
    recorded_at TIMESTAMP NOT NULL,
    boarding_count INTEGER DEFAULT 0,
    alighting_count INTEGER DEFAULT 0,
    is_operational BOOLEAN DEFAULT true, -- 그 날 전체 운행 여부 (CSV 데이터 존재 여부)
    is_in_service_hours BOOLEAN DEFAULT true, -- 해당 시간이 노선 운행시간 내인지 여부
    is_holiday BOOLEAN DEFAULT false,
    is_weekend BOOLEAN DEFAULT false, -- 주말 여부 (토요일, 일요일)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (stop_id, recorded_at)
);

-- TimescaleDB 하이퍼테이블로 변환(Chunk를 기준으로 스캔, 쿼리 속도 증가)
SELECT create_hypertable('stop_usage', 'recorded_at');

-- 시계열 인덱스
CREATE INDEX idx_stop_usage_stop_time ON stop_usage (stop_id, recorded_at DESC);

-- 5. POI (Point of Interest) 테이블
CREATE TABLE pois (
    poi_id SERIAL PRIMARY KEY,
    poi_name VARCHAR(200) NOT NULL,
    poi_type VARCHAR(50) NOT NULL, -- 병원, 학교, 시장, 관광지 등
    poi_category VARCHAR(50),
    location GEOGRAPHY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    opens_at TIME,
    closes_at TIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- POI 공간 인덱스
CREATE INDEX idx_pois_location ON pois USING GIST (location);
CREATE INDEX idx_pois_type ON pois(poi_type);

-- 트리거: updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_bus_routes_updated_at BEFORE UPDATE ON bus_routes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bus_stops_updated_at BEFORE UPDATE ON bus_stops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pois_updated_at BEFORE UPDATE ON pois
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();