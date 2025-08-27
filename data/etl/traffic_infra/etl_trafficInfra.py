# etl/etl_pipeline.py
# Seoul Bus Infrastructure ETL Pipeline

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import logging
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SeoulBusETL:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        self.cur = None

    def connect_db(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def close_db(self):
        """데이터베이스 연결 종료"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def process_bus_stops(self, file_path):
        """정류장(노드) 정보 처리 (seoul_node_info.csv)"""
        logger.info(f"Processing bus stops from {file_path}")
        
        try:
            # 기존 데이터 삭제 (CASCADE로 연관 데이터도 삭제됨)
            self.cur.execute("TRUNCATE bus_stops CASCADE;")
            logger.info("Existing bus_stops data deleted (with CASCADE)")
            self.conn.commit()
            
            # CSV 읽기
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Korean to English column mapping
            column_mapping = {
                '노드ID': 'node_id',
                '노드명': 'node_name', 
                '노드설명': 'node_description',
                '노드유형': 'node_type',
                '좌표X': 'coordinates_x',
                '좌표Y': 'coordinates_y',
                '맵핑좌표X': 'mapping_x',
                '맵핑좌표Y': 'mapping_y',
                '정류장번호': 'node_num',
                '표준코드여부(1:표준/0:비표준)': 'is_standard',
                '사용여부': 'is_active'
            }
            
            df = df.rename(columns=column_mapping)
            
            # 모든 노드 타입 포함 (정류장 + 교차로 + 기타 노드들)
            # df = df[df['node_type'] == 0]  # 필터링 제거
            
            # 중복 제거
            df = df.drop_duplicates(subset=['node_id'])
            
            # 데이터 타입 변환
            df['coordinates_x'] = pd.to_numeric(df['coordinates_x'], errors='coerce')
            df['coordinates_y'] = pd.to_numeric(df['coordinates_y'], errors='coerce')
            df['mapping_x'] = pd.to_numeric(df['mapping_x'], errors='coerce')
            df['mapping_y'] = pd.to_numeric(df['mapping_y'], errors='coerce')
            df['node_type'] = pd.to_numeric(df['node_type'], errors='coerce').fillna(0).astype(int)
            df['is_standard'] = df['is_standard'].astype(bool)
            df['is_active'] = df['is_active'].astype(bool)
            
            # 유효한 좌표가 있는 정류장만 처리
            df = df.dropna(subset=['coordinates_x', 'coordinates_y'])
            
            # NULL 값 처리
            df = df.fillna({
                'node_description': '',
                'node_num': '',
                'mapping_x': df['coordinates_x'],
                'mapping_y': df['coordinates_y']
            })
            
            # DB 삽입
            insert_query = """
                INSERT INTO bus_stops (
                    node_id, node_name, node_description, node_num, node_type,
                    coordinates_x, coordinates_y, mapping_x, mapping_y,
                    is_standard, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (node_id) DO UPDATE SET
                    node_name = EXCLUDED.node_name,
                    node_description = EXCLUDED.node_description,
                    node_num = EXCLUDED.node_num,
                    coordinates_x = EXCLUDED.coordinates_x,
                    coordinates_y = EXCLUDED.coordinates_y,
                    mapping_x = EXCLUDED.mapping_x,
                    mapping_y = EXCLUDED.mapping_y,
                    is_standard = EXCLUDED.is_standard,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            records = []
            for _, row in df.iterrows():
                records.append((
                    row['node_id'],
                    row['node_name'],
                    row['node_description'],
                    str(row['node_num']) if pd.notna(row['node_num']) else '',
                    int(row['node_type']),
                    float(row['coordinates_x']),
                    float(row['coordinates_y']),
                    float(row['mapping_x']),
                    float(row['mapping_y']),
                    bool(row['is_standard']),
                    bool(row['is_active'])
                ))
            
            execute_batch(self.cur, insert_query, records)
            self.conn.commit()
            
            logger.info(f"Inserted/Updated {len(records)} bus stop records")
            
        except Exception as e:
            logger.error(f"Error processing bus stops: {e}")
            self.conn.rollback()
            raise

    def _decimal_to_time(self, decimal_time):
        """소수 시간을 TIME 형식으로 변환 (0.0400 -> 04:00:00)"""
        if pd.isna(decimal_time) or decimal_time == 0:
            return None
        
        try:
            # 소수를 분단위로 변환
            total_minutes = int(decimal_time * 1440)  # 1440 = 24*60
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            # 24시간 넘는 경우 모듈로 처리
            hours = hours % 24
            
            return f"{hours:02d}:{minutes:02d}:00"
        except:
            return None

    def process_route_info(self, file_path):
        """노선 정보 처리 (seoul_route_info.csv)"""
        logger.info(f"Processing route info from {file_path}")
        
        try:
            # 기존 데이터 삭제 (CASCADE로 연관 데이터도 삭제됨)
            self.cur.execute("TRUNCATE bus_routes CASCADE;")
            logger.info("Existing bus_routes data deleted (with CASCADE)")
            self.conn.commit()
            
            # CSV 읽기
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Korean to English column mapping
            column_mapping = {
                '노선ID': 'route_id',
                '노선명': 'route_name',
                '노선유형': 'route_type',
                '지역ID': 'region_id',
                '거리': 'total_distance',
                '기점명(인가정보)': 'start_point',
                '종점명(인가정보)': 'end_point',
                '인가선수': 'authorized_vehicles',
                '운행여부': 'is_operating',
                '배차': 'weekday_interval',
                '배차(토요일)': 'saturday_interval', 
                '배차(공휴일)': 'holiday_interval',
                '첫차시간': 'weekday_first_time',
                '막차시간': 'weekday_last_time',
                '첫차시간(토요일)': 'saturday_first_time',
                '막차시간(토요일)': 'saturday_last_time',
                '첫차시간(공휴일)': 'holiday_first_time',
                '막차시간(공휴일)': 'holiday_last_time',
                '최소배차': 'min_interval',
                '최대배차': 'max_interval',
                '운행소요시간': 'total_operation_time',
                '종점대기시간': 'terminal_waiting_time',
                '곡률도': 'curvature',
                '예비차량건수': 'spare_vehicles',
                '최고속도': 'max_speed',
                '평균속도': 'avg_speed'
            }
            
            df = df.rename(columns=column_mapping)
            
            # 중복 제거
            df = df.drop_duplicates(subset=['route_id'])
            
            # 데이터 타입 변환 및 NULL 처리
            df['route_type'] = pd.to_numeric(df['route_type'], errors='coerce').fillna(0).astype(int)
            df['total_distance'] = pd.to_numeric(df['total_distance'], errors='coerce')
            df['authorized_vehicles'] = pd.to_numeric(df['authorized_vehicles'], errors='coerce').fillna(0).astype(int)
            df['is_operating'] = df['is_operating'].astype(bool)
            
            # 시간 변환 (decimal to TIME)
            time_columns = ['weekday_first_time', 'weekday_last_time', 'saturday_first_time', 
                           'saturday_last_time', 'holiday_first_time', 'holiday_last_time']
            for col in time_columns:
                df[col] = df[col].apply(self._decimal_to_time)
            
            # 배차간격 변환
            interval_columns = ['weekday_interval', 'saturday_interval', 'holiday_interval', 
                              'min_interval', 'max_interval']
            for col in interval_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            # NULL 값 처리
            df = df.fillna({
                'route_name': '',
                'region_id': '',
                'start_point': '',
                'end_point': '',
                'total_operation_time': 0,
                'terminal_waiting_time': 0,
                'curvature': 0,
                'spare_vehicles': 0,
                'max_speed': 0,
                'avg_speed': 0
            })
            
            # 노선 기본 정보 삽입
            insert_routes_query = """
                INSERT INTO bus_routes (
                    route_id, route_name, route_type, region_id, total_distance,
                    start_point, end_point, authorized_vehicles, is_operating
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_id) DO UPDATE SET
                    route_name = EXCLUDED.route_name,
                    route_type = EXCLUDED.route_type,
                    region_id = EXCLUDED.region_id,
                    total_distance = EXCLUDED.total_distance,
                    start_point = EXCLUDED.start_point,
                    end_point = EXCLUDED.end_point,
                    authorized_vehicles = EXCLUDED.authorized_vehicles,
                    is_operating = EXCLUDED.is_operating,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            routes_records = []
            for _, row in df.iterrows():
                routes_records.append((
                    row['route_id'],
                    row['route_name'],
                    int(row['route_type']),
                    row['region_id'],
                    row['total_distance'] if pd.notna(row['total_distance']) else None,
                    row['start_point'],
                    row['end_point'],
                    int(row['authorized_vehicles']),
                    bool(row['is_operating'])
                ))
            
            execute_batch(self.cur, insert_routes_query, routes_records)
            
            # 운행 스케줄 정보 삽입
            insert_schedules_query = """
                INSERT INTO operation_schedules (
                    route_id, weekday_interval, weekday_first_time, weekday_last_time,
                    saturday_interval, saturday_first_time, saturday_last_time,
                    holiday_interval, holiday_first_time, holiday_last_time,
                    min_interval, max_interval
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_id) DO UPDATE SET
                    weekday_interval = EXCLUDED.weekday_interval,
                    weekday_first_time = EXCLUDED.weekday_first_time,
                    weekday_last_time = EXCLUDED.weekday_last_time,
                    saturday_interval = EXCLUDED.saturday_interval,
                    saturday_first_time = EXCLUDED.saturday_first_time,
                    saturday_last_time = EXCLUDED.saturday_last_time,
                    holiday_interval = EXCLUDED.holiday_interval,
                    holiday_first_time = EXCLUDED.holiday_first_time,
                    holiday_last_time = EXCLUDED.holiday_last_time,
                    min_interval = EXCLUDED.min_interval,
                    max_interval = EXCLUDED.max_interval,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            schedules_records = []
            for _, row in df.iterrows():
                schedules_records.append((
                    row['route_id'],
                    int(row['weekday_interval']),
                    row['weekday_first_time'],
                    row['weekday_last_time'],
                    int(row['saturday_interval']),
                    row['saturday_first_time'],
                    row['saturday_last_time'],
                    int(row['holiday_interval']),
                    row['holiday_first_time'],
                    row['holiday_last_time'],
                    int(row['min_interval']) if row['min_interval'] else None,
                    int(row['max_interval']) if row['max_interval'] else None
                ))
            
            execute_batch(self.cur, insert_schedules_query, schedules_records)
            
            # 노선 상세 정보 삽입
            insert_details_query = """
                INSERT INTO route_details (
                    route_id, total_operation_time, terminal_waiting_time, curvature,
                    spare_vehicles, max_speed, avg_speed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_id) DO UPDATE SET
                    total_operation_time = EXCLUDED.total_operation_time,
                    terminal_waiting_time = EXCLUDED.terminal_waiting_time,
                    curvature = EXCLUDED.curvature,
                    spare_vehicles = EXCLUDED.spare_vehicles,
                    max_speed = EXCLUDED.max_speed,
                    avg_speed = EXCLUDED.avg_speed,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            details_records = []
            for _, row in df.iterrows():
                details_records.append((
                    row['route_id'],
                    int(row['total_operation_time']),
                    int(row['terminal_waiting_time']),
                    float(row['curvature']) if pd.notna(row['curvature']) else None,
                    int(row['spare_vehicles']),
                    int(row['max_speed']) if row['max_speed'] else None,
                    int(row['avg_speed']) if row['avg_speed'] else None
                ))
            
            execute_batch(self.cur, insert_details_query, details_records)
            self.conn.commit()
            
            logger.info(f"Inserted/Updated {len(routes_records)} route records")
            logger.info(f"Inserted/Updated {len(schedules_records)} schedule records")
            logger.info(f"Inserted/Updated {len(details_records)} detail records")
            
        except Exception as e:
            logger.error(f"Error processing route info: {e}")
            self.conn.rollback()
            raise

    def process_route_stops(self, file_path):
        """노선-정류장 매핑 처리 (seoul_route_node.csv)"""
        logger.info(f"Processing route-stops mapping from {file_path}")
        
        try:
            # CSV 읽기
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Korean to English column mapping
            column_mapping = {
                '노선ID': 'route_id',
                '노드ID': 'stop_id',
                '노드순번': 'node_sequence',
                '정류장순번': 'stop_sequence',
                '구간ID': 'section_id',
                '정류장구간ID': 'stop_section_id',
                '교차로구간ID': 'intersection_section_id',
                '링크ID': 'link_id',
                '구간거리누계': 'cumulative_section_distance',
                '정류장거리누계': 'cumulative_stop_distance',
                '방향안내': 'direction_guide',
                '사용여부': 'is_active'
            }
            
            df = df.rename(columns=column_mapping)
            
            # 데이터 타입 변환
            df['node_sequence'] = pd.to_numeric(df['node_sequence'], errors='coerce').astype(int)
            df['stop_sequence'] = pd.to_numeric(df['stop_sequence'], errors='coerce')
            df['cumulative_section_distance'] = pd.to_numeric(df['cumulative_section_distance'], errors='coerce')
            df['cumulative_stop_distance'] = pd.to_numeric(df['cumulative_stop_distance'], errors='coerce')
            df['is_active'] = df['is_active'].astype(bool)
            
            # 중복 제거 및 정제
            df = df.drop_duplicates(subset=['route_id', 'node_sequence'])
            df = df.dropna(subset=['route_id', 'stop_id', 'node_sequence'])
            
            # 실제 존재하는 stop_id만 필터링 (외래키 제약조건 위반 방지)
            valid_stop_ids = self._get_valid_stop_ids()
            df['stop_id_str'] = df['stop_id'].astype(str)
            df = df[df['stop_id_str'].isin(valid_stop_ids)]
            
            # route_id 유효성 검증
            valid_route_ids = self._get_valid_route_ids()
            df['route_id_str'] = df['route_id'].astype(str)
            df = df[df['route_id_str'].isin(valid_route_ids)]
            
            logger.info(f"Records after validation: {len(df)}")
            
            # NULL 값 처리
            df = df.fillna({
                'section_id': '',
                'stop_section_id': '',
                'intersection_section_id': '',
                'link_id': '',
                'direction_guide': ''
            })
            
            # DB 삽입
            insert_query = """
                INSERT INTO route_stops (
                    route_id, stop_id, node_sequence, stop_sequence, section_id,
                    stop_section_id, intersection_section_id, link_id,
                    cumulative_section_distance, cumulative_stop_distance,
                    direction_guide, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_id, node_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    stop_sequence = EXCLUDED.stop_sequence,
                    section_id = EXCLUDED.section_id,
                    stop_section_id = EXCLUDED.stop_section_id,
                    intersection_section_id = EXCLUDED.intersection_section_id,
                    link_id = EXCLUDED.link_id,
                    cumulative_section_distance = EXCLUDED.cumulative_section_distance,
                    cumulative_stop_distance = EXCLUDED.cumulative_stop_distance,
                    direction_guide = EXCLUDED.direction_guide,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            records = []
            for _, row in df.iterrows():
                records.append((
                    row['route_id'],
                    row['stop_id'],
                    int(row['node_sequence']),
                    int(row['stop_sequence']) if pd.notna(row['stop_sequence']) else None,
                    row['section_id'],
                    row['stop_section_id'],
                    row['intersection_section_id'],
                    row['link_id'],
                    row['cumulative_section_distance'],
                    row['cumulative_stop_distance'],
                    row['direction_guide'],
                    bool(row['is_active'])
                ))
            
            execute_batch(self.cur, insert_query, records)
            self.conn.commit()
            
            logger.info(f"Inserted/Updated {len(records)} route-stop mappings")
            
        except Exception as e:
            logger.error(f"Error processing route-stops mapping: {e}")
            self.conn.rollback()
            raise

    def _get_valid_stop_ids(self):
        """DB에서 유효한 stop_id 목록 조회"""
        self.cur.execute("SELECT node_id FROM bus_stops WHERE is_active = true")
        valid_stop_ids = set(str(row[0]) for row in self.cur.fetchall())
        logger.info(f"Loaded {len(valid_stop_ids)} valid stop IDs from database")
        return valid_stop_ids
    
    def _get_valid_route_ids(self):
        """DB에서 유효한 route_id 목록 조회"""
        self.cur.execute("SELECT route_id FROM bus_routes")  # 운행 여부 조건 제거
        valid_route_ids = set(str(row[0]) for row in self.cur.fetchall())
        logger.info(f"Loaded {len(valid_route_ids)} valid route IDs from database")
        return valid_route_ids

    def update_geometry_fields(self):
        """좌표 데이터에서 PostGIS POINT 필드 업데이트"""
        logger.info("Updating PostGIS geometry fields...")
        
        try:
            # bus_stops 테이블의 geometry 필드 업데이트
            update_query = """
                UPDATE bus_stops 
                SET coordinates = ST_SetSRID(ST_MakePoint(coordinates_x, coordinates_y), 4326)
                WHERE coordinates_x IS NOT NULL AND coordinates_y IS NOT NULL;
                
                UPDATE bus_stops 
                SET mapping_coordinates = ST_SetSRID(ST_MakePoint(mapping_x, mapping_y), 4326)
                WHERE mapping_x IS NOT NULL AND mapping_y IS NOT NULL;
            """
            
            self.cur.execute(update_query)
            self.conn.commit()
            
            logger.info("PostGIS geometry fields updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating geometry fields: {e}")
            self.conn.rollback()
            raise

    def process_admin_boundaries(self, file_path):
        """행정동 경계 데이터 처리 (HangJeongDong_ver20250401.geojson)"""
        logger.info(f"Processing administrative boundaries from {file_path}")
        
        try:
            # GeoJSON 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            logger.info(f"Loaded GeoJSON with {len(geojson_data['features'])} features")
            
            # 서울시 데이터만 필터링
            seoul_features = []
            for feature in geojson_data['features']:
                props = feature['properties']
                
                # 서울특별시 데이터만 선택
                if props.get('sidonm') == '서울특별시':
                    seoul_features.append({
                        'adm_cd': props.get('adm_cd'),        # 행정동 코드
                        'adm_cd2': props.get('adm_cd2'),      # 행정동 코드2
                        'adm_nm': props.get('adm_nm'),        # 행정동 전체명
                        'sgg': props.get('sgg'),              # 시군구 코드
                        'sido': props.get('sido'),            # 시도 코드
                        'sidonm': props.get('sidonm'),        # 시도명
                        'sggnm': props.get('sggnm'),          # 시군구명
                        'admin_dong_name': self._extract_dong_name(props.get('adm_nm', '')),  # 행정동명 추출
                        'geometry': json.dumps(feature['geometry'])  # geometry를 JSON 문자열로
                    })
            
            logger.info(f"Filtered {len(seoul_features)} Seoul administrative boundaries")
            
            # 기존 데이터 삭제 (서울시 데이터만)
            self.cur.execute("DELETE FROM admin_boundaries WHERE sidonm = '서울특별시';")
            logger.info("Existing Seoul administrative boundary data deleted")
            
            # 배치 삽입
            insert_query = """
                INSERT INTO admin_boundaries (
                    adm_cd, adm_cd2, adm_nm, sgg, sido, sidonm, sggnm, admin_dong_name, geometry
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromGeoJSON(%s))
            """
            
            records = []
            for item in seoul_features:
                records.append((
                    item['adm_cd'],
                    item['adm_cd2'], 
                    item['adm_nm'],
                    item['sgg'],
                    item['sido'],
                    item['sidonm'],
                    item['sggnm'],
                    item['admin_dong_name'],
                    item['geometry']
                ))
            
            execute_batch(self.cur, insert_query, records)
            self.conn.commit()
            
            logger.info(f"Inserted {len(records)} administrative boundary records")
            
        except Exception as e:
            logger.error(f"Error processing administrative boundaries: {e}")
            self.conn.rollback()
            raise
    
    def _extract_dong_name(self, full_name):
        """행정동 전체명에서 동명만 추출"""
        if not full_name:
            return ''
        
        try:
            # "서울특별시 마포구 합정동" -> "합정동"
            parts = full_name.split(' ')
            if len(parts) >= 3:
                return parts[2]  # 동명 부분
            return full_name
        except:
            return full_name

    def build_spatial_mapping(self):
        """공간 매핑 테이블 구축 (성능 최적화용)"""
        logger.info("Building spatial mapping table for performance optimization...")
        
        try:
            # 기존 매핑 데이터 삭제
            self.cur.execute("DELETE FROM spatial_mapping;")
            logger.info("Existing spatial mapping data deleted")
            self.conn.commit()
            
            # 배치 처리를 위해 구별로 나누어 처리
            district_query = """
                SELECT DISTINCT sggnm, sgg 
                FROM admin_boundaries 
                WHERE sidonm = '서울특별시'
                ORDER BY sggnm;
            """
            self.cur.execute(district_query)
            districts = self.cur.fetchall()
            
            logger.info(f"Processing {len(districts)} districts...")
            total_count = 0
            
            for district_name, district_code in districts:
                # 각 구별로 공간 조인 수행
                mapping_query = """
                    INSERT INTO spatial_mapping (
                        node_id, 
                        sido_code, sido_name,
                        sgg_code, sgg_name,
                        adm_code, adm_name,
                        stop_type,
                        is_seoul,
                        is_major_stop
                    )
                    SELECT DISTINCT ON (bs.node_id)
                        bs.node_id,
                        ab.sido as sido_code,
                        ab.sidonm as sido_name,
                        ab.sgg as sgg_code,
                        ab.sggnm as sgg_name,
                        ab.adm_cd as adm_code,
                        ab.admin_dong_name as adm_name,
                        bs.node_type as stop_type,
                        TRUE as is_seoul,
                        CASE 
                            WHEN bs.node_type IN (1, 3, 4) THEN TRUE 
                            ELSE FALSE 
                        END as is_major_stop
                    FROM bus_stops bs
                    JOIN admin_boundaries ab ON ST_Within(bs.coordinates, ab.geometry)
                    WHERE bs.is_active = true 
                      AND ab.sidonm = '서울특별시'
                      AND ab.sggnm = %s
                      AND bs.coordinates IS NOT NULL
                    ORDER BY bs.node_id, ab.adm_cd;
                """
                
                self.cur.execute(mapping_query, (district_name,))
                district_count = self.cur.rowcount
                total_count += district_count
                self.conn.commit()
                
                logger.info(f"  - {district_name}: {district_count:,} stops mapped")
            
            logger.info(f"Created total {total_count:,} spatial mappings")
            
            # 매핑 결과 검증
            verification_query = """
                SELECT 
                    sgg_name,
                    COUNT(*) as stop_count
                FROM spatial_mapping
                GROUP BY sgg_name
                ORDER BY sgg_name;
            """
            
            self.cur.execute(verification_query)
            results = self.cur.fetchall()
            
            logger.info("District-stop mapping verification:")
            total_stops = 0
            for district, count in results:
                logger.info(f"  {district}: {count} stops")
                total_stops += count
            logger.info(f"  Total mapped stops: {total_stops}")
            
            # 중복 확인
            duplicate_check_query = """
                SELECT 
                    COUNT(*) as total_mappings,
                    COUNT(DISTINCT node_id) as unique_nodes
                FROM spatial_mapping;
            """
            
            self.cur.execute(duplicate_check_query)
            total, unique = self.cur.fetchone()
            
            if total != unique:
                logger.warning(f"Found {total - unique} duplicate mappings")
            else:
                logger.info("No duplicate mappings found")
                
        except Exception as e:
            logger.error(f"Error building district-stop mapping: {e}")
            self.conn.rollback()
            raise

    def verify_data(self):
        """데이터 검증 및 통계 출력"""
        logger.info("Verifying loaded data...")
        
        queries = [
            ("Total routes", "SELECT COUNT(*) FROM bus_routes"),
            ("Total stops", "SELECT COUNT(*) FROM bus_stops"),
            ("Total route-stop mappings", "SELECT COUNT(*) FROM route_stops"),
            ("Total operation schedules", "SELECT COUNT(*) FROM operation_schedules"),
            ("Total route details", "SELECT COUNT(*) FROM route_details"),
            ("Total admin boundaries", "SELECT COUNT(*) FROM admin_boundaries"),
            ("Total spatial mappings", "SELECT COUNT(*) FROM spatial_mapping"),
            ("Admin boundaries by district", """
                SELECT sggnm, COUNT(*) 
                FROM admin_boundaries 
                WHERE sidonm = '서울특별시'
                GROUP BY sggnm 
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """),
            ("Top 5 routes by distance", """
                SELECT route_name, total_distance
                FROM bus_routes 
                WHERE total_distance IS NOT NULL
                ORDER BY total_distance DESC 
                LIMIT 5
            """),
            ("Route type distribution", """
                SELECT route_type, COUNT(*) 
                FROM bus_routes 
                GROUP BY route_type 
                ORDER BY route_type
            """)
        ]
                
        for title, query in queries:
            self.cur.execute(query)
            result = self.cur.fetchall()
            logger.info(f"{title}: {result}")

    def run_etl(self, data_dir):
        """전체 Seoul Bus ETL 프로세스 실행"""
        logger.info("Starting Seoul Bus Infrastructure ETL process...")
        
        try:
            self.connect_db()

            # 1. 정류장(노드) 정보 처리
            bus_stops_path = os.path.join(data_dir, 'processed/busInfra/seoul_node_info_filtered.csv')
            if os.path.exists(bus_stops_path):
                self.process_bus_stops(bus_stops_path)
            else:
                logger.warning(f"Bus stops file not found: {bus_stops_path}")
            
            # 2. 노선 정보 처리
            route_info_path = os.path.join(data_dir, 'processed/busInfra/seoul_route_info_filtered.csv')
            if os.path.exists(route_info_path):
                self.process_route_info(route_info_path)
            else:
                logger.warning(f"Route info file not found: {route_info_path}")
            
            # 3. 노선-정류장 매핑 처리
            route_stops_path = os.path.join(data_dir, 'processed/busInfra/seoul_route_node_filtered.csv')
            if os.path.exists(route_stops_path):
                self.process_route_stops(route_stops_path)
            else:
                logger.warning(f"Route-stops mapping file not found: {route_stops_path}")
            
            # 4. 행정동 경계 데이터 처리
            admin_boundaries_path = os.path.join(data_dir, 'processed/busInfra/HangJeongDong_ver20250401.geojson')
            if os.path.exists(admin_boundaries_path):
                self.process_admin_boundaries(admin_boundaries_path)
            else:
                logger.warning(f"Administrative boundaries file not found: {admin_boundaries_path}")
            
            # 5. PostGIS geometry 필드 업데이트
            self.update_geometry_fields()

            # 6. 공간 매핑 테이블 구축 (성능 최적화)
            self.build_spatial_mapping()

            # 7. 데이터 검증
            self.verify_data()

            logger.info("Seoul Bus ETL process completed successfully!")
            
        except Exception as e:
            logger.error(f"Seoul Bus ETL process failed: {e}")
            raise
        finally:
            self.close_db()


# ETL 실행 스크립트
if __name__ == "__main__":
    import sys
    
    # 데이터베이스 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 데이터 디렉토리
    data_dir = sys.argv[1] if len(sys.argv) > 1 else '/data'
    
    # Seoul Bus ETL 실행
    etl = SeoulBusETL(db_config)
    etl.run_etl(data_dir)