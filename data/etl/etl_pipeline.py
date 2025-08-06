# etl/etl_pipeline.py

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime, timedelta
import os
import logging
from pathlib import Path
import numpy as np

# 공휴일 정의 (2024-11-01 ~ 2025-12-31)
HOLIDAYS_2024_2025 = [
    # 2024년
    '2024-12-25',  # 크리스마스
    # 2025년  
    '2025-01-01', '2025-01-27', '2025-01-28',
    '2025-01-29', '2025-01-30', '2025-03-03',
    '2025-05-05', '2025-05-06', '2025-06-03',
    '2025-06-06', '2025-08-15', '2025-10-03',
    '2025-10-06', '2025-10-07', '2025-10-08',
    '2025-10-09', '2025-12-25',
]

# 빠른 조회를 위한 set 변환
HOLIDAY_DATES = set(pd.to_datetime(HOLIDAYS_2024_2025).date)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GapyeongBusETL:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        self.unmapped_stop_numbers = set()
        self.stop_id_map = {} # stop_id_map을 저장할 인스턴스

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
    
    def process_route_info(self, file_path):
        """노선 정보 처리 (route_info.csv)"""
        logger.info(f"Processing route info from {file_path}")
        
        try:
            # CSV 읽기
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 컬럼 매핑
            column_mapping = {
                'routeid': 'route_id',
                'routeno': 'route_number',
                'routetp': 'route_type',
                'startnodenm': 'start_point',
                'endnodenm': 'end_point',
                'startvehicletime': 'first_bus_time',
                'endvehicletime': 'last_bus_time',
                'intervaltime': 'weekday_interval',
                'intervalsattime': 'saturday_interval',
                'intervalsuntime': 'sunday_interval'
            }
            
            # 컬럼명 변경
            df = df.rename(columns=column_mapping)
            
            # 중복 제거
            df = df.drop_duplicates(subset=['route_id'])
            
            # NULL 값 처리
            df = df.fillna({
                'route_type': '',
                'start_point': '',
                'end_point': '',
                'first_bus_time': '',
                'last_bus_time': '',
                'weekday_interval': 0,
                'saturday_interval': 0,
                'sunday_interval': 0
            })
            
            # 시간 형식 변환 (HH:MM 형식인 경우)
            time_columns = ['first_bus_time', 'last_bus_time']
            for col in time_columns:
                df[col] = df[col].apply(self._parse_time)
            
            # 배차간격 정수 변환
            interval_columns = ['weekday_interval', 'saturday_interval', 'sunday_interval']
            for col in interval_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(int)
            
            # 데이터베이스에 삽입
            insert_query = """
                INSERT INTO bus_routes (
                    route_id, route_number, route_type, 
                    start_point, end_point, 
                    first_bus_time, last_bus_time,
                    weekday_interval, saturday_interval, sunday_interval
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_id) DO UPDATE SET
                    route_number = EXCLUDED.route_number,
                    route_type = EXCLUDED.route_type,
                    start_point = EXCLUDED.start_point,
                    end_point = EXCLUDED.end_point,
                    first_bus_time = EXCLUDED.first_bus_time,
                    last_bus_time = EXCLUDED.last_bus_time,
                    weekday_interval = EXCLUDED.weekday_interval,
                    saturday_interval = EXCLUDED.saturday_interval,
                    sunday_interval = EXCLUDED.sunday_interval,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            # 레코드 준비
            records = []
            for _, row in df.iterrows():
                records.append((
                    row['route_id'],
                    row['route_number'],
                    row['route_type'],
                    row['start_point'],
                    row['end_point'],
                    row['first_bus_time'],
                    row['last_bus_time'],
                    row['weekday_interval'],
                    row['saturday_interval'],
                    row['sunday_interval']
                ))
            
            execute_batch(self.cur, insert_query, records)
            self.conn.commit()
            
            logger.info(f"Inserted/Updated {len(records)} route records")
            
        except Exception as e:
            logger.error(f"Error processing route info: {e}")
            self.conn.rollback()
            raise
    
    def process_route_stops(self, file_path):
        """노선별 경유 정류소 처리 (route_stops.csv)"""
        logger.info(f"Processing route_stops from {file_path}")
        
        try:
            # CSV 읽기
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 컬럼 매핑
            column_mapping = {
                'routeid': 'route_id',
                'nodeid': 'stop_id',
                'nodeno': 'stop_number',
                'nodeord': 'stop_sequence',
                'nodenm': 'stop_name',
                'gpslati': 'latitude',
                'gpslong': 'longitude'
            }
            
            df = df.rename(columns=column_mapping)
            
            # 데이터 타입 변환 (stop_number를 정수형 문자열로 통일)
            df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            df['stop_sequence'] = pd.to_numeric(df['stop_sequence'], errors='coerce').astype(int)
            df['stop_number'] = pd.to_numeric(df['stop_number'], errors='coerce').dropna().astype(int).astype(str)
            
            # 정류장 정보 추출 (중복 제거)
            stops_df = df[['stop_id', 'stop_number', 'stop_name', 
                          'latitude', 'longitude']].drop_duplicates(subset=['stop_id'])
            
            # NULL 좌표 제거
            stops_df = stops_df.dropna(subset=['latitude', 'longitude'])
            
            # 정류장 정보 삽입
            insert_stops_query = """
                INSERT INTO bus_stops (
                    stop_id, stop_number, stop_name, 
                    latitude, longitude, location, district, is_active
                ) VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), '가평군', true)
                ON CONFLICT (stop_id) DO UPDATE SET
                    stop_name = EXCLUDED.stop_name,
                    stop_number = EXCLUDED.stop_number,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    location = EXCLUDED.location,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            stops_records = []
            for _, row in stops_df.iterrows():
                location = f"POINT({row['longitude']} {row['latitude']})"
                stops_records.append((
                    row['stop_id'],
                    str(row['stop_number']),
                    row['stop_name'],
                    row['latitude'],
                    row['longitude'],
                    location
                ))
            
            execute_batch(self.cur, insert_stops_query, stops_records)
            logger.info(f"Inserted/Updated {len(stops_records)} stop records")
            
            # 노선-정류장 매핑 정보 삽입
            route_stops_df = df[['route_id', 'stop_id', 'stop_sequence']].dropna()
            
            insert_route_stops_query = """
                INSERT INTO route_stops (route_id, stop_id, stop_sequence)
                VALUES (%s, %s, %s)
                ON CONFLICT (route_id, stop_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    created_at = CURRENT_TIMESTAMP
            """
            
            route_stops_records = route_stops_df.to_records(index=False).tolist()
            execute_batch(self.cur, insert_route_stops_query, route_stops_records)
            
            self.conn.commit()
            logger.info(f"Inserted/Updated {len(route_stops_records)} route-stop mappings")
            
        except Exception as e:
            logger.error(f"Error processing route stops: {e}")
            self.conn.rollback()
            raise
    
    def _get_stop_id_map(self):
        """DB에서 (정류장번호 -> stop_id) 맵을 미리 조회"""
        self.cur.execute("SELECT stop_number, stop_id FROM bus_stops WHERE stop_number IS NOT NULL")
        stop_map = {row[0]: row[1] for row in self.cur.fetchall()}
        logger.info(f"Loaded {len(stop_map)} stop ID mappings from database.")
        return stop_map

    def _get_route_service_hours(self):
        """DB에서 (stop_id -> 04시 기준 운행시간) 맵을 조회"""
        query = """
            SELECT rs.stop_id, 
                   MIN(br.first_bus_time) as earliest_start,
                   MAX(br.last_bus_time) as latest_end
            FROM route_stops rs
            JOIN bus_routes br ON rs.route_id = br.route_id
            WHERE br.first_bus_time IS NOT NULL AND br.last_bus_time IS NOT NULL
            GROUP BY rs.stop_id
        """
        self.cur.execute(query)
        service_hours = {}
        for row in self.cur.fetchall():
            stop_id, earliest_start, latest_end = row
            service_hours[stop_id] = {
                'first_bus_time': earliest_start,
                'last_bus_time': latest_end
            }
        logger.info(f"Loaded service hours for {len(service_hours)} stops from database.")
        return service_hours

    def _check_service_hours(self, stop_id, recorded_at, service_hours_map):
        """04시 기준 운행일에서 운행시간 내인지 체크 (시간 단위)"""
        if stop_id not in service_hours_map:
            # 운행시간 정보가 없으면 기본적으로 True (기존 동작 유지)
            return True
        
        service_info = service_hours_map[stop_id]
        first_time = service_info['first_bus_time']
        last_time = service_info['last_bus_time']
        
        # 04시 기준 운행시간으로 변환 (00-03시는 24-27시로 처리)
        current_hour = recorded_at.hour
        if current_hour < 4:
            current_hour += 24  # 00:xx → 24, 01:xx → 25, 02:xx → 26, 03:xx → 27
        
        # 첫차/막차 시간도 04시 기준으로 변환
        first_hour = first_time.hour
        if first_hour < 4:
            first_hour += 24
        # 첫차 시간 반내림 (04:40 → 04시, 05:30 → 05시)
        # 분 단위는 무시하고 시간 단위만 사용
        
        last_hour = last_time.hour  
        if last_hour < 4:
            last_hour += 24
        elif last_time.minute > 0:
            last_hour += 1  # 막차 시간 반올림 (17:15 → 18시, 23:30 → 24시)
        
        # 단순 비교 (자정 넘나듦 문제 해결됨)
        return first_hour <= current_hour <= last_hour

    def process_usage_data(self, file_path):
        """정류장 이용량 데이터 처리 (개선된 버전)"""
        logger.info(f"Processing usage data from {file_path} with new logic")
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            logger.info(f"Original records: {len(df)}")

            # 1. 정류장번호가 없는 경우 수집에서 제외 (Rule 3)
            df.dropna(subset=['정류장번호'], inplace=True)
            df = df[df['정류장번호'] != '~']
            logger.info(f"After dropping rows with no stop number: {len(df)}")

            # 2. 정류장명에 _1, _2 같은 넘버링 제거 (Rule 2)
            # (정류장명이 더 이상 매핑에 직접 사용되지 않지만, 정제 로직은 유지)
            df['정류장명'] = df['정류장명'].str.replace(r'_\d+$', '', regex=True)

            # 3. 정류장번호 + 일자 기준 중복 제거 (Rule 1)
            df.drop_duplicates(subset=['정류장번호', '일자'], keep='first', inplace=True)
            logger.info(f"After deduplication: {len(df)}")

            # 4. Wide to Long: 데이터를 세로로 길게 변환
            id_vars = ['정류장번호', '일자']
            value_vars = [f"{h:02d}시_승차" for h in range(24)] + [f"{h:02d}시_하차" for h in range(24)]
            df_long = df.melt(id_vars=id_vars, value_vars=value_vars, var_name='type', value_name='count')

            # 5. 시간 정보 추출 및 데이터 타입 변환
            df_long['hour'] = df_long['type'].str.extract(r'(\d{2})시').astype(int)
            df_long['action'] = df_long['type'].str.contains('승차').map({True: 'boarding', False: 'alighting'})
            df_long.drop(columns='type', inplace=True)
            
            # 6. 승차/하차 데이터를 다시 가로로 합치기
            df_final = df_long.pivot_table(
                index=['정류장번호', '일자', 'hour'], 
                columns='action', 
                values='count',
                dropna=False
            ).reset_index()
            df_final.rename(columns={'boarding': 'boarding_count', 'alighting': 'alighting_count'}, inplace=True)

            # 7. is_operational 및 최종 값 계산
            # is_operational을 먼저 계산 (NaN 값을 기준으로)
            df_final['is_operational'] = ~(df_final['boarding_count'].isna() & df_final['alighting_count'].isna())
            
            # 그 다음, 모든 NaN 값을 0으로 채우고 정수형으로 변환
            # 이렇게 하면 is_operational=False인 행도 boarding_count=0, alighting_count=0이 됨
            df_final['boarding_count'] = df_final['boarding_count'].fillna(0).astype(int)
            df_final['alighting_count'] = df_final['alighting_count'].fillna(0).astype(int)

            # 8. DB의 stop_id와 매핑
            #stop_id_map = self._get_stop_id_map()
            #df_final['stop_id'] = df_final['정류장번호'].astype(str).map(self.stop_id_map)
            #df_final['stop_id'] = df_final['정류장번호'].astype(float).astype(int).astype(str).map(self.stop_id_map)

            # 매핑에 실패한 데이터 확인 및 기록
            #failed_mask = df_final['stop_id'].isna()
            #skipped_count = failed_mask.sum()


            # 8. DB의 stop_id와 매핑
            # 정류장번호를 float -> int -> str 순으로 변환하여 '.0'을 제거하고 DB 타입과 일치시킴
            #df_final['정류장번호_str'] = pd.to_numeric(df_final['정류장번호'], errors='coerce').dropna().astype(int).astype(str)
            #df_final['stop_id'] = df_final['정류장번호_str'].map(self.stop_id_map)


            # 8. DB의 stop_id와 매핑
            # 정류장번호를 숫자로 먼저 변환 (변환 불가 시 NaT로 처리)
            numeric_stop_numbers = pd.to_numeric(df_final['정류장번호'], errors='coerce')
            
            # NaT가 아닌 유효한 숫자만 정수형 문자열로 변환합니다.
            # .astype('Int64')는 NaN을 처리할 수 있는 특수 정수 타입입니다.
            # 이 방법을 통해 NaN을 유지하면서 정수 변환이 가능합니다.
            df_final['정류장번호_str'] = numeric_stop_numbers.astype('Int64').astype(str).replace('<NA>', np.nan)
            
            # 변환된 문자열 키로 매핑을 수행합니다.
            df_final['stop_id'] = df_final['정류장번호_str'].map(self.stop_id_map)

            # 매핑에 실패한 데이터 확인 및 기록
            failed_mask = df_final['stop_id'].isna()
            skipped_count = failed_mask.sum()


            if skipped_count > 0:
                # 매핑 실패 경고 로그 (기존과 동일)
                logger.warning(f"{skipped_count} records from this file could not be mapped and will be skipped.")
                
                # 실패한 정류장 번호(고유값)를 클래스 변수에 저장
                failed_numbers = df_final[failed_mask]['정류장번호'].unique()
                self.unmapped_stop_numbers.update(failed_numbers)
                
                # 실패한 데이터프레임에서 제외 (기존과 동일)
                df_final.dropna(subset=['stop_id'], inplace=True)

            # 9. 최종 데이터(04시 기준 운행일 로직 적용)
            df_final['recorded_at'] = pd.to_datetime(df_final['일자']) + pd.to_timedelta(df_final['hour'], unit='h')
            
            # 04시 기준 운행일 계산 (00-03시는 전날 운행일로 처리)
            df_final['operational_date'] = df_final['recorded_at'].apply(
                lambda x: x.date() - timedelta(days=1) if x.hour < 4 else x.date()
            )
            
            # 운행일 기준으로 weekend/holiday 계산 (더 정확한 플래그)
            df_final['is_weekend'] = df_final['operational_date'].apply(
                lambda x: pd.Timestamp(x).weekday() >= 5  # 5=토요일, 6=일요일
            )
            df_final['is_holiday'] = df_final['operational_date'].apply(lambda x: x in HOLIDAY_DATES)
            
            # 운행시간 체크 추가 (운행하는 날에만 체크)
            df_final['is_in_service_hours'] = df_final.apply(
                lambda row: self._check_service_hours(
                    row['stop_id'], 
                    row['recorded_at'], 
                    self.service_hours_map
                ) if row['is_operational'] else False, axis=1
            )
            
            # Convert recorded_at to string format for PostgreSQL timestamp compatibility
            df_final['recorded_at'] = df_final['recorded_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 10. 운행시간 외 승차인원 예외 케이스 로깅
            anomaly_cases = df_final[
                (df_final['is_operational'] == True) & 
                (df_final['is_in_service_hours'] == False) & 
                (df_final['boarding_count'] > 0)
            ]
            
            if len(anomaly_cases) > 0:
                logger.warning(f"Found {len(anomaly_cases)} cases with boarding_count > 0 outside service hours")
                for _, row in anomaly_cases.head(10).iterrows():  # 상위 10개만 로깅
                    logger.warning(f"  Stop: {row['stop_id']}, Time: {row['recorded_at']}, Boarding: {row['boarding_count']}")
                
                # 통계 로깅
                total_boarding_outside = anomaly_cases['boarding_count'].sum()
                max_boarding_outside = anomaly_cases['boarding_count'].max()
                logger.warning(f"  Total boarding outside service hours: {total_boarding_outside}")
                logger.warning(f"  Max boarding outside service hours: {max_boarding_outside}")
            else:
                logger.info("No boarding cases found outside service hours - data is consistent")

            # 11. DB에 삽입할 레코드 준비
            records_to_insert = df_final[[
                'stop_id', 'recorded_at', 'boarding_count', 'alighting_count', 'is_operational', 'is_holiday', 'is_weekend', 'is_in_service_hours'
            ]].to_records(index=False).tolist()

            # 배치 삽입
            if records_to_insert:
                insert_query = """
                    INSERT INTO stop_usage (
                        stop_id, recorded_at, boarding_count, alighting_count, 
                        is_operational, is_holiday, is_weekend, is_in_service_hours
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stop_id, recorded_at) DO UPDATE SET
                        boarding_count = EXCLUDED.boarding_count,
                        alighting_count = EXCLUDED.alighting_count,
                        is_operational = EXCLUDED.is_operational,
                        is_holiday = EXCLUDED.is_holiday,
                        is_weekend = EXCLUDED.is_weekend,
                        is_in_service_hours = EXCLUDED.is_in_service_hours
                """
                execute_batch(self.cur, insert_query, records_to_insert, page_size=1000)
                self.conn.commit()
                logger.info(f"Inserted {len(records_to_insert)} usage records from {file_path}")

        except Exception as e:
            logger.error(f"Error processing usage data from {file_path}: {e}")
            self.conn.rollback()
            raise

    def _parse_time(self, time_str):
        """시간 문자열을 TIME 형식으로 변환"""
        if pd.isna(time_str) or time_str == '':
            return None
        
        try:
            # 숫자를 4자리 문자열로 변환 (앞에 0 패딩)
            time_str = str(time_str).zfill(4)
            
            # HHMM 형식
            if len(time_str) == 4 and time_str.isdigit():
                return f"{time_str[:2]}:{time_str[2:]}"
            # HH:MM 형식은 그대로
            elif ':' in time_str:
                return time_str
            else:
                return None
        except:
            return None

    def verify_data(self):
        """데이터 검증 및 통계 출력"""
        logger.info("Verifying loaded data...")
        
        queries = [
            ("Total routes", "SELECT COUNT(*) FROM bus_routes"),
            ("Total stops", "SELECT COUNT(*) FROM bus_stops"),
            ("Total route-stop mappings", "SELECT COUNT(*) FROM route_stops"),
            ("Total usage records", "SELECT COUNT(*) FROM stop_usage"),
            ("Date range", """
                SELECT MIN(recorded_at)::date, MAX(recorded_at)::date 
                FROM stop_usage
            """),
            ("Operational but zero usage records", """
                SELECT COUNT(*) FROM stop_usage 
                WHERE is_operational = true AND boarding_count = 0 AND alighting_count = 0
            """),
            ("Non-operational records", """
                SELECT COUNT(*) FROM stop_usage 
                WHERE is_operational = false
            """),
            ("Top 5 busiest stops", """
                SELECT s.stop_name, SUM(su.boarding_count) as total_boarding
                FROM stop_usage su
                JOIN bus_stops s ON su.stop_id = s.stop_id
                WHERE su.is_operational = true
                GROUP BY s.stop_name
                ORDER BY total_boarding DESC
                LIMIT 5
            """)
        ]
                
        for title, query in queries:
            self.cur.execute(query)
            result = self.cur.fetchall()
            logger.info(f"{title}: {result}")


    def log_unmapped_summary(self):
        """
        ETL 프로세스 전체에서 매핑에 실패한 모든 고유 정류장 번호를 요약하여 로깅합니다.
        """
        logger.info("--- Unmapped Stop Number Summary ---")
        if self.unmapped_stop_numbers:
            # 보기 좋게 정렬하여 출력
            sorted_failed_numbers = sorted(list(self.unmapped_stop_numbers))
            
            logger.warning(f"Total {len(sorted_failed_numbers)} unique stop numbers could not be mapped across all files.")
            logger.warning(f"Unmapped Stop Numbers: {sorted_failed_numbers}")
        else:
            logger.info("All stop numbers were successfully mapped.")
        logger.info("------------------------------------")
    
    def run_etl(self, data_dir):
        """전체 ETL 프로세스 실행"""
        logger.info("Starting ETL process...")
        
        try:
            self.connect_db()

            # 1. 노선 정보 처리
            route_info_path = os.path.join(data_dir, 'raw/routes/route_info.csv')
            if os.path.exists(route_info_path):
                self.process_route_info(route_info_path)
            
            # 2. 노선별 경유 정류소 처리
            route_stops_path = os.path.join(data_dir, 'raw/routes/route_stops.csv')
            if os.path.exists(route_stops_path):
                self.process_route_stops(route_stops_path)
            
            # ETL 시작 시 정류장 맵과 운행시간 맵을 로드
            logger.info("Loading stop ID map after master data processing . . .")
            self.stop_id_map = self._get_stop_id_map()
            
            logger.info("Loading service hours map after master data processing . . .")
            self.service_hours_map = self._get_route_service_hours()

            # 3. 이용량 데이터 처리
            usage_dir = os.path.join(data_dir, 'raw/usages')
            if os.path.exists(usage_dir):
                import glob
                usage_files = glob.glob(os.path.join(usage_dir, '*_*.csv'))
                usage_files.sort()  # 날짜순으로 정렬
                
                for file_path in usage_files:
                    logger.info(f"Processing usage file: {os.path.basename(file_path)}")
                    self.process_usage_data(file_path)
            
            # 4. 데이터 검증
            self.verify_data()
            
            # 5. 매핑 실패 요약 로그 출력
            self.log_unmapped_summary()

            logger.info("ETL process completed successfully!")
            
        except Exception as e:
            logger.error(f"ETL process failed: {e}")
            raise
        finally:
            self.close_db()


# ETL 실행 스크립트
if __name__ == "__main__":
    import sys
    
    # 데이터베이스 설정
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 데이터 디렉토리
    data_dir = sys.argv[1] if len(sys.argv) > 1 else '/data'
    
    # ETL 실행
    etl = GapyeongBusETL(db_config)
    etl.run_etl(data_dir)