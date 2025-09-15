#!/usr/bin/env python3
"""
COPY 방식 ETL - 기존 etl_daily_od_analysis_fixed.py 로직 그대로 사용
"""

import os
import csv
import json
import subprocess
import pandas as pd
from pathlib import Path
import math
import time

# 기존 ETL 클래스 상속
import sys
import os
sys.path.append(os.path.dirname(__file__))

from etl_daily_od_analysis_fixed import DailyODAnalysisETL

class DailyODAnalysisETLCopyFixed(DailyODAnalysisETL):
    
    def bulk_insert_with_copy(self, records, date_str):
        """COPY 명령으로 초고속 벌크 삽입"""
        if not records:
            print("❌ 삽입할 레코드가 없습니다")
            return 0
            
        csv_start_time = time.time()
        print(f"🚀 COPY 벌크 삽입 시작")
        print(f"   📊 레코드 수: {len(records):,}개") 
        print(f"   📅 날짜: {date_str}")
        print(f"   ⏰ 시작 시간: {pd.Timestamp.now().strftime('%H:%M:%S')}")
        print("=" * 50)
        
        # 1. CSV 파일 생성
        temp_csv = f"/tmp/od_{date_str}.csv"
        
        # 컬럼 순서 정의 (DB 스키마와 동일)
        columns = [
            'analysis_date', 'from_station_id', 'to_station_id',
            'from_station_name', 'from_coordinates_x', 'from_coordinates_y',
            'from_district_code', 'from_district_name', 'from_admin_dong', 'from_routes',
            'to_station_name', 'to_coordinates_x', 'to_coordinates_y',
            'to_district_code', 'to_district_name', 'to_admin_dong', 'to_routes',
            'h00', 'h01', 'h02', 'h03', 'h04', 'h05', 'h06', 'h07', 'h08', 'h09', 'h10', 'h11',
            'h12', 'h13', 'h14', 'h15', 'h16', 'h17', 'h18', 'h19', 'h20', 'h21', 'h22', 'h23',
            'estimated_distance_km',
            'common_routes', 'from_only_routes', 'to_only_routes',
            'direct_connection_count', 'transfer_required'
        ]
        
        with open(temp_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            
            for record in records:
                row = []
                for col in columns:
                    value = record.get(col, '')
                    
                    # JSONB 필드 처리
                    if col in ['from_routes', 'to_routes', 'common_routes', 'from_only_routes', 'to_only_routes']:
                        if isinstance(value, str):
                            # 이미 JSON 문자열인 경우 (기존 ETL에서 json.dumps 된 상태)
                            row.append(value)
                        elif isinstance(value, (list, dict)):
                            # 객체인 경우 JSON 문자열로 변환
                            json_str = json.dumps(value, ensure_ascii=False)
                            row.append(json_str)
                        else:
                            row.append('[]')
                    else:
                        row.append(str(value) if value is not None else '')
                
                writer.writerow(row)
        
        print(f"📝 임시 CSV 생성: {temp_csv}")
        
        # 2. PostgreSQL 컨테이너로 파일 복사
        copy_cmd = ['docker', 'cp', temp_csv, 'ddf-postgres:/tmp/od_batch.csv']
        result = subprocess.run(copy_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"파일 복사 실패: {result.stderr}")
        
        # 3. COPY 명령 실행
        copy_sql = f"""
        COPY daily_od_analysis (
            {', '.join(columns)}
        )
        FROM '/tmp/od_batch.csv'
        WITH (FORMAT CSV, QUOTE '\"');
        """
        
        psql_cmd = [
            'docker', 'exec', 'ddf-postgres', 'psql', '-U', 'ddf_user', '-d', 'ddf_db',
            '-c', copy_sql
        ]
        
        result = subprocess.run(psql_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"COPY 실행 실패: {result.stderr}")
        
        # 임시 파일 정리
        os.remove(temp_csv)
        
        # 삽입된 행 수 추출
        if "COPY" in result.stdout:
            inserted_count = int(result.stdout.strip().split("COPY ")[1])
            print(f"✅ COPY 완료: {inserted_count:,}개 레코드 삽입")
            return inserted_count
        else:
            print(f"✅ COPY 완료")
            return len(records)
    
    def run_etl_copy(self, target_dates=None):
        """COPY 방식으로 ETL 실행"""
        print("🚀 Daily OD Analysis ETL (COPY 방식) 시작")
        print("=" * 80)
        
        # 메타데이터 로드 (기존 방식 그대로)
        if not self.load_bus_stops_metadata():
            print("❌ 정류장 메타데이터 로드 실패")
            return False
        
        if not self.load_station_routes():
            print("❌ 노선 정보 로드 실패") 
            return False
        
        # 대상 날짜 설정
        if target_dates is None:
            target_dates = ["20250715"]  # 테스트용
        
        total_inserted = 0
        
        for i, date_str in enumerate(target_dates, 1):
            try:
                print(f"\n📅 처리 중: {date_str} ({i}/{len(target_dates)})")
                print("=" * 50)
                
                # 1. 기존 로직으로 레코드 생성 (process_csv_file 그대로 사용)
                records = self.process_csv_file(date_str)
                
                if not records:
                    print(f"⚠️ {date_str}: 처리할 데이터 없음")
                    continue
                
                # 2. COPY로 벌크 삽입
                inserted = self.bulk_insert_with_copy(records, date_str)
                total_inserted += inserted
                
                # 3. 메모리 해제
                del records
                
                # 4. 진행률 표시
                progress = i / len(target_dates) * 100
                print(f"✅ {date_str} 완료: {inserted:,}개 삽입")
                print(f"📊 누적 삽입: {total_inserted:,}개")
                print(f"🚀 전체 진행률: {progress:.1f}%")
                
            except Exception as e:
                print(f"❌ {date_str} 실패: {e}")
                continue
        
        print("=" * 80)
        print(f"🎉 ETL 완료! 총 {total_inserted:,}개 레코드 삽입")
        return total_inserted > 0

def main():
    etl = DailyODAnalysisETLCopyFixed()
    
    # 2025-07-15 ~ 2025-07-31 (17일간) 처리
    from datetime import datetime, timedelta
    
    start_date = datetime(2025, 7, 15)
    target_dates = []
    
    for i in range(17):  # 17일간
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%Y%m%d')
        target_dates.append(date_str)
    
    print(f"📅 처리 예정 날짜: {len(target_dates)}일")
    print(f"   시작: {target_dates[0]}")
    print(f"   종료: {target_dates[-1]}")
    
    success = etl.run_etl_copy(target_dates)
    
    if success:
        print(f"\n🎊 COPY 방식 ETL 성공! ({len(target_dates)}일 처리)")
    else:
        print(f"\n💥 COPY 방식 ETL 실패! ({len(target_dates)}일 처리)")

if __name__ == "__main__":
    main()