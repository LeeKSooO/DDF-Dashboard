#!/usr/bin/env python3
"""
Daily OD Analysis 테이블 ETL 스크립트 (완전 재작성)
- 데이터 소스 1: data/processed/od/*.csv (OD pairs + 시간대별 승객수)
- 데이터 소스 2: PostgreSQL DB (정류장 메타데이터, 노선 정보, 배차 정보)
- 대상 기간: 2025-07-15 ~ 2025-07-31 (17일)
"""

import pandas as pd
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import sys

class DailyODAnalysisETL:
    def __init__(self):
        # 프로젝트 루트에서 상대 경로로 변경
        current_dir = Path(__file__).parent.parent.parent.parent
        self.base_csv_dir = str(current_dir / "data" / "processed" / "od")
        self.db_config = {
            'host': 'localhost',
            'port': '5432', 
            'database': 'ddf_db',
            'user': 'ddf_user'
        }
        self.bus_stops_cache = {}
        self.station_routes_cache = {}
        
    def connect_db(self):
        """PostgreSQL 연결 테스트"""
        try:
            result = subprocess.run([
                'docker', 'exec', 'ddf-postgres', 'psql', 
                '-U', 'ddf_user', '-d', 'ddf_db', 
                '-c', 'SELECT 1;'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"DB 연결 실패: {result.stderr}")
                
            print("✅ PostgreSQL 연결 성공")
            return True
            
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            return False
    
    def load_bus_stops_metadata(self):
        """정류장 메타데이터 로드 (spatial_mapping 조인)"""
        print("📍 정류장 메타데이터 로드 중...")
        
        query = """
        SELECT 
            bs.node_id,
            bs.node_name,
            bs.coordinates_x,
            bs.coordinates_y,
            sm.sgg_code as district_code,
            sm.sgg_name as district_name,
            sm.adm_name as admin_dong
        FROM bus_stops bs
        LEFT JOIN spatial_mapping sm ON bs.node_id = sm.node_id
        WHERE bs.is_active = TRUE
        ORDER BY bs.node_id;
        """
        
        result = subprocess.run([
            'docker', 'exec', 'ddf-postgres', 'psql', 
            '-U', 'ddf_user', '-d', 'ddf_db', 
            '-t', '-c', query
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"정류장 데이터 조회 실패: {result.stderr}")
        
        # 결과 파싱
        for line in result.stdout.strip().split('\n'):
            if line.strip() and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4 and parts[0] not in ['node_id', '']:
                    self.bus_stops_cache[parts[0]] = {
                        'node_name': parts[1],
                        'coordinates_x': float(parts[2]) if parts[2] and parts[2] != '' else None,
                        'coordinates_y': float(parts[3]) if parts[3] and parts[3] != '' else None,
                        'district_code': parts[4] if len(parts) > 4 and parts[4] != '' else None,
                        'district_name': parts[5] if len(parts) > 5 and parts[5] != '' else None,
                        'admin_dong': parts[6] if len(parts) > 6 and parts[6] != '' else None
                    }
        
        print(f"✅ 정류장 메타데이터 {len(self.bus_stops_cache):,}개 로드 완료")
        return len(self.bus_stops_cache) > 0
    
    def load_station_routes(self):
        """정류장별 노선 정보 로드 (route_stops + bus_routes + operation_schedules 조인)"""
        print("🚌 정류장별 노선 정보 로드 중...")
        
        query = """
        SELECT DISTINCT 
            rs.stop_id as node_id,
            br.route_id,
            br.route_name,
            br.route_type,
            br.total_distance,
            os.weekday_interval,
            os.weekday_first_time,
            os.weekday_last_time,
            os.min_interval,
            rs.node_sequence
        FROM route_stops rs
        JOIN bus_routes br ON rs.route_id = br.route_id
        LEFT JOIN operation_schedules os ON br.route_id = os.route_id
        WHERE rs.is_active = TRUE  -- is_operating 조건 제거 (OD 데이터가 있으면 운행 중)
        ORDER BY rs.stop_id, br.route_id;
        """
        
        result = subprocess.run([
            'docker', 'exec', 'ddf-postgres', 'psql', 
            '-U', 'ddf_user', '-d', 'ddf_db', 
            '-t', '-c', query
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ 노선 정보 로드 실패: {result.stderr}")
            return False
        
        # 노선 정보 파싱
        station_routes = {}
        for line in result.stdout.strip().split('\n'):
            if line.strip() and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 10 and parts[0] not in ['node_id', '']:
                    node_id = parts[0]
                    route_info = {
                        'route_id': parts[1],
                        'route_name': parts[2],
                        'route_type': parts[3],
                        'route_type_code': int(parts[3]) if parts[3].isdigit() else 0,
                        'total_distance_km': float(parts[4]) if parts[4] and parts[4] != '' else None,
                        'dispatch_interval': int(parts[5]) if parts[5] and parts[5] != '' else None,
                        'first_departure_time': parts[6] if parts[6] != '' else None,
                        'last_departure_time': parts[7] if parts[7] != '' else None,
                        'min_interval': int(parts[8]) if parts[8] and parts[8] != '' else None,
                        'stop_sequence': int(parts[9]) if parts[9] and parts[9] != '' else None
                    }
                    
                    if node_id not in station_routes:
                        station_routes[node_id] = []
                    station_routes[node_id].append(route_info)
        
        self.station_routes_cache = station_routes
        print(f"✅ {len(station_routes):,}개 정류장의 노선 정보 로드 완료")
        return len(station_routes) > 0
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """두 좌표 간 직선거리 계산 (Haversine formula)"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0
            
        # 위도, 경도를 라디안으로 변환
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine 공식
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # 지구 반지름 (km)
        
        return round(c * r, 2)
    
    def find_common_routes(self, from_routes, to_routes):
        """공통 노선 찾기"""
        from_route_ids = {r['route_id'] for r in from_routes}
        to_route_ids = {r['route_id'] for r in to_routes}
        common_ids = from_route_ids.intersection(to_route_ids)
        
        common_routes = []
        from_only_routes = []
        to_only_routes = []
        
        # 공통 노선 (from 기준으로 상세정보 포함)
        for route in from_routes:
            if route['route_id'] in common_ids:
                common_routes.append(route)
        
        # From 전용 노선
        for route in from_routes:
            if route['route_id'] not in common_ids:
                from_only_routes.append(route)
                
        # To 전용 노선  
        for route in to_routes:
            if route['route_id'] not in common_ids:
                to_only_routes.append(route)
        
        return common_routes, from_only_routes, to_only_routes
    
    def process_csv_file(self, date_str):
        """단일 CSV 파일 처리 (CNT_00H~CNT_23H 활용)"""
        file_path = f"{self.base_csv_dir}/KSCC_DX_RA_OD_{date_str}_seoul_only.csv"
        
        if not Path(file_path).exists():
            print(f"⚠️ 파일 없음: {file_path}")
            return []
        
        try:
            print(f"📂 처리 중: {date_str}")
            print(f"  📄 파일 로드: {file_path}")
            df = pd.read_csv(file_path)
            print(f"  📊 파일 크기: {len(df):,}개 레코드")
            
            # 필요한 컬럼 확인
            required_cols = ['RIDE_PUB_STA_ID', 'ALGH_PUB_STA_ID', 'CNT'] + [f'CNT_{h:02d}H' for h in range(24)]
            if not all(col in df.columns for col in required_cols):
                missing_cols = [col for col in required_cols if col not in df.columns]
                raise Exception(f"필수 컬럼 없음: {missing_cols}")
            
            od_records = []
            processed_count = 0
            skipped_count = 0
            
            print(f"  🔄 레코드 처리 시작...")
            
            for _, row in df.iterrows():
                processed_count += 1
                
                # 진행률 표시 (1만개마다)
                if processed_count % 10000 == 0:
                    print(f"    ⏳ {processed_count:,}/{len(df):,} 처리중... ({processed_count/len(df)*100:.1f}%)")
                from_id_str = str(row['RIDE_PUB_STA_ID'])
                to_id_str = str(row['ALGH_PUB_STA_ID'])
                
                # 정류장 메타데이터 확인
                if from_id_str not in self.bus_stops_cache or to_id_str not in self.bus_stops_cache:
                    skipped_count += 1
                    continue
                
                # 시간대별 승객수 추출 (CNT_00H ~ CNT_23H)
                hourly_dist = {}
                hourly_values = {}
                for hour in range(24):
                    col_name = f'CNT_{hour:02d}H'
                    passengers = int(row[col_name]) if pd.notna(row[col_name]) else 0
                    hourly_dist[str(hour)] = passengers
                    hourly_values[f'h{hour:02d}'] = passengers
                
                total_passengers = sum(hourly_values.values())
                if total_passengers == 0:
                    continue
                
                # 메타데이터 추출
                from_meta = self.bus_stops_cache[from_id_str]
                to_meta = self.bus_stops_cache[to_id_str]
                from_routes = self.station_routes_cache.get(from_id_str, [])
                to_routes = self.station_routes_cache.get(to_id_str, [])
                
                # 노선 연결성 분석
                common_routes, from_only_routes, to_only_routes = self.find_common_routes(from_routes, to_routes)
                
                # 거리 계산
                distance = self.calculate_distance(
                    from_meta['coordinates_y'], from_meta['coordinates_x'],
                    to_meta['coordinates_y'], to_meta['coordinates_x']
                )
                
                # 레코드 생성
                record = {
                    'analysis_date': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                    'from_station_id': from_id_str,
                    'to_station_id': to_id_str,
                    'from_station_name': from_meta['node_name'],
                    'from_coordinates_x': from_meta['coordinates_x'],
                    'from_coordinates_y': from_meta['coordinates_y'],
                    'from_district_code': from_meta['district_code'],
                    'from_district_name': from_meta['district_name'],
                    'from_admin_dong': from_meta['admin_dong'],
                    'from_routes': json.dumps(from_routes, ensure_ascii=False),
                    'to_station_name': to_meta['node_name'],
                    'to_coordinates_x': to_meta['coordinates_x'],
                    'to_coordinates_y': to_meta['coordinates_y'],
                    'to_district_code': to_meta['district_code'],
                    'to_district_name': to_meta['district_name'],
                    'to_admin_dong': to_meta['admin_dong'],
                    'to_routes': json.dumps(to_routes, ensure_ascii=False),
                    'estimated_distance_km': distance,
                    'hourly_distribution': json.dumps(hourly_dist, ensure_ascii=False),
                    'common_routes': json.dumps(common_routes, ensure_ascii=False),
                    'from_only_routes': json.dumps(from_only_routes, ensure_ascii=False),
                    'to_only_routes': json.dumps(to_only_routes, ensure_ascii=False),
                    'direct_connection_count': len(common_routes),
                    'transfer_required': len(common_routes) == 0
                }
                
                # 24시간 개별 컬럼 추가
                record.update(hourly_values)
                
                od_records.append(record)
            
            print(f"  📊 처리 완료: 전체 {processed_count:,}개 중 {len(od_records):,}개 생성, {skipped_count:,}개 스킵")
            print(f"✅ {date_str}: {len(od_records):,}개 OD pairs 처리 완료")
            return od_records
            
        except Exception as e:
            print(f"❌ {date_str} 처리 실패: {e}")
            return []
    
    def insert_records_to_db(self, records, batch_size=1):
        """DB에 레코드 일괄 삽입"""
        if not records:
            return 0
            
        print(f"💾 DB 삽입 시작: {len(records):,}개 레코드")
        
        # 컬럼 순서 정의
        columns = [
            'analysis_date', 'from_station_id', 'to_station_id',
            'from_station_name', 'from_coordinates_x', 'from_coordinates_y',
            'from_district_code', 'from_district_name', 'from_admin_dong', 'from_routes',
            'to_station_name', 'to_coordinates_x', 'to_coordinates_y',
            'to_district_code', 'to_district_name', 'to_admin_dong', 'to_routes',
            'h00', 'h01', 'h02', 'h03', 'h04', 'h05', 'h06', 'h07', 'h08', 'h09', 'h10', 'h11',
            'h12', 'h13', 'h14', 'h15', 'h16', 'h17', 'h18', 'h19', 'h20', 'h21', 'h22', 'h23',
            'estimated_distance_km', 'hourly_distribution',
            'common_routes', 'from_only_routes', 'to_only_routes',
            'direct_connection_count', 'transfer_required'
        ]
        
        inserted_count = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            # SQL INSERT 생성
            insert_values = []
            for record in batch:
                value_parts = []
                for col in columns:
                    val = record.get(col, '')
                    if val is None or val == '':
                        value_parts.append('NULL')
                    elif col in ['from_routes', 'to_routes', 'hourly_distribution', 
                                'common_routes', 'from_only_routes', 'to_only_routes']:
                        # JSONB 컬럼
                        escaped_json = str(val).replace("'", "''")
                        value_parts.append(f"'{escaped_json}'::jsonb")
                    elif isinstance(val, str):
                        # 문자열
                        escaped_str = str(val).replace("'", "''")
                        value_parts.append(f"'{escaped_str}'")
                    else:
                        # 숫자, boolean
                        value_parts.append(str(val))
                
                insert_values.append(f"({','.join(value_parts)})")
            
            # SQL 실행
            insert_sql = f"""
            INSERT INTO daily_od_analysis ({','.join(columns)}) 
            VALUES {','.join(insert_values)};
            """
            
            result = subprocess.run([
                'docker', 'exec', 'ddf-postgres', 'psql',
                '-U', 'ddf_user', '-d', 'ddf_db',
                '-c', insert_sql
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                inserted_count += len(batch)
                print(f"  ✅ 배치 {i//batch_size + 1}: {len(batch)}개 삽입 완료 (총 {inserted_count:,}/{len(records):,})")
            else:
                print(f"  ❌ 배치 {i//batch_size + 1} 삽입 실패: {result.stderr}")
                print(f"  🔍 실패한 SQL 길이: {len(insert_sql):,} 문자")
                print(f"  🚨 치명적 오류로 ETL 중단합니다.")
                raise Exception(f"DB 삽입 실패: {result.stderr}")
        
        return inserted_count
    
    def run_etl(self):
        """전체 ETL 프로세스 실행"""
        print("🚀 Daily OD Analysis ETL 시작 (완전 재작성)")
        print("=" * 80)
        
        # 1. DB 연결 확인
        if not self.connect_db():
            return False
        
        # 2. 메타데이터 로드
        if not self.load_bus_stops_metadata():
            print("❌ 정류장 메타데이터 로드 실패")
            return False
            
        if not self.load_station_routes():
            print("⚠️ 노선 정보 로드 실패 - 계속 진행")
        
        # 3. 날짜별 CSV 처리
        start_date = datetime(2025, 7, 15)
        all_records = []
        
        for i in range(17):  # 2025-07-15 ~ 2025-07-31
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y%m%d')
            
            records = self.process_csv_file(date_str)
            all_records.extend(records)
            
            # 메모리 관리: 10만 레코드마다 DB 삽입
            if len(all_records) >= 100000:
                print(f"\n💾 중간 삽입: {len(all_records):,}개 레코드")
                inserted = self.insert_records_to_db(all_records)
                print(f"💾 중간 삽입 완료: {inserted:,}개 레코드 삽입됨")
                all_records = []  # 메모리 해제
        
        # 4. 최종 DB 삽입
        if all_records:
            inserted_count = self.insert_records_to_db(all_records)
            
            print(f"\n🎉 ETL 완료!")
            print(f"  - 처리 기간: 2025-07-15 ~ 2025-07-31 (17일)")
            print(f"  - 최종 삽입: {inserted_count:,}개")
            
            return inserted_count > 0
        else:
            print("❌ 처리할 레코드가 없습니다.")
            return False

if __name__ == "__main__":
    etl = DailyODAnalysisETL()
    success = etl.run_etl()
    
    if success:
        print("\n✅ ETL 프로세스 성공!")
        sys.exit(0)
    else:
        print("\n❌ ETL 프로세스 실패!")
        sys.exit(1)