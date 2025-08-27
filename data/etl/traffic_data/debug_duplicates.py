#!/usr/bin/env python3
"""
ETL 중복 키 디버깅 스크립트
실제 API 데이터에서 중복 생성되는 PK를 찾아보자
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# ETL 클래스 임포트
sys.path.append('/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data/etl/traffic_data')
from etl_trafficData import SeoulTrafficETL

def debug_api_duplicates(api_num: int, date: str = '20250719'):
    """특정 API의 중복 키 생성 패턴 분석"""
    print(f"\n🔍 API{api_num} 중복 키 분석 - 날짜: {date}")
    
    etl = SeoulTrafficETL()
    
    # API 설정
    api_config = etl.api_config['apis'][f'API{api_num}']
    service_key = os.getenv('SEOUL_TRAFFIC_API_KEY')
    
    # 테스트용 소량 데이터 요청 (1개 페이지만)
    params = {
        'serviceKey': service_key,
        'type': 'json',
        'startIndex': 1,
        'endIndex': 10,  # 소량만 테스트
        'USE_DT': date
    }
    
    try:
        url = api_config['endpoint']
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API 호출 실패: {response.status_code}")
            return
            
        data = response.json()
        
        if api_num in [1, 3]:
            # 노드별 승차 데이터 분석
            items = data.get('CardBusStatisticsService', {}).get('row', [])
            keys = []
            for item in items:
                for hour in range(24):
                    hour_str = f"{hour:02d}"
                    key = (date, item.get('ROUTE_ID', ''), item.get('NODE_ID', ''), hour_str)
                    keys.append(key)
        
        elif api_num in [2, 4]:
            # 구간별 이동 데이터 분석  
            items = data.get('CardBusStatisticsService', {}).get('row', [])
            keys = []
            for item in items:
                for hour in range(24):
                    hour_str = f"{hour:02d}"
                    key = (date, item.get('ROUTE_ID', ''), item.get('FR_NODE_ID', ''), item.get('TO_NODE_ID', ''), hour_str)
                    keys.append(key)
        
        # 중복 검사
        key_counts = Counter(keys)
        duplicates = {k: v for k, v in key_counts.items() if v > 1}
        
        print(f"✅ 총 키 개수: {len(keys)}")
        print(f"✅ 유니크 키 개수: {len(key_counts)}")
        
        if duplicates:
            print(f"🚨 중복 키 발견: {len(duplicates)}개")
            for key, count in list(duplicates.items())[:5]:  # 처음 5개만 출력
                print(f"   {key} -> {count}회 중복")
        else:
            print("✅ 중복 없음")
            
        return len(duplicates)
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        return None

def debug_batch_processing():
    """배치 처리 과정에서 중복 생성 패턴 분석"""
    print("\n🔍 배치 처리 중복 분석")
    
    # 임시 배치 데이터 생성 (실제 ETL과 동일한 로직)
    test_batch = [
        ('20250719', 'ROUTE_001', 'NODE_001', '08'),
        ('20250719', 'ROUTE_001', 'NODE_001', '09'), 
        ('20250719', 'ROUTE_001', 'NODE_001', '08'),  # 의도적 중복
        ('20250719', 'ROUTE_002', 'NODE_002', '10'),
    ]
    
    # 중복 검사 로직 테스트
    keys_seen = set()
    duplicates = []
    
    for record in test_batch:
        key = record  # 전체가 PK
        if key in keys_seen:
            duplicates.append(key)
            print(f"🚨 중복 발견: {key}")
        keys_seen.add(key)
    
    print(f"배치 크기: {len(test_batch)}")
    print(f"중복 개수: {len(duplicates)}")
    
if __name__ == "__main__":
    print("=" * 60)
    print("ETL 중복 키 디버깅")
    print("=" * 60)
    
    # 각 API 별로 중복 분석
    for api_num in [1, 2]:
        debug_api_duplicates(api_num)
    
    # 배치 처리 테스트
    debug_batch_processing()