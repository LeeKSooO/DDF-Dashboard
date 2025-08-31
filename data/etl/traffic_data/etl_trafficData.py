# traffic_etl.py
# Seoul Traffic Data ETL Pipeline for Historical Traffic Analysis
# Fetches data from 5 APIs and loads into TimescaleDB with Tall Table structure

import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch, execute_values, RealDictCursor
from psycopg2 import pool
import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
import time
import traceback
import gc
from math import ceil
import threading
from contextlib import contextmanager
import concurrent.futures
from queue import Queue

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
    """서울시 교통 데이터 ETL 파이프라인 (성능 최적화 버전)"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        
        # 연결 풀 초기화
        self.connection_pool = None
        self._init_connection_pool()
        
        # 스레드 안전성을 위한 로컬 스토리지
        self.local = threading.local()
        
        # 성능 최적화된 배치 설정
        self.max_workers = 4  # 동시 처리 스레드 수
        
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
        
        # 성능 최적화된 배치 크기 설정 (16GB 메모리 기준)
        self.api_batch_size = 25000    # API 호출당 레코드 수 (2.5배 증가)
        self.db_batch_size = 20000     # DB 삽입 배치 크기 (20배 증가)
        self.chunk_size = 10000        # Tall Table 변환 청크 크기 (20배 증가)
        
        # 커밋 최적화 설정
        self.commit_batch_count = 3    # N개 배치마다 commit
        self.batch_counter = 0
        
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
    
    def _init_connection_pool(self):
        """연결 풀 초기화"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,      # 최소 연결 수
                maxconn=8,      # 최대 연결 수 (PostgreSQL max_connections 고려)
                **self.db_config
            )
            logger.info("🔗 Database connection pool initialized (2-8 connections)")
        except Exception as e:
            logger.error(f"Connection pool initialization failed: {e}")
            raise
    
    @contextmanager
    def get_db_connection(self):
        """연결 풀에서 안전한 연결 획득"""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn, conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
        
    def connect_db(self):
        """기존 메서드 호환성 유지 (레거시 지원)"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def close_db(self):
        """데이터베이스 연결 종료 (연결 풀 포함)"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")
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
                # 중복 키 검증 (디버깅용)
                keys_seen = set()
                duplicates = []
                for record in batch_data:
                    key = (record[0], record[1], record[2], record[3])  # date, route_id, node_id, hour
                    if key in keys_seen:
                        duplicates.append(key)
                    keys_seen.add(key)
                
                if duplicates:
                    logger.warning(f"🚨 Duplicate keys found in API1 batch: {len(duplicates)} duplicates")
                    logger.warning(f"Sample duplicates: {duplicates[:5]}")
                    # 중복 제거
                    unique_batch = []
                    seen_keys = set()
                    for record in batch_data:
                        key = (record[0], record[1], record[2], record[3])
                        if key not in seen_keys:
                            unique_batch.append(record)
                            seen_keys.add(key)
                    batch_data = unique_batch
                    logger.info(f"✅ Deduplicated batch: {len(batch_data)} unique records")
                
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
                # 중복 키 검증 (디버깅용)
                keys_seen = set()
                duplicates = []
                for record in batch_data:
                    key = (record[0], record[1], record[2], record[3], record[4])  # date, route_id, from_node_id, to_node_id, hour
                    if key in keys_seen:
                        duplicates.append(key)
                    keys_seen.add(key)
                
                if duplicates:
                    logger.warning(f"🚨 Duplicate keys found in API2 batch: {len(duplicates)} duplicates")
                    logger.warning(f"Sample duplicates: {duplicates[:5]}")
                    # 중복 제거
                    unique_batch = []
                    seen_keys = set()
                    for record in batch_data:
                        key = (record[0], record[1], record[2], record[3], record[4])
                        if key not in seen_keys:
                            unique_batch.append(record)
                            seen_keys.add(key)
                    batch_data = unique_batch
                    logger.info(f"✅ Deduplicated API2 batch: {len(batch_data)} unique records")
                
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
                # 중복 키 검증 (API4 PK: record_date, route_id, from_node_id, to_node_id, hour)
                keys_seen = set()
                duplicates = []
                for record in batch_data:
                    key = (record[0], record[1], record[2], record[3], record[4])  # date, route_id, from_node_id, to_node_id, hour
                    if key in keys_seen:
                        duplicates.append(key)
                    keys_seen.add(key)
                
                if duplicates:
                    logger.warning(f"🚨 Duplicate keys found in API4 batch: {len(duplicates)} duplicates")
                    logger.warning(f"Sample duplicates: {duplicates[:5]}")
                    # 중복 제거
                    unique_batch = []
                    seen_keys = set()
                    for record in batch_data:
                        key = (record[0], record[1], record[2], record[3], record[4])
                        if key not in seen_keys:
                            unique_batch.append(record)
                            seen_keys.add(key)
                    batch_data = unique_batch
                    logger.info(f"✅ Deduplicated API4 batch: {len(batch_data)} unique records")
                
                inserted_count = self.insert_section_speed_batch(batch_data)
                total_inserted += inserted_count
                
                # 메모리 정리
                del batch_data
                
        return total_inserted
    
    def insert_station_passenger_batch(self, batch_data: List[Tuple]) -> int:
        """정류장별 승하차 데이터 배치 삽입 (성능 최적화 버전)"""
        if not batch_data:
            return 0
            
        # 연결 풀 사용
        with self.get_db_connection() as (conn, cur):
            sql = """
                INSERT INTO station_passenger_history (
                    record_date, route_id, node_id, hour,
                    route_name, station_name, station_sequence,
                    dispatch_count, ride_passenger, alight_passenger
                ) VALUES %s
                ON CONFLICT (record_date, route_id, node_id, hour)
                DO UPDATE SET
                    route_name = EXCLUDED.route_name,
                    station_name = EXCLUDED.station_name,
                    station_sequence = EXCLUDED.station_sequence,
                    dispatch_count = EXCLUDED.dispatch_count,
                    ride_passenger = EXCLUDED.ride_passenger,
                    alight_passenger = EXCLUDED.alight_passenger
            """
            
            # execute_values로 고성능 배치 삽입 (execute_batch보다 5-10배 빠름)
            execute_values(cur, sql, batch_data, page_size=self.db_batch_size)
            
            # 배치 커밋 최적화: N개 배치마다 커밋
            self.batch_counter += 1
            if self.batch_counter % self.commit_batch_count == 0:
                conn.commit()
                logger.info(f"🔄 Batch commit executed ({self.batch_counter} batches processed)")
            else:
                conn.commit()  # 현재는 모든 배치에서 커밋 (안정성 우선)
                
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
        """구간별 승객수 데이터 배치 삽입 (성능 최적화 버전)"""
        if not batch_data:
            return 0
            
        # 연결 풀 사용
        with self.get_db_connection() as (conn, cur):
            sql = """
                INSERT INTO section_passenger_history (
                    record_date, route_id, from_node_id, to_node_id, hour, station_sequence,
                    passenger_count, daily_total_passengers
                ) VALUES %s
                ON CONFLICT (record_date, route_id, from_node_id, to_node_id, hour)
                DO UPDATE SET
                    station_sequence = EXCLUDED.station_sequence,
                    passenger_count = EXCLUDED.passenger_count,
                    daily_total_passengers = EXCLUDED.daily_total_passengers
            """
            
            # 고성능 배치 삽입
            execute_values(cur, sql, batch_data, page_size=self.db_batch_size)
            conn.commit()
            
            return len(batch_data)
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
        
        # 중복 키 검증 (API3 PK: record_date, start_district, start_admin_dong, end_district, end_admin_dong)
        keys_seen = set()
        duplicates = []
        for record in batch_data:
            key = (record[0], record[1], record[2], record[3], record[4])  # date, start_district, start_admin_dong, end_district, end_admin_dong
            if key in keys_seen:
                duplicates.append(key)
            keys_seen.add(key)
        
        if duplicates:
            logger.warning(f"🚨 Duplicate keys found in API3 batch: {len(duplicates)} duplicates")
            logger.warning(f"Sample duplicates: {duplicates[:5]}")
            # 중복 제거
            unique_batch = []
            seen_keys = set()
            for record in batch_data:
                key = (record[0], record[1], record[2], record[3], record[4])
                if key not in seen_keys:
                    unique_batch.append(record)
                    seen_keys.add(key)
            batch_data = unique_batch
            logger.info(f"✅ Deduplicated API3 batch: {len(batch_data)} unique records")
        
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
    
    def refresh_materialized_views(self):
        """ETL 완료 후 Materialized Views 갱신 (API 성능 최적화)"""
        try:
            logger.info("🔄 Starting materialized view refresh for API optimization...")
            
            # 1. 기본 MV 갱신
            refresh_sql = "SELECT refresh_all_traffic_views();"
            self.cur.execute(refresh_sql)
            self.conn.commit()
            
            # 2. Anomaly Pattern 전용 MV 갱신
            logger.info("🎯 Refreshing Anomaly Pattern MV (station_hourly_patterns)...")
            try:
                # MV가 존재하는지 확인
                check_sql = """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_matviews 
                        WHERE matviewname = 'mv_station_hourly_patterns'
                    );
                """
                self.cur.execute(check_sql)
                exists = self.cur.fetchone()[0]
                
                if exists:
                    # MV가 있으면 갱신 함수 호출
                    refresh_anomaly_sql = "SELECT refresh_station_hourly_patterns();"
                    self.cur.execute(refresh_anomaly_sql)
                    self.conn.commit()
                    logger.info("✅ Anomaly Pattern MV refreshed successfully!")
                else:
                    logger.warning("⚠️ mv_station_hourly_patterns not found. Please run 002_station_hourly_patterns.sql first.")
                
            except Exception as e:
                logger.warning(f"⚠️ Could not refresh Anomaly Pattern MV: {e}")
                # 실패해도 전체 ETL은 계속 진행
            
            # 갱신 후 통계 확인
            stats_sql = "SELECT * FROM check_mv_statistics();"
            self.cur.execute(stats_sql)
            stats = self.cur.fetchall()
            
            logger.info("📊 Materialized View Statistics:")
            for stat in stats:
                view_name = stat['view_name'] if isinstance(stat, dict) else stat[0]
                row_count = stat['row_count'] if isinstance(stat, dict) else stat[1]
                disk_size = stat['disk_size'] if isinstance(stat, dict) else stat[2]
                logger.info(f"   - {view_name}: {row_count:,} rows, {disk_size}")
            
            # ETL 로그에 기록
            self.log_etl_message('ETL_MATERIALIZED_VIEWS', 'INFO', 
                               f'Successfully refreshed {len(stats)} materialized views', 
                               'AGGREGATION',
                               {'refreshed_views': len(stats)})
            
        except Exception as e:
            logger.error(f"Failed to refresh materialized views: {e}")
            # 구체적인 에러 로깅
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'stage': 'materialized_view_refresh'
            }
            self.log_etl_message('ETL_MATERIALIZED_VIEWS', 'ERROR', f'Materialized view refresh failed: {e}', 'AGGREGATION', error_details)
            raise
    
    def run_full_etl(self, start_date: str = '20250719', end_date: str = '20250731'):
        """전체 ETL 프로세스 실행 (날짜별 루프 방식)"""
        logger.info(f"=== Starting Seoul Traffic ETL Process (Daily Loop Mode) ===")
        logger.info(f"Date Range: {start_date} to {end_date} (continuing from last complete date: 2025-07-18)")
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
            
            # ✅ ETL 완료 후 Materialized Views 갱신 (API 성능 최적화)
            logger.info("="*80)
            logger.info("📊 Refreshing Materialized Views for API Optimization...")
            try:
                self.refresh_materialized_views()
                logger.info("✅ All materialized views refreshed successfully!")
            except Exception as e:
                logger.error(f"❌ Failed to refresh materialized views: {e}")
                # 집계 테이블 갱신 실패해도 전체 ETL은 성공으로 처리
                self.log_etl_message('ETL_MATERIALIZED_VIEWS', 'ERROR', f'Materialized view refresh failed: {e}', 'AGGREGATION')
            
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
    
    def run_parallel_etl(self, start_date: str = '20250719', end_date: str = '20250731'):
        """병렬 처리 ETL 프로세스 실행 (성능 최적화 버전)"""
        logger.info(f"=== Starting Parallel Seoul Traffic ETL Process ===")
        logger.info(f"Date Range: {start_date} to {end_date} (continuing from last complete date: 2025-07-18)")
        logger.info(f"🚀 Processing Pattern: Parallel execution with {self.max_workers} workers")
        logger.info(f"⚡ Performance Optimizations: Connection Pool + Batch Processing + Parallel APIs")
        self._monitor_memory("Parallel ETL process start")
        
        try:
            # 기본 연결 생성 (Seoul Routes 로딩용)
            self.connect_db()
            self.load_seoul_routes()
            
            # 날짜 범위 계산
            current_date = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            total_days = (end_dt - current_date).days + 1
            
            # 날짜별 작업 큐 생성
            date_queue = Queue()
            while current_date <= end_dt:
                date_queue.put(current_date.strftime('%Y%m%d'))
                current_date += timedelta(days=1)
            
            logger.info(f"🗓️ Total days to process: {total_days}")
            logger.info(f"👥 Parallel workers: {self.max_workers}")
            logger.info("="*80)
            
            # 병렬 처리 통계
            total_api1_count = 0
            total_api2_count = 0  
            total_api3_count = 0
            total_api4_count = 0
            processed_dates = []
            
            # 병렬 처리 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                # 각 날짜별로 API들을 병렬 처리
                while not date_queue.empty():
                    date_str = date_queue.get()
                    processed_dates.append(date_str)
                    
                    logger.info(f"📅 Queuing parallel processing for {date_str}")
                    
                    # API별 병렬 실행
                    future_api1 = executor.submit(self._process_api1_parallel, date_str)
                    future_api2 = executor.submit(self._process_api2_parallel, date_str)
                    future_api3 = executor.submit(self._process_api3_parallel, date_str)
                    future_api4 = executor.submit(self._process_api4_parallel, date_str)
                    
                    futures.extend([
                        ('API1', date_str, future_api1),
                        ('API2', date_str, future_api2), 
                        ('API3', date_str, future_api3),
                        ('API4', date_str, future_api4)
                    ])
                
                logger.info(f"🔄 Processing {len(futures)} parallel tasks...")
                
                # 결과 수집
                for api_name, date_str, future in futures:
                    try:
                        result = future.result(timeout=600)  # 10분 타임아웃
                        
                        if api_name == 'API1':
                            total_api1_count += result
                        elif api_name == 'API2':
                            total_api2_count += result
                        elif api_name == 'API3':
                            total_api3_count += result
                        elif api_name == 'API4':
                            total_api4_count += result
                            
                        logger.info(f"✅ {api_name} for {date_str}: {result:,} records")
                        
                    except concurrent.futures.TimeoutError:
                        logger.error(f"⏰ {api_name} for {date_str} timed out")
                    except Exception as e:
                        logger.error(f"❌ {api_name} for {date_str} failed: {e}")
            
            # 전체 요약
            total_records = total_api1_count + total_api2_count + total_api3_count + total_api4_count
            total_api_calls = sum(self.api_call_counts.values())
            
            logger.info("="*80)
            logger.info("🎉 Parallel ETL Process Completed Successfully!")
            logger.info(f"📈 Total Records Processed: {total_records:,}")
            logger.info(f"   - API1 (Station Passenger): {total_api1_count:,}")
            logger.info(f"   - API2 (Section Passenger): {total_api2_count:,}")
            logger.info(f"   - API3 (EMD OD Traffic): {total_api3_count:,}")
            logger.info(f"   - API4 (Section Speed): {total_api4_count:,}")
            logger.info(f"📞 Total API Calls Made: {total_api_calls:,}")
            logger.info(f"📅 Date Range Processed: {start_date} to {end_date} ({total_days} days)")
            logger.info(f"⚡ Parallel Processing: {self.max_workers} workers")
            
            # ✅ ETL 완료 후 Materialized Views 갱신 (API 성능 최적화)
            logger.info("="*80)
            logger.info("📊 Refreshing Materialized Views for API Optimization...")
            try:
                self.refresh_materialized_views()
                logger.info("✅ All materialized views refreshed successfully!")
            except Exception as e:
                logger.error(f"❌ Failed to refresh materialized views: {e}")
                # 집계 테이블 갱신 실패해도 전체 ETL은 성공으로 처리
            
            logger.info("="*80)
            self._monitor_memory("Parallel ETL process completed")
            
        except Exception as e:
            logger.error(f"❌ Parallel ETL process failed: {e}")
            self._monitor_memory("Parallel ETL process failed")
            raise
        finally:
            self.close_db()
    
    def _process_api1_parallel(self, date_str: str) -> int:
        """API1 병렬 처리 (독립 연결 사용)"""
        try:
            return self.process_api1_station_passenger(date_str, date_str)
        except Exception as e:
            logger.error(f"API1 parallel processing failed for {date_str}: {e}")
            return 0
    
    def _process_api2_parallel(self, date_str: str) -> int:
        """API2 병렬 처리 (독립 연결 사용)"""
        try:
            return self.process_api2_section_passenger(date_str, date_str)
        except Exception as e:
            logger.error(f"API2 parallel processing failed for {date_str}: {e}")
            return 0
    
    def _process_api3_parallel(self, date_str: str) -> int:
        """API3 병렬 처리 (독립 연결 사용)"""
        try:
            return self.process_api3_emd_od(date_str, date_str)
        except Exception as e:
            logger.error(f"API3 parallel processing failed for {date_str}: {e}")
            return 0
    
    def _process_api4_parallel(self, date_str: str) -> int:
        """API4 병렬 처리 (독립 연결 사용)"""
        try:
            return self.process_api4_section_speed(date_str, date_str)
        except Exception as e:
            logger.error(f"API4 parallel processing failed for {date_str}: {e}")
            return 0

def main():
    """메인 실행 함수 (성능 최적화 버전)"""
    # DB 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 성능 최적화된 ETL 프로세스 실행
    etl = SeoulTrafficETL(db_config)
    
    # 실행 모드 선택 (환경 변수로 제어 가능)
    parallel_mode = os.getenv('ETL_PARALLEL_MODE', 'true').lower() == 'true'
    
    if parallel_mode:
        logger.info("🚀 Starting High-Performance Parallel Seoul Traffic ETL Process")
        logger.info("⚡ Performance Features: Connection Pool + Parallel Processing + Optimized Batching")
        logger.info("📊 APIs to process: API1, API2, API3, API4 (Parallel Execution)")
        logger.info("📅 Processing with 4 parallel workers for maximum performance")
        
        # 병렬 ETL 실행 (기본 날짜 범위: 2025-07-19 ~ 2025-07-31)
        etl.run_parallel_etl()
        etl_success = True  # ETL 완료 가정
    else:
        logger.info("🚀 Starting Standard Seoul Traffic ETL Process")
        logger.info("📊 APIs to process: API1, API2, API3, API4 (Sequential Execution)")
        logger.info("📅 All APIs will process the full date range sequentially")
        
        # 기본 ETL 실행 (순차 처리)
        etl.run_full_etl()
        etl_success = True  # ETL 완료 가정
    
    # ETL 완료 후 DRT 집계 실행 (기존 MV 갱신 방식과 동일)
    logger.info("🎯 Starting DRT Score Aggregation...")
    try:
        # DB 연결이 없으면 연결
        if not etl.conn or etl.conn.closed:
            etl.connect_db()
        
        # mv_station_hourly_patterns에서 사용 가능한 월 조회
        check_months_sql = """
            SELECT DISTINCT month_date 
            FROM mv_station_hourly_patterns 
            ORDER BY month_date DESC
        """
        etl.cur.execute(check_months_sql)
        available_months = [row[0] for row in etl.cur.fetchall()]
        
        if available_months:
            logger.info(f"📅 Found {len(available_months)} months to aggregate: {[m.strftime('%Y-%m') for m in available_months]}")
            
            # 각 월별로 DRT 집계 함수 실행
            for month_date in available_months:
                logger.info(f"🚀 Processing DRT aggregation for {month_date.strftime('%Y-%m')}...")
                
                # 3개 DRT 모델 모두 실행
                for model_name, function_name in [
                    ('Commuter', 'calculate_commuter_drt_scores'),
                    ('Tourism', 'calculate_tourism_drt_scores'), 
                    ('Vulnerable', 'calculate_vulnerable_drt_scores')
                ]:
                    try:
                        logger.info(f"  ⚡ Running {model_name} model...")
                        drt_sql = f"SELECT {function_name}(%s);"
                        etl.cur.execute(drt_sql, (month_date,))
                        result = etl.cur.fetchone()[0]
                        etl.conn.commit()
                        logger.info(f"  ✅ {model_name} completed: {result:,} records")
                    except Exception as e:
                        logger.warning(f"  ⚠️ {model_name} failed: {e}")
                        # 실패해도 다음 모델 계속 진행
                
                logger.info(f"✅ {month_date.strftime('%Y-%m')} DRT aggregation completed")
            
            logger.info("🎉 All DRT Score aggregation completed!")
        else:
            logger.warning("⚠️ No months found in mv_station_hourly_patterns, skipping DRT aggregation")
            
    except Exception as e:
        logger.warning(f"⚠️ DRT Score aggregation failed: {e}")
        # 실패해도 전체 ETL은 성공으로 처리
        logger.info("   ETL data is still available, DRT aggregation can be run manually")

if __name__ == "__main__":
    main()