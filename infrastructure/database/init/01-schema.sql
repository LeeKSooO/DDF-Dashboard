-- ===============================================
-- 01-schema.sql - 서울시 교통 데이터 기본 스키마
-- 새로운 서울시 busInfra 데이터에 맞게 설계된 스키마
-- ===============================================

-- TimescaleDB 및 PostGIS 확장 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- ===============================================
-- 유틸리티 함수들
-- ===============================================
-- 시간 변환은 ETL 파이프라인에서 처리

-- ===============================================
-- 1. 정류장(노드) 테이블
-- ===============================================

CREATE TABLE bus_stops (
    node_id VARCHAR(50) PRIMARY KEY,           -- 노드ID
    node_name VARCHAR(200) NOT NULL,           -- 노드명
    node_description VARCHAR(200),             -- 노드설명
    node_num VARCHAR(20),                      -- 정류장번호
    node_type INTEGER DEFAULT 0,               -- 노드유형 (0=정류장)
    
    -- 좌표 정보
    coordinates_x DECIMAL(12, 8),              -- 원본 좌표X (경도)
    coordinates_y DECIMAL(11, 8),              -- 원본 좌표Y (위도)
    coordinates GEOMETRY(POINT, 4326),         -- PostGIS POINT (좌표X, 좌표Y)
    
    -- 매핑 좌표 정보
    mapping_x DECIMAL(12, 8),                  -- 맵핑좌표X
    mapping_y DECIMAL(11, 8),                  -- 맵핑좌표Y
    mapping_coordinates GEOMETRY(POINT, 4326), -- PostGIS POINT (매핑좌표)
    
    -- 메타 정보
    is_standard BOOLEAN DEFAULT FALSE,         -- 표준코드여부 (1:표준/0:비표준)
    is_active BOOLEAN DEFAULT TRUE,            -- 사용여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 정류장 테이블 인덱스
CREATE INDEX idx_bus_stops_coordinates ON bus_stops USING GIST (coordinates);
CREATE INDEX idx_bus_stops_mapping_coordinates ON bus_stops USING GIST (mapping_coordinates);
CREATE INDEX idx_bus_stops_node_num ON bus_stops (node_num);
CREATE INDEX idx_bus_stops_is_active ON bus_stops (is_active);

-- ===============================================
-- 2. 노선 테이블
-- ===============================================

CREATE TABLE bus_routes (
    route_id VARCHAR(50) PRIMARY KEY,          -- 노선ID
    route_name VARCHAR(100) NOT NULL,          -- 노선명
    route_type INTEGER NOT NULL,               -- 노선유형
    region_id VARCHAR(10),                     -- 지역ID
    total_distance DECIMAL(8, 2),              -- 총거리 (km)
    start_point VARCHAR(100),                  -- 기점명
    end_point VARCHAR(100),                    -- 종점명
    authorized_vehicles INTEGER,               -- 인가대수
    is_operating BOOLEAN DEFAULT TRUE,         -- 운행여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 노선 테이블 인덱스
CREATE INDEX idx_bus_routes_region_id ON bus_routes (region_id);
CREATE INDEX idx_bus_routes_route_type ON bus_routes (route_type);
CREATE INDEX idx_bus_routes_is_operating ON bus_routes (is_operating);

-- ===============================================
-- 3. 운행 스케줄 테이블
-- ===============================================

CREATE TABLE operation_schedules (
    route_id VARCHAR(50) PRIMARY KEY,          -- 노선ID (FK)
    
    -- 평일 스케줄
    weekday_interval INTEGER,                  -- 평일배차간격(분)
    weekday_first_time TIME,                   -- 평일첫차시간
    weekday_last_time TIME,                    -- 평일막차시간
    
    -- 토요일 스케줄  
    saturday_interval INTEGER,                 -- 토요일배차간격(분)
    saturday_first_time TIME,                  -- 토요일첫차시간
    saturday_last_time TIME,                   -- 토요일막차시간
    
    -- 공휴일 스케줄
    holiday_interval INTEGER,                  -- 공휴일배차간격(분)
    holiday_first_time TIME,                   -- 공휴일첫차시간
    holiday_last_time TIME,                    -- 공휴일막차시간
    
    -- 배차간격 범위
    min_interval INTEGER,                      -- 최소배차간격(분)
    max_interval INTEGER,                      -- 최대배차간격(분)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (route_id) REFERENCES bus_routes(route_id) ON DELETE CASCADE
);

-- ===============================================
-- 4. 노선 상세 테이블
-- ===============================================

CREATE TABLE route_details (
    route_id VARCHAR(50) PRIMARY KEY,          -- 노선ID (FK)
    total_operation_time INTEGER,              -- 총운행소요시간(분)
    terminal_waiting_time INTEGER,             -- 종점대기시간(분)
    curvature DECIMAL(10, 3),                  -- 곡률도
    spare_vehicles INTEGER,                    -- 예비차량수
    max_speed INTEGER,                         -- 최고속도
    avg_speed INTEGER,                         -- 평균속도
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (route_id) REFERENCES bus_routes(route_id) ON DELETE CASCADE
);

-- ===============================================
-- 5. 노선-정류장 매핑 테이블
-- ===============================================

CREATE TABLE route_stops (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(50) NOT NULL,             -- 노선ID (FK)
    stop_id VARCHAR(50) NOT NULL,              -- 정류장ID (FK)
    
    -- 순서 정보
    node_sequence INTEGER NOT NULL,            -- 노드순서
    stop_sequence INTEGER,                     -- 정류장순서
    
    -- 구간 정보
    section_id VARCHAR(50),                    -- 구간ID
    stop_section_id VARCHAR(50),               -- 정류장구간ID
    intersection_section_id VARCHAR(50),       -- 교차로구간ID
    link_id VARCHAR(50),                       -- 링크ID
    
    -- 거리 정보
    cumulative_section_distance DECIMAL(10, 2), -- 구간누적거리
    cumulative_stop_distance DECIMAL(10, 2),    -- 정류장누적거리
    
    -- 기타 정보
    direction_guide VARCHAR(100),              -- 방향안내
    is_active BOOLEAN DEFAULT TRUE,            -- 사용여부
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (route_id) REFERENCES bus_routes(route_id) ON DELETE CASCADE,
    FOREIGN KEY (stop_id) REFERENCES bus_stops(node_id) ON DELETE CASCADE,
    
    -- 유니크 제약조건
    UNIQUE(route_id, node_sequence)
);

-- route_stops 테이블 인덱스
CREATE INDEX idx_route_stops_route_id ON route_stops (route_id);
CREATE INDEX idx_route_stops_stop_id ON route_stops (stop_id);
CREATE INDEX idx_route_stops_node_sequence ON route_stops (route_id, node_sequence);
CREATE INDEX idx_route_stops_is_active ON route_stops (is_active);

-- ===============================================
-- 트리거: updated_at 자동 업데이트
-- ===============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 각 테이블에 updated_at 트리거 적용
CREATE TRIGGER update_bus_stops_updated_at 
    BEFORE UPDATE ON bus_stops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bus_routes_updated_at 
    BEFORE UPDATE ON bus_routes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_operation_schedules_updated_at 
    BEFORE UPDATE ON operation_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_route_details_updated_at 
    BEFORE UPDATE ON route_details
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_route_stops_updated_at 
    BEFORE UPDATE ON route_stops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===============================================
-- 데이터 무결성 체크 함수
-- ===============================================

-- PostGIS POINT 필드를 좌표값으로 업데이트하는 함수
CREATE OR REPLACE FUNCTION update_geometry_fields()
RETURNS void AS $$
BEGIN
    -- bus_stops 테이블의 geometry 필드 업데이트
    UPDATE bus_stops 
    SET coordinates = ST_SetSRID(ST_MakePoint(coordinates_x, coordinates_y), 4326)
    WHERE coordinates_x IS NOT NULL AND coordinates_y IS NOT NULL;
    
    UPDATE bus_stops 
    SET mapping_coordinates = ST_SetSRID(ST_MakePoint(mapping_x, mapping_y), 4326)
    WHERE mapping_x IS NOT NULL AND mapping_y IS NOT NULL;
    
    RAISE NOTICE 'Geometry fields updated successfully';
END;
$$ LANGUAGE plpgsql;

-- ===============================================
-- 초기 데이터 검증 뷰
-- ===============================================

-- VIEW는 모든 테이블 생성 후에 생성됩니다

-- ===============================================
-- 6. 행정동 경계 테이블
-- ===============================================

CREATE TABLE admin_boundaries (
    id SERIAL PRIMARY KEY,
    adm_cd VARCHAR(20) UNIQUE NOT NULL,        -- 행정동 코드 (11140680)
    adm_cd2 VARCHAR(20),                       -- 행정동 코드2 (1144068000)
    adm_nm VARCHAR(200) NOT NULL,              -- 행정동 전체명 (서울특별시 마포구 합정동)
    sgg VARCHAR(10),                           -- 시군구 코드 (11440)
    sido VARCHAR(10),                          -- 시도 코드 (11)
    sidonm VARCHAR(50) NOT NULL,               -- 시도명 (서울특별시)
    sggnm VARCHAR(50) NOT NULL,                -- 시군구명 (마포구)
    admin_dong_name VARCHAR(100) NOT NULL,     -- 행정동명 (합정동)
    geometry GEOMETRY(MULTIPOLYGON, 4326),     -- 행정동 경계 폴리곤
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 행정동 경계 테이블 인덱스
CREATE INDEX idx_admin_boundaries_geom ON admin_boundaries USING GIST (geometry);
CREATE INDEX idx_admin_boundaries_sgg ON admin_boundaries (sggnm);
CREATE INDEX idx_admin_boundaries_adm_cd ON admin_boundaries (adm_cd);
CREATE INDEX idx_admin_boundaries_dong_name ON admin_boundaries (admin_dong_name);
CREATE INDEX idx_admin_boundaries_sido ON admin_boundaries (sidonm);

-- ===============================================
-- 7. 공간 매핑 테이블 (성능 최적화용)
-- ===============================================

CREATE TABLE spatial_mapping (
    node_id VARCHAR(50) PRIMARY KEY,              -- 정류장ID (PK & FK)
    
    -- 계층 정보
    sido_code VARCHAR(10) DEFAULT '11',           -- 시도 코드 (서울: 11)
    sido_name VARCHAR(50) DEFAULT '서울특별시',    -- 시도명
    sgg_code VARCHAR(10) NOT NULL,                -- 시군구 코드
    sgg_name VARCHAR(50) NOT NULL,                -- 시군구명 (강남구, 서초구 등)
    adm_code VARCHAR(20),                         -- 행정동 코드
    adm_name VARCHAR(100),                        -- 행정동명
    
    -- 추가 메타데이터
    is_seoul BOOLEAN DEFAULT TRUE,                -- 서울시 소속 여부
    is_major_stop BOOLEAN DEFAULT FALSE,          -- 주요 정류장 여부
    stop_type INTEGER,                            -- 정류장 유형 (bus_stops.node_type 복사)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (node_id) REFERENCES bus_stops(node_id) ON DELETE CASCADE
);

-- 공간 매핑 테이블 인덱스 (쿼리 성능 최적화)
CREATE INDEX idx_spatial_sgg_name ON spatial_mapping (sgg_name);
CREATE INDEX idx_spatial_sgg_code ON spatial_mapping (sgg_code);
CREATE INDEX idx_spatial_adm_code ON spatial_mapping (adm_code);
CREATE INDEX idx_spatial_hierarchy ON spatial_mapping (sido_code, sgg_code, adm_code);
CREATE INDEX idx_spatial_sgg_composite ON spatial_mapping (sgg_name, node_id);
-- Covering index for better performance
CREATE INDEX idx_spatial_covering ON spatial_mapping (sgg_name) INCLUDE (node_id, adm_name);

-- 테이블 생성 후 트리거 생성
CREATE TRIGGER update_admin_boundaries_updated_at 
    BEFORE UPDATE ON admin_boundaries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_spatial_mapping_updated_at 
    BEFORE UPDATE ON spatial_mapping
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===============================================
-- 데이터 품질 확인용 뷰 (모든 테이블 생성 후)
-- ===============================================
CREATE VIEW data_quality_summary AS
SELECT 
    'bus_stops' as table_name,
    COUNT(*) as total_records,
    COUNT(CASE WHEN coordinates IS NOT NULL THEN 1 END) as records_with_coordinates,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_records
FROM bus_stops
UNION ALL
SELECT 
    'bus_routes' as table_name,
    COUNT(*) as total_records,
    COUNT(CASE WHEN total_distance > 0 THEN 1 END) as records_with_distance,
    COUNT(CASE WHEN is_operating = TRUE THEN 1 END) as operating_routes
FROM bus_routes
UNION ALL
SELECT 
    'route_stops' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_mappings
FROM route_stops
UNION ALL
SELECT 
    'admin_boundaries' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT sggnm) as unique_districts,
    COUNT(CASE WHEN geometry IS NOT NULL THEN 1 END) as records_with_geometry
FROM admin_boundaries
UNION ALL
SELECT 
    'spatial_mapping' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT sgg_name) as unique_districts,
    COUNT(CASE WHEN is_seoul = TRUE THEN 1 END) as seoul_stops
FROM spatial_mapping;

-- ===============================================
-- 완료 메시지
-- ===============================================

DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE '서울시 교통 데이터 스키마 초기화 완료';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '생성된 테이블:';
    RAISE NOTICE '  - bus_stops (정류장)';
    RAISE NOTICE '  - bus_routes (노선)';
    RAISE NOTICE '  - operation_schedules (운행스케줄)';
    RAISE NOTICE '  - route_details (노선상세)';
    RAISE NOTICE '  - route_stops (노선-정류장 매핑)';
    RAISE NOTICE '  - admin_boundaries (행정동 경계)';
    RAISE NOTICE '  - spatial_mapping (공간 매핑 - 정류장/구/동 관계)';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '데이터 로드 후 다음 함수를 실행하세요:';
    RAISE NOTICE '  SELECT update_geometry_fields();';
    RAISE NOTICE '===========================================';
END $$;