# traffic_etl.py
# Seoul Traffic Data ETL Pipeline for Historical Traffic Analysis
# Fetches data from 5 APIs and loads into TimescaleDB with Tall Table structure

import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
import time
import traceback
import gc
from math import ceil

# psutil을 선택적으로 import (없어도 동작하도록)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SeoulTrafficETL:
    """서울시 교통 데이터 ETL 파이프라인"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        
        # API 설정 (.env에서 로드)
        self.api_config = {
            'base_url': os.getenv('SEOUL_API_BASE_URL', 'https://t-data.seoul.go.kr/apig/apiman-gateway/tapi'),
            'timeout': int(os.getenv('API_TIMEOUT', 30)),
            'max_retries': int(os.getenv('API_MAX_RETRIES', 3)),
            'apis': {
                'API1': {
                    'name': 'API1_STATION_PASSENGER',
                    'endpoint': os.getenv('API1_ENDPOINT', 'TaimsTpssStaRouteInfoH/1.0'),
                    'key': os.getenv('API1_STATION_RIDERSHIP_KEY'),
                    'table': 'station_passenger_history'
                },
                'API2': {
                    'name': 'API2_SECTION_PASSENGER', 
                    'endpoint': os.getenv('API2_ENDPOINT', 'TaimsTpssA18RouteSection/1.0'),
                    'key': os.getenv('API2_SECTION_RIDERSHIP_KEY'),
                    'table': 'section_passenger_history'
                },
                'API3': {
                    'name': 'API3_EMD_OD',
                    'endpoint': os.getenv('API3_ENDPOINT', 'TaimsTpssEmdOdTc/1.0'), 
                    'key': os.getenv('API3_EMD_OD_KEY'),
                    'table': 'od_traffic_history'
                },
                'API4': {
                    'name': 'API4_SECTION_SPEED',
                    'endpoint': os.getenv('API4_ENDPOINT', 'TaimsTpssRouteSectionSpeedH/1.0'),
                    'key': os.getenv('API4_SECTION_SPEED_KEY'), 
                    'table': 'section_speed_history'
                },
            }
        }
        
        # 배치 크기 설정 (메모리 16GB, Rate Limit 1000회/일 최적화)
        self.api_batch_size = 10000    # API 호출당 레코드 수 (메모리 여유 충분, Rate Limit 안전)
        self.db_batch_size = 1000      # DB 삽입 배치 크기
        self.chunk_size = 500          # Tall Table 변환 청크 크기 (메모리 여유로 증가)
        
        # API 호출 횟수 추적
        self.api_call_counts = {
            'API1': 0, 'API2': 0, 'API3': 0, 'API4': 0
        }
        
        # 현재 처리 중인 날짜 추적
        self.current_processing_date = None
        
        # 서울시 노선 ID 캐시 (Seoul Route Filtering)
        self.seoul_route_ids: Set[str] = set()
        self.seoul_route_names: Set[str] = set()
        self.route_id_to_name: Dict[str, str] = {}
        
        # 필터링 통계 추가
        self.filter_stats = {
            'API1': {'total_fetched': 0, 'seoul_filtered': 0},
            'API2': {'total_fetched': 0, 'seoul_filtered': 0},
            'API4': {'total_fetched': 0, 'seoul_filtered': 0}
        }
        
    def connect_db(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
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
    
    def load_seoul_routes(self):
        """DB에서 서울시 버스 노선 정보 로드 (Seoul Route Filtering)"""
        try:
            logger.info("🚌 Loading Seoul bus route information from database...")
            
            query = """
                SELECT route_id, route_name 
                FROM bus_routes 
                ORDER BY route_id
            """
            
            self.cur.execute(query)
            routes = self.cur.fetchall()
            
            self.seoul_route_ids = set()
            self.seoul_route_names = set()
            self.route_id_to_name = {}
            
            for route in routes:
                route_id = route['route_id']
                route_name = route['route_name']
                
                self.seoul_route_ids.add(route_id)
                self.seoul_route_names.add(route_name)
                self.route_id_to_name[route_id] = route_name
            
            logger.info(f"✅ Loaded {len(self.seoul_route_ids)} Seoul bus routes for filtering")
            logger.info(f"   Route ID range: {min(self.seoul_route_ids)} ~ {max(self.seoul_route_ids)}")
            logger.info(f"   Sample routes: {list(self.seoul_route_ids)[:5]}")
            
        except Exception as e:
            logger.error(f"Failed to load Seoul routes: {e}")
            raise
    
    def is_seoul_route(self, route_id: str, route_name: str = None) -> bool:
        """노선이 서울시 노선인지 확인 (Seoul Route Filtering)"""
        # route_id 기준 우선 확인
        if route_id in self.seoul_route_ids:
            return True
        
        # route_name 기준 보조 확인 (API1에서 사용)
        if route_name and route_name in self.seoul_route_names:
            return True
            
        return False
    
    def _monitor_memory(self, stage: str) -> None:
        """메모리 사용량 모니터링 (feature_generator 방식)"""
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory usage at {stage}: {memory_mb:.2f} MB")
                
                if memory_mb > 2000:  # 2GB 초과시 경고
                    logger.warning(f"High memory usage detected: {memory_mb:.2f} MB")
                    gc.collect()
            except Exception:
                pass  # 메모리 모니터링 실패해도 메인 프로세스는 계속
        else:
            logger.info(f"Processing stage: {stage} (memory monitoring disabled - psutil not available)")
            # psutil 없이도 가비지 컬렉션은 수행
            gc.collect()
    
    def log_etl_status(self, job_name: str, status: str, records_processed: int = 0, 
                      records_inserted: int = 0, records_updated: int = 0, 
                      error_message: str = None, data_date: str = None):
        """ETL 작업 상태를 DB에 기록"""
        try:
            if status == 'RUNNING':
                sql = """
                    UPDATE etl_job_status 
                    SET status = %s, last_run_start = CURRENT_TIMESTAMP, 
                        records_processed = 0, records_inserted = 0, records_updated = 0,
                        error_message = NULL, data_date = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE job_name = %s
                """
                self.cur.execute(sql, (status, data_date, job_name))
            elif status in ['SUCCESS', 'FAILED']:
                sql = """
                    UPDATE etl_job_status 
                    SET status = %s, last_run_end = CURRENT_TIMESTAMP,
                        records_processed = %s, records_inserted = %s, records_updated = %s,
                        error_message = %s, updated_at = CURRENT_TIMESTAMP
                """
                params = (status, records_processed, records_inserted, records_updated, error_message)
                if status == 'SUCCESS':
                    sql += ", last_success = CURRENT_TIMESTAMP"
                sql += " WHERE job_name = %s"
                params += (job_name,)
                self.cur.execute(sql, params)
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log ETL status: {e}")
    
    def log_etl_message(self, job_name: str, log_level: str, message: str, 
                       execution_step: str = None, additional_data: Dict = None):
        """ETL 상세 로그를 DB에 기록"""
        try:
            sql = """
                INSERT INTO etl_job_logs (job_name, log_level, log_message, execution_step, additional_data)
                VALUES (%s, %s, %s, %s, %s)
            """
            self.cur.execute(sql, (job_name, log_level, message, execution_step, 
                                 json.dumps(additional_data) if additional_data else None))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log ETL message: {e}")
    
    def make_api_request(self, api_key: str, endpoint: str, params: Dict, api_name: str = None) -> Optional[Dict]:
        """Seoul API 요청 및 응답 처리 (호출 횟수 추적 포함)"""
        url = f"{self.api_config['base_url']}/{endpoint}"
        
        # API 키를 파라미터에 추가 (api_metadata_extractor.py 방식)
        params_with_key = params.copy()
        params_with_key['apikey'] = api_key
        
        for attempt in range(self.api_config['max_retries']):
            try:
                response = requests.get(
                    url, 
                    params=params_with_key,
                    timeout=self.api_config['timeout'],
                    verify=False  # SSL 검증 비활성화 (api_metadata_extractor.py 방식)
                )
                
                # API 호출 횟수 카운트 (성공/실패 무관하게 카운트)
                if api_name and api_name in self.api_call_counts:
                    self.api_call_counts[api_name] += 1
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"API request successful: {endpoint}, attempt {attempt + 1}, total calls: {self.api_call_counts.get(api_name, 'N/A')}")
                    return data
                elif response.status_code == 500:
                    # 500 에러는 보통 데이터 소진을 의미하므로 첫 번째 시도에서 바로 중단
                    logger.warning(f"API request failed: {response.status_code} (likely end of data), attempt {attempt + 1}, total calls: {self.api_call_counts.get(api_name, 'N/A')}")
                    return None  # 재시도 없이 바로 None 반환
                else:
                    logger.warning(f"API request failed: {response.status_code}, attempt {attempt + 1}, total calls: {self.api_call_counts.get(api_name, 'N/A')}")
                    
            except Exception as e:
                logger.error(f"API request error: {e}, attempt {attempt + 1}")
                
            if attempt < self.api_config['max_retries'] - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return None
    
    def process_api1_station_passenger(self, start_date: str, end_date: str) -> int:
        """API 1: 정류장별 승하차 인원수 처리 (Tall Table 변환)"""
        api_config = self.api_config['apis']['API1']
        job_name = api_config['name']
        
        try:
            # DB 연결 확인
            if not self.conn or self.conn.closed:
                self.connect_db()
                
            self.log_etl_status(job_name, 'RUNNING', data_date=start_date)
            self.log_etl_message(job_name, 'INFO', f'Starting API1 processing: {start_date} to {end_date}', 'API_CALL')
            self._monitor_memory("API1 start")
            
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_inserted = 0
            total_days = (end_dt - current_date).days + 1
            
            while current_date <= end_dt:
                date_str = current_date.strftime('%Y%m%d')
                self.current_processing_date = date_str  # 현재 처리 날짜 추적
                logger.info(f"📅 Processing date: {date_str} ({current_date.strftime('%Y-%m-%d')})")
                
                # API 요청 파라미터 (메모리 효율성을 위해 배치 크기 감소)
                params = {
                    'stdrDe': date_str,
                    'startRow': 1,
                    'rowCnt': self.api_batch_size
                }
                
                page_num = 1
                daily_inserted = 0
                
                while True:
                    params['startRow'] = (page_num - 1) * self.api_batch_size + 1
                    
                    # API 호출 (호출 횟수 추적)
                    response_data = self.make_api_request(
                        api_config['key'], 
                        api_config['endpoint'], 
                        params,
                        'API1'
                    )
                    
                    if not response_data:
                        self.log_etl_message(job_name, 'ERROR', f'API call failed for date {date_str}', 'API_CALL')
                        break
                    
                    # 데이터 추출 (API 응답이 직접 배열)
                    try:
                        if isinstance(response_data, list):
                            items = response_data
                        else:
                            items = response_data.get('TaimsTpssStaRouteInfoH', {}).get('row', [])
                        
                        if not items or len(items) == 0:
                            logger.info(f"No more data available for {date_str} at page {page_num}, moving to next date")
                            break
                        
                        # 🎯 서울시 노선 필터링 (Seoul Route Filtering)
                        seoul_items = []
                        for item in items:
                            route_id = item.get('routeId', '')
                            route_name = item.get('routeNm', '')
                            
                            self.filter_stats['API1']['total_fetched'] += 1
                            
                            if self.is_seoul_route(route_id, route_name):
                                seoul_items.append(item)
                                self.filter_stats['API1']['seoul_filtered'] += 1
                        
                        logger.info(f"  📊 Page {page_num}: {len(items)} total → {len(seoul_items)} Seoul routes")
                        
                        if seoul_items:
                            # 스트리밍 방식으로 청크별 변환 및 즉시 삽입 (서울시 데이터만)
                            inserted_count = self.process_api1_chunk_streaming(seoul_items, date_str)
                            daily_inserted += inserted_count
                            
                        page_num += 1
                        
                        # 페이지 제한 체크 (무한루프 방지)
                        if page_num > 100:  
                            break
                            
                    except Exception as e:
                        self.log_etl_message(job_name, 'ERROR', f'Data processing error for {date_str}: {e}', 'DATA_TRANSFORM')
                        break
                
                total_inserted += daily_inserted
                self.log_etl_message(job_name, 'INFO', f'Processed {date_str}: {daily_inserted} records', 'DB_INSERT')
                current_date += timedelta(days=1)
            
            self.log_etl_status(job_name, 'SUCCESS', records_processed=total_inserted, records_inserted=total_inserted)
            return total_inserted
            
        except Exception as e:
            error_msg = f"API1 processing failed: {str(e)}\n{traceback.format_exc()}"
            self.log_etl_status(job_name, 'FAILED', error_message=error_msg)
            self.log_etl_message(job_name, 'ERROR', error_msg, 'GENERAL')
            raise
    
    def process_api1_chunk_streaming(self, items: List[Dict], date_str: str) -> int:
        """API1 데이터를 스트리밍 방식으로 청크별 변환 및 즉시 삽입 (feature_generator 방식)"""
        total_inserted = 0
        
        # 아이템을 작은 청크로 나누어 처리 (메모리 효율성)
        for i in range(0, len(items), self.chunk_size):
            chunk = items[i:i + self.chunk_size]
            batch_data = []
            
            for item in chunk:
                route_id = item.get('routeId', '')
                node_id = item.get('staId', '')  # station_id → node_id로 매핑
                route_name = item.get('routeNm', '')
                station_name = item.get('staNm', '')
                station_sequence = item.get('staSn', 0)
                
                # 24시간 데이터를 Tall Table로 변환
                for hour in range(24):
                    hour_str = f"{hour:02d}"
                    
                    dispatch_count = int(item.get(f'a05Num{hour_str}h', 0) or 0)
                    ride_passenger = int(item.get(f'ridePnsgerCnt{hour_str}h', 0) or 0) 
                    alight_passenger = int(item.get(f'alghPnsgerCnt{hour_str}h', 0) or 0)
                    
                    batch_data.append((
                        date_str, route_id, node_id, hour,
                        route_name, station_name, station_sequence,
                        dispatch_count, ride_passenger, alight_passenger
                    ))
            
            # 청크별 즉시 삽입 (메모리 절약)
            if batch_data:
                inserted_count = self.insert_station_passenger_batch(batch_data)
                total_inserted += inserted_count
                
                # 메모리 정리
                del batch_data
                
        return total_inserted
    
    def process_api2_chunk_streaming(self, items: List[Dict], date_str: str) -> int:
        """API2 데이터를 스트리밍 방식으로 청크별 변환 및 즉시 삽입"""
        total_inserted = 0
        
        # 아이템을 작은 청크로 나누어 처리
        for i in range(0, len(items), self.chunk_size):
            chunk = items[i:i + self.chunk_size]
            batch_data = []
            
            for item in chunk:
                route_id = item.get('routeId', '')
                from_node_id = item.get('fromStaId', '')
                to_node_id = item.get('toStaId', '')
                station_sequence = item.get('staSn', 0)
                
                # 24시간 데이터를 Tall Table로 변환 (최적화된 스키마)
                daily_total_passengers = int(item.get('a18SumLoadPsng', 0) or 0)
                
                for hour in range(24):
                    hour_str = f"{hour:02d}"
                    
                    # API2 검증 완료: a18SumLoadPsngNum{hour}h 필드만 유효
                    passenger_count = item.get(f'a18SumLoadPsngNum{hour_str}h')
                    
                    # NULL이 아닌 경우에만 정수 변환
                    if passenger_count is not None:
                        try:
                            passenger_count = int(passenger_count)
                        except (ValueError, TypeError):
                            passenger_count = None
                    else:
                        passenger_count = None
                    
                    batch_data.append((
                        date_str, route_id, from_node_id, to_node_id, hour, station_sequence,
                        passenger_count, daily_total_passengers
                    ))
            
            # 청크별 즉시 삽입
            if batch_data:
                inserted_count = self.insert_section_passenger_batch(batch_data)
                total_inserted += inserted_count
                
                # 메모리 정리
                del batch_data
                
        return total_inserted
    
    def process_api4_chunk_streaming(self, items: List[Dict], date_str: str) -> int:
        """API4 데이터를 스트리밍 방식으로 청크별 변환 및 즉시 삽입 (Seoul Route Filtering)"""
        total_inserted = 0
        
        # 아이템을 작은 청크로 나누어 처리
        for i in range(0, len(items), self.chunk_size):
            chunk = items[i:i + self.chunk_size]
            batch_data = []
            
            for item in chunk:
                route_id = item.get('routeId', '')
                
                # Seoul Route Filtering - API4는 route_id만 제공
                self.filter_stats['API4']['total_fetched'] += 1
                if not self.is_seoul_route(route_id):
                    continue  # 서울시 노선이 아니면 건너뛰기
                
                self.filter_stats['API4']['seoul_filtered'] += 1
                
                from_node_id = item.get('fromStaId', '')
                to_node_id = item.get('toStaId', '')
                from_station_sequence = int(item.get('fromStaSn', 0) or 0)
                to_station_sequence = int(item.get('toStaSn', 0) or 0)
                
                # 24시간 데이터를 Tall Table로 변환 (유효한 trip_time만 처리)
                for hour in range(24):
                    hour_str = f"{hour:02d}"
                    
                    # 유효한 데이터만 처리: trip_time (73.9% 유효율)
                    trip_time = int(item.get(f'tripTime{hour_str}h', 0) or 0)
                    
                    batch_data.append((
                        date_str, route_id, from_node_id, to_node_id, hour,
                        from_station_sequence, to_station_sequence, trip_time
                    ))
            
            # 청크별 즉시 삽입
            if batch_data:
                inserted_count = self.insert_section_speed_batch(batch_data)
                total_inserted += inserted_count
                
                # 메모리 정리
                del batch_data
                
        return total_inserted
    
    def insert_station_passenger_batch(self, batch_data: List[Tuple]) -> int:
        """정류장별 승하차 데이터 배치 삽입"""
        if not batch_data:
            return 0
            
        sql = """
            INSERT INTO station_passenger_history (
                record_date, route_id, node_id, hour,
                route_name, station_name, station_sequence,
                dispatch_count, ride_passenger, alight_passenger
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_date, route_id, node_id, hour)
            DO UPDATE SET
                route_name = EXCLUDED.route_name,
                station_name = EXCLUDED.station_name,
                station_sequence = EXCLUDED.station_sequence,
                dispatch_count = EXCLUDED.dispatch_count,
                ride_passenger = EXCLUDED.ride_passenger,
                alight_passenger = EXCLUDED.alight_passenger
        """
        
        execute_batch(self.cur, sql, batch_data, page_size=self.db_batch_size)
        self.conn.commit()
        return len(batch_data)
    
    def process_api2_section_passenger(self, start_date: str, end_date: str) -> int:
        """API 2: 구간별 승객수 처리 (Tall Table 변환)"""
        api_config = self.api_config['apis']['API2']
        job_name = api_config['name']
        
        try:
            # DB 연결 확인
            if not self.conn or self.conn.closed:
                self.connect_db()
                
            self.log_etl_status(job_name, 'RUNNING', data_date=start_date)
            self.log_etl_message(job_name, 'INFO', f'Starting API2 processing: {start_date} to {end_date}', 'API_CALL')
            
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_inserted = 0
            
            while current_date <= end_dt:
                date_str = current_date.strftime('%Y%m%d')
                params = {'stdrDe': date_str, 'startRow': 1, 'rowCnt': self.api_batch_size}
                
                page_num = 1
                daily_inserted = 0
                
                while True:
                    params['startRow'] = (page_num - 1) * self.api_batch_size + 1
                    response_data = self.make_api_request(api_config['key'], api_config['endpoint'], params, 'API2')
                    
                    if not response_data:
                        break
                    
                    try:
                        if isinstance(response_data, list):
                            items = response_data
                        else:
                            items = response_data.get('TaimsTpssA18RouteSection', {}).get('row', [])
                        
                        if not items or len(items) == 0:
                            logger.info(f"No more data available for {date_str} at page {page_num}, moving to next date")
                            break
                        
                        # 🎯 서울시 노선 필터링 (Seoul Route Filtering)
                        seoul_items = []
                        for item in items:
                            route_id = item.get('routeId', '')
                            
                            self.filter_stats['API2']['total_fetched'] += 1
                            
                            if self.is_seoul_route(route_id):
                                seoul_items.append(item)
                                self.filter_stats['API2']['seoul_filtered'] += 1
                        
                        logger.info(f"  📊 API2 Page {page_num}: {len(items)} total → {len(seoul_items)} Seoul routes")
                        
                        if seoul_items:
                            # 스트리밍 방식으로 청크별 변환 및 즉시 삽입 (서울시 데이터만)
                            inserted_count = self.process_api2_chunk_streaming(seoul_items, date_str)
                            daily_inserted += inserted_count
                            
                        page_num += 1
                        if page_num > 100:
                            break
                            
                    except Exception as e:
                        self.log_etl_message(job_name, 'ERROR', f'Data processing error for {date_str}: {e}', 'DATA_TRANSFORM')
                        break
                
                total_inserted += daily_inserted
                self.log_etl_message(job_name, 'INFO', f'Processed {date_str}: {daily_inserted} records', 'DB_INSERT')
                current_date += timedelta(days=1)
            
            self.log_etl_status(job_name, 'SUCCESS', records_processed=total_inserted, records_inserted=total_inserted)
            return total_inserted
            
        except Exception as e:
            error_msg = f"API2 processing failed: {str(e)}\n{traceback.format_exc()}"
            self.log_etl_status(job_name, 'FAILED', error_message=error_msg)
            self.log_etl_message(job_name, 'ERROR', error_msg, 'GENERAL')
            raise
    
    def convert_api2_to_tall_table(self, items: List[Dict], date_str: str) -> List[Tuple]:
        """API2 데이터를 Tall Table 형태로 변환 (최적화된 스키마)"""
        batch_data = []
        
        for item in items:
            route_id = item.get('routeId', '')
            from_node_id = item.get('fromStaId', '')
            to_node_id = item.get('toStaId', '')
            station_sequence = item.get('staSn', 0)
            daily_total_passengers = int(item.get('a18SumLoadPsng', 0) or 0)
            
            # 24시간 데이터를 Tall Table로 변환 (유효 필드만)
            for hour in range(24):
                hour_str = f"{hour:02d}"
                
                # API2 검증 완료: a18SumLoadPsngNum{hour}h 필드만 유효
                passenger_count = item.get(f'a18SumLoadPsngNum{hour_str}h')
                
                # NULL이 아닌 경우에만 정수 변환
                if passenger_count is not None:
                    try:
                        passenger_count = int(passenger_count)
                    except (ValueError, TypeError):
                        passenger_count = None
                else:
                    passenger_count = None
                
                batch_data.append((
                    date_str, route_id, from_node_id, to_node_id, hour, station_sequence,
                    passenger_count, daily_total_passengers
                ))
        
        return batch_data
    
    def insert_section_passenger_batch(self, batch_data: List[Tuple]) -> int:
        """구간별 승객수 데이터 배치 삽입 (최적화된 스키마)"""
        if not batch_data:
            return 0
            
        sql = """
            INSERT INTO section_passenger_history (
                record_date, route_id, from_node_id, to_node_id, hour, station_sequence,
                passenger_count, daily_total_passengers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_date, route_id, from_node_id, to_node_id, hour)
            DO UPDATE SET
                station_sequence = EXCLUDED.station_sequence,
                passenger_count = EXCLUDED.passenger_count,
                daily_total_passengers = EXCLUDED.daily_total_passengers
        """
        
        execute_batch(self.cur, sql, batch_data, page_size=self.db_batch_size)
        self.conn.commit()
        return len(batch_data)
    
    def process_api3_emd_od(self, start_date: str, end_date: str) -> int:
        """API 3: 행정동별 OD 통행량 처리"""
        api_config = self.api_config['apis']['API3']
        job_name = api_config['name']
        
        try:
            # DB 연결 확인
            if not self.conn or self.conn.closed:
                self.connect_db()
                
            self.log_etl_status(job_name, 'RUNNING', data_date=start_date)
            self.log_etl_message(job_name, 'INFO', f'Starting API3 processing: {start_date} to {end_date}', 'API_CALL')
            
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_inserted = 0
            
            while current_date <= end_dt:
                date_str = current_date.strftime('%Y%m%d')
                params = {
                    'stdrDe': date_str, 
                    'emdCd': '1111051',  # 청운효자동 (테스트용 기본값)
                    'startRow': 1, 
                    'rowCnt': self.api_batch_size
                }
                
                page_num = 1
                daily_inserted = 0
                
                while True:
                    params['startRow'] = (page_num - 1) * self.api_batch_size + 1
                    response_data = self.make_api_request(api_config['key'], api_config['endpoint'], params, 'API3')
                    
                    if not response_data:
                        break
                    
                    try:
                        if isinstance(response_data, list):
                            items = response_data
                        else:
                            items = response_data.get('TaimsTpssEmdOdTc', {}).get('row', [])
                        
                        if not items or len(items) == 0:
                            logger.info(f"No more data available for {date_str} at page {page_num}, moving to next date")
                            break
                            
                        batch_data = self.convert_api3_to_table(items, date_str)
                        if batch_data:
                            inserted_count = self.insert_od_traffic_batch(batch_data)
                            daily_inserted += inserted_count
                            
                        page_num += 1
                        if page_num > 100:
                            break
                            
                    except Exception as e:
                        self.log_etl_message(job_name, 'ERROR', f'Data processing error for {date_str}: {e}', 'DATA_TRANSFORM')
                        break
                
                total_inserted += daily_inserted
                self.log_etl_message(job_name, 'INFO', f'Processed {date_str}: {daily_inserted} records', 'DB_INSERT')
                current_date += timedelta(days=1)
            
            self.log_etl_status(job_name, 'SUCCESS', records_processed=total_inserted, records_inserted=total_inserted)
            return total_inserted
            
        except Exception as e:
            error_msg = f"API3 processing failed: {str(e)}\n{traceback.format_exc()}"
            self.log_etl_status(job_name, 'FAILED', error_message=error_msg)
            self.log_etl_message(job_name, 'ERROR', error_msg, 'GENERAL')
            raise
    
    def convert_api3_to_table(self, items: List[Dict], date_str: str) -> List[Tuple]:
        """API3 데이터 변환 (필드명 수정: 실제 API 응답 구조에 맞춤)"""
        batch_data = []
        
        for item in items:
            start_district = item.get('startSggNm', '')  # 수정: startSgg → startSggNm
            start_admin_dong = item.get('startEmdNm', '')
            end_district = item.get('endSggNm', '')      # 수정: endSgg → endSggNm
            end_admin_dong = item.get('endEmdNm', '')
            total_passenger_count = int(item.get('totPsngNum', 0) or 0)  # 수정: totTc → totPsngNum
            
            batch_data.append((
                date_str, start_district, start_admin_dong, 
                end_district, end_admin_dong, total_passenger_count
            ))
        
        return batch_data
    
    def insert_od_traffic_batch(self, batch_data: List[Tuple]) -> int:
        """OD 통행량 데이터 배치 삽입"""
        if not batch_data:
            return 0
            
        sql = """
            INSERT INTO od_traffic_history (
                record_date, start_district, start_admin_dong,
                end_district, end_admin_dong, total_passenger_count
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_date, start_district, start_admin_dong, end_district, end_admin_dong)
            DO UPDATE SET
                total_passenger_count = EXCLUDED.total_passenger_count
        """
        
        execute_batch(self.cur, sql, batch_data, page_size=self.db_batch_size)
        self.conn.commit()
        return len(batch_data)
    
    def process_api4_section_speed(self, start_date: str, end_date: str) -> int:
        """API 4: 구간별 운행시간 처리 (Tall Table 변환)"""
        api_config = self.api_config['apis']['API4']
        job_name = api_config['name']
        
        try:
            # DB 연결 확인
            if not self.conn or self.conn.closed:
                self.connect_db()
                
            self.log_etl_status(job_name, 'RUNNING', data_date=start_date)
            self.log_etl_message(job_name, 'INFO', f'Starting API4 processing: {start_date} to {end_date}', 'API_CALL')
            
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_inserted = 0
            
            while current_date <= end_dt:
                date_str = current_date.strftime('%Y%m%d')
                params = {'stdrDe': date_str, 'startRow': 1, 'rowCnt': self.api_batch_size}
                
                page_num = 1
                daily_inserted = 0
                
                while True:
                    params['startRow'] = (page_num - 1) * self.api_batch_size + 1
                    response_data = self.make_api_request(api_config['key'], api_config['endpoint'], params, 'API4')
                    
                    if not response_data:
                        break
                    
                    try:
                        if isinstance(response_data, list):
                            items = response_data
                        else:
                            items = response_data.get('TaimsTpssRouteSectionSpeedH', {}).get('row', [])
                        
                        if not items or len(items) == 0:
                            logger.info(f"No more data available for {date_str} at page {page_num}, moving to next date")
                            break
                            
                        # 스트리밍 방식으로 청크별 변환 및 즉시 삽입
                        inserted_count = self.process_api4_chunk_streaming(items, date_str)
                        daily_inserted += inserted_count
                            
                        page_num += 1
                        if page_num > 100:
                            break
                            
                    except Exception as e:
                        self.log_etl_message(job_name, 'ERROR', f'Data processing error for {date_str}: {e}', 'DATA_TRANSFORM')
                        break
                
                total_inserted += daily_inserted
                self.log_etl_message(job_name, 'INFO', f'Processed {date_str}: {daily_inserted} records', 'DB_INSERT')
                current_date += timedelta(days=1)
            
            self.log_etl_status(job_name, 'SUCCESS', records_processed=total_inserted, records_inserted=total_inserted)
            return total_inserted
            
        except Exception as e:
            error_msg = f"API4 processing failed: {str(e)}\n{traceback.format_exc()}"
            self.log_etl_status(job_name, 'FAILED', error_message=error_msg)
            self.log_etl_message(job_name, 'ERROR', error_msg, 'GENERAL')
            raise
    
    def convert_api4_to_tall_table(self, items: List[Dict], date_str: str) -> List[Tuple]:
        """API4 데이터를 Tall Table 형태로 변환"""
        batch_data = []
        
        for item in items:
            route_id = item.get('routeId', '')
            from_node_id = item.get('fromStaId', '')
            to_node_id = item.get('toStaId', '')
            from_station_sequence = int(item.get('fromStaSn', 0) or 0)
            to_station_sequence = int(item.get('toStaSn', 0) or 0)
            usage_count = int(item.get('useCnt', 0) or 0)
            
            # 24시간 데이터를 Tall Table로 변환
            for hour in range(24):
                hour_str = f"{hour:02d}"
                
                # speed = float(item.get(f'speed{hour_str}h', 0) or 0)  # API 응답에서 모든 값이 0이므로 완전 제거
                trip_time = int(item.get(f'tripTime{hour_str}h', 0) or 0)
                
                batch_data.append((
                    date_str, route_id, from_node_id, to_node_id, hour,
                    from_station_sequence, to_station_sequence, usage_count,
                    trip_time
                ))
        
        return batch_data
    
    def insert_section_speed_batch(self, batch_data: List[Tuple]) -> int:
        """구간별 운행시간 데이터 배치 삽입"""
        if not batch_data:
            return 0
            
        sql = """
            INSERT INTO section_speed_history (
                record_date, route_id, from_node_id, to_node_id, hour,
                from_station_sequence, to_station_sequence, trip_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_date, route_id, from_node_id, to_node_id, hour)
            DO UPDATE SET
                from_station_sequence = EXCLUDED.from_station_sequence,
                to_station_sequence = EXCLUDED.to_station_sequence,
                trip_time = EXCLUDED.trip_time
        """
        
        execute_batch(self.cur, sql, batch_data, page_size=self.db_batch_size)
        self.conn.commit()
        return len(batch_data)
    
    def run_full_etl(self, start_date: str = '20250716', end_date: str = '20250731'):
        """전체 ETL 프로세스 실행 (날짜별 루프 방식)"""
        logger.info(f"=== Starting Seoul Traffic ETL Process (Daily Loop Mode) ===")
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"📅 Processing Pattern: Each date will process API1→API2→API3→API4 sequentially")
        self._monitor_memory("ETL process start")
        
        try:
            self.connect_db()
            
            # Seoul Route Filtering - DB에서 서울시 노선 정보 로드
            self.load_seoul_routes()
            
            # 날짜 범위 계산
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_days = (end_dt - current_date).days + 1
            
            # 누적 통계
            total_api1_count = 0
            total_api2_count = 0
            total_api3_count = 0
            total_api4_count = 0
            day_counter = 0
            
            logger.info(f"🗓️ Total days to process: {total_days}")
            logger.info("="*80)
            
            # 날짜별 루프 (각 날짜마다 API1-4 순차 처리)
            while current_date <= end_dt:
                day_counter += 1
                date_str = current_date.strftime('%Y%m%d')
                date_display = current_date.strftime('%Y-%m-%d (%a)')
                
                logger.info(f"📅 Day {day_counter}/{total_days}: Processing {date_display}")
                logger.info("-" * 60)
                
                daily_start_time = datetime.now()
                
                try:
                    # API1: 정류장별 승하차 데이터 (단일 날짜)
                    logger.info(f"  📊 API1: Station Passenger Data for {date_str}")
                    self._monitor_memory(f"Day{day_counter} API1 start")
                    api1_count = self.process_api1_station_passenger(date_str, date_str)
                    total_api1_count += api1_count
                    logger.info(f"  ✅ API1 completed: {api1_count:,} records")
                    
                    # API2: 구간별 승객수 데이터 (단일 날짜)
                    logger.info(f"  📊 API2: Section Passenger Data for {date_str}")
                    self._monitor_memory(f"Day{day_counter} API2 start")
                    api2_count = self.process_api2_section_passenger(date_str, date_str)
                    total_api2_count += api2_count
                    logger.info(f"  ✅ API2 completed: {api2_count:,} records")
                    
                    # API3: 행정동별 OD 통행량 데이터 (단일 날짜)
                    logger.info(f"  📊 API3: EMD OD Traffic Data for {date_str}")
                    self._monitor_memory(f"Day{day_counter} API3 start")
                    api3_count = self.process_api3_emd_od(date_str, date_str)
                    total_api3_count += api3_count
                    logger.info(f"  ✅ API3 completed: {api3_count:,} records")
                    
                    # API4: 구간별 운행시간 데이터 (단일 날짜)
                    logger.info(f"  📊 API4: Section Speed Data for {date_str}")
                    self._monitor_memory(f"Day{day_counter} API4 start")
                    api4_count = self.process_api4_section_speed(date_str, date_str)
                    total_api4_count += api4_count
                    logger.info(f"  ✅ API4 completed: {api4_count:,} records")
                    
                    # 일별 요약
                    daily_total = api1_count + api2_count + api3_count + api4_count
                    daily_duration = datetime.now() - daily_start_time
                    logger.info(f"🎯 Day {day_counter} Summary: {daily_total:,} records in {daily_duration}")
                    logger.info(f"   API1: {api1_count:,} | API2: {api2_count:,} | API3: {api3_count:,} | API4: {api4_count:,}")
                    
                except Exception as e:
                    logger.error(f"❌ Day {day_counter} ({date_str}) failed: {e}")
                    # 개별 날짜 실패 시에도 다음 날짜 계속 진행
                    continue
                
                logger.info("=" * 60)
                current_date += timedelta(days=1)
            
            # 전체 요약
            total_records = total_api1_count + total_api2_count + total_api3_count + total_api4_count
            total_api_calls = sum(self.api_call_counts.values())
            
            logger.info("="*80)
            logger.info("🎉 Daily Loop ETL Process Completed Successfully!")
            logger.info(f"📈 Total Records Processed: {total_records:,}")
            logger.info(f"   - API1 (Station Passenger): {total_api1_count:,}")
            logger.info(f"   - API2 (Section Passenger): {total_api2_count:,}")
            logger.info(f"   - API3 (EMD OD Traffic): {total_api3_count:,}")
            logger.info(f"   - API4 (Section Speed): {total_api4_count:,}")
            logger.info(f"📞 Total API Calls Made: {total_api_calls:,} (Rate Limit: 1000/day)")
            logger.info(f"   - API1 Calls: {self.api_call_counts['API1']:,}")
            logger.info(f"   - API2 Calls: {self.api_call_counts['API2']:,}")
            logger.info(f"   - API3 Calls: {self.api_call_counts['API3']:,}")
            logger.info(f"   - API4 Calls: {self.api_call_counts['API4']:,}")
            logger.info(f"📅 Date Range Processed: {start_date} to {end_date} ({total_days} days)")
            
            # Seoul Route Filtering 통계 출력
            logger.info("="*80)
            logger.info("🚌 Seoul Route Filtering Statistics:")
            logger.info(f"   - Seoul Routes Loaded: {len(self.seoul_route_ids):,} routes")
            for api_name, stats in self.filter_stats.items():
                if stats['total_fetched'] > 0:
                    filter_rate = (stats['seoul_filtered'] / stats['total_fetched']) * 100
                    logger.info(f"   - {api_name}: {stats['seoul_filtered']:,}/{stats['total_fetched']:,} records ({filter_rate:.1f}% Seoul routes)")
            
            # API 호출 통계를 DB에도 기록
            self.log_etl_message('ETL_SUMMARY', 'INFO', f'Daily loop ETL: {total_api_calls} API calls for {start_date}-{end_date}', 'API_STATISTICS', 
                               {'api_call_counts': self.api_call_counts, 'total_records': total_records, 'total_days': total_days, 'date_range': f'{start_date}-{end_date}'})
            logger.info("="*80)
            self._monitor_memory("ETL process completed")
            
        except Exception as e:
            logger.error(f"❌ Daily Loop ETL process failed: {e}")
            self._monitor_memory("ETL process failed")
            raise
        finally:
            self.close_db()

def main():
    """메인 실행 함수"""
    # DB 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 전체 ETL 프로세스 실행 (API1, API2, API3, API4 모두 활성화)
    etl = SeoulTrafficETL(db_config)
    
    logger.info("🚀 Starting Complete Seoul Traffic ETL Process")
    logger.info("📊 APIs to process: API1, API2, API3, API4")
    logger.info("📅 All APIs will process the full date range continuously")
    
    # 전체 ETL 실행 (기본 날짜 범위: 2025-07-16 ~ 2025-07-31)
    etl.run_full_etl()

if __name__ == "__main__":
    main()