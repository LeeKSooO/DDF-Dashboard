#!/usr/bin/env python3
"""
수정된 SQL 쿼리 테스트 스크립트
"""
import psycopg2
import pandas as pd
from sqlalchemy import create_engine, text

# 데이터베이스 연결 정보
DATABASE_URL = "postgresql://ddf_user:ddf_password@localhost:5432/ddf_db"

# 수정된 쿼리들
QUERIES = {
    "8월달 총 운행건수": """
        SELECT 
            COUNT(DISTINCT route_id, record_date, hour) as total_operations,
            SUM(ride_passenger + alight_passenger) as total_passengers,
            COUNT(DISTINCT node_id) as active_stations,
            ROUND(AVG(ride_passenger + alight_passenger), 2) as avg_passengers_per_operation
        FROM station_passenger_history 
        WHERE record_date >= '2025-08-01'
          AND record_date < '2025-09-01'
          AND (ride_passenger > 0 OR alight_passenger > 0)
    """,
    
    "가장 바쁜 정류장 (상위 5개)": """
        SELECT 
            sph.station_name,
            sph.node_id,
            SUM(sph.ride_passenger + sph.alight_passenger) as total_passengers,
            SUM(sph.ride_passenger) as total_boarding,
            SUM(sph.alight_passenger) as total_alighting,
            ROUND(AVG(sph.ride_passenger + sph.alight_passenger), 2) as avg_passengers_per_hour
        FROM station_passenger_history sph
        WHERE sph.record_date >= '2025-08-01'
          AND sph.record_date < '2025-09-01'
          AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
        GROUP BY sph.node_id, sph.station_name
        ORDER BY total_passengers DESC
        LIMIT 5
    """,
    
    "시간대별 이용 패턴 (피크 시간)": """
        SELECT 
            sph.hour,
            COUNT(*) as total_operations,
            SUM(sph.ride_passenger + sph.alight_passenger) as total_passengers,
            ROUND(AVG(sph.ride_passenger + sph.alight_passenger), 2) as avg_passengers,
            CASE 
                WHEN sph.hour BETWEEN 7 AND 9 THEN 'Morning Peak'
                WHEN sph.hour BETWEEN 17 AND 19 THEN 'Evening Peak'
                WHEN sph.hour BETWEEN 10 AND 16 THEN 'Daytime Off-Peak'
                WHEN sph.hour BETWEEN 20 AND 23 THEN 'Evening Off-Peak'
                ELSE 'Night/Early Morning'
            END as time_category
        FROM station_passenger_history sph
        WHERE sph.record_date >= '2025-08-01'
          AND sph.record_date < '2025-09-01'
          AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
        GROUP BY sph.hour
        ORDER BY sph.hour
    """
}

def test_queries():
    """수정된 쿼리들을 테스트"""
    try:
        engine = create_engine(DATABASE_URL)
        
        print("🔍 수정된 SQL 쿼리 테스트")
        print("=" * 60)
        
        for query_name, sql in QUERIES.items():
            print(f"\n📊 {query_name}")
            print("-" * 40)
            
            try:
                df = pd.read_sql(sql, engine)
                if len(df) > 0:
                    print(f"✅ 쿼리 성공: {len(df)}개 결과")
                    print(df.to_string(index=False))
                else:
                    print("⚠️ 결과 없음")
                    
            except Exception as e:
                print(f"❌ 쿼리 실패: {e}")
            
            print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")

if __name__ == "__main__":
    test_queries()