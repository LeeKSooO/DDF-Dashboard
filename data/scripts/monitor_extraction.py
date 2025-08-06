#!/usr/bin/env python3
"""
DRT 데이터 추출 진행 상황 모니터링 스크립트
"""

import os
import time
import subprocess
from datetime import datetime

def check_extraction_status():
    """추출 진행 상황 확인"""
    
    print("=== DRT 데이터 추출 상태 모니터링 ===")
    print(f"확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 실행 중인 프로세스 확인
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = [line for line in result.stdout.split('\n') 
                    if 'extract_drt_features_to_csv.py' in line and 'grep' not in line]
        
        if processes:
            print("🔄 추출 프로세스 실행 중:")
            for proc in processes:
                print(f"   {proc}")
        else:
            print("⏸️ 추출 프로세스가 실행되지 않음")
    except Exception as e:
        print(f"프로세스 확인 실패: {e}")
    
    print()
    
    # 2. 로그 파일 확인
    log_file = "drt_extraction.log"
    if os.path.exists(log_file):
        print("📋 최근 로그 (마지막 10줄):")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(f"   {line.strip()}")
        
        # 진행률 계산
        last_processed = 0
        for line in reversed(lines):
            if '누적:' in line:
                try:
                    start = line.find('누적: ') + 6
                    end = line.find(')')
                    processed_str = line[start:end].replace(',', '')
                    last_processed = int(processed_str)
                    break
                except:
                    continue
        
        total_records = 4682809
        progress = (last_processed / total_records) * 100 if total_records > 0 else 0
        
        print(f"\n📊 진행 상황:")
        print(f"   처리된 레코드: {last_processed:,} / {total_records:,}")
        print(f"   진행률: {progress:.1f}%")
        
    else:
        print("❌ 로그 파일을 찾을 수 없음")
    
    print()
    
    # 3. CSV 파일 확인
    csv_files = [f for f in os.listdir('data/processed') if f.startswith('drt_features_') and f.endswith('.csv')]
    csv_files.sort(key=lambda x: os.path.getmtime(f'data/processed/{x}'), reverse=True)
    
    if csv_files:
        latest_csv = csv_files[0]
        csv_path = f'data/processed/{latest_csv}'
        file_size_mb = os.path.getsize(csv_path) / (1024**2)
        mod_time = datetime.fromtimestamp(os.path.getmtime(csv_path))
        
        print(f"📁 최신 CSV 파일:")
        print(f"   파일명: {latest_csv}")
        print(f"   크기: {file_size_mb:.1f} MB")
        print(f"   마지막 수정: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 파일이 최근에 수정되었는지 확인 (5분 이내)
        if (datetime.now() - mod_time).seconds < 300:
            print("   상태: 🔄 활발히 업데이트 중")
        else:
            print("   상태: ⏸️ 업데이트 중단됨")
    else:
        print("❌ CSV 파일을 찾을 수 없음")

def restart_extraction():
    """추출 프로세스 재시작"""
    print("\n🔄 추출 프로세스 재시작...")
    
    cmd = ["python3", "data_preparation/extract_drt_features_to_csv.py", "50000"]
    
    try:
        # 백그라운드 실행
        process = subprocess.Popen(cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 text=True)
        
        print(f"✅ 추출 프로세스 시작됨 (PID: {process.pid})")
        print("📋 실시간 로그 모니터링을 원하면:")
        print("   tail -f drt_extraction.log")
        print("\n📊 진행 상황 확인을 원하면:")
        print("   python3 monitor_extraction.py")
        
        return process
        
    except Exception as e:
        print(f"❌ 프로세스 시작 실패: {e}")
        return None

def main():
    """메인 함수"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restart':
        restart_extraction()
    else:
        check_extraction_status()
        
        # 진행 상태에 따른 권장 행동
        print("\n💡 권장 행동:")
        print("   - 프로세스가 중단된 경우: python3 monitor_extraction.py restart")
        print("   - 실시간 모니터링: tail -f drt_extraction.log")
        print("   - 상태 재확인: python3 monitor_extraction.py")

if __name__ == "__main__":
    main()