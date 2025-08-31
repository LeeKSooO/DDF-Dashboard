#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 구조 및 데이터 확인 스크립트
"""
import psycopg2
import pandas as pd
from sqlalchemy import create_engine, inspect, text

def check_database():
    """데이터베이스 연결 및 구조 확인"""
    
    # 데이터베이스 연결 정보 (rag_app_3.py와 동일하게)
    DATABASE_URL = "postgresql://ddf_user:ddf_password@localhost:5432/ddf_db"
    
    try:
        # SQLAlchemy 엔진 생성
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        
        print("🔍 PostgreSQL 데이터베이스 구조 분석")
        print("=" * 50)
        
        # 1. 테이블 목록 확인
        tables = inspector.get_table_names()
        print(f"📋 총 {len(tables)}개의 테이블 발견:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table}")
        print()
        
        # 2. 각 테이블의 스키마 정보 출력
        for table_name in tables:
            print(f"📊 테이블: {table_name}")
            print("-" * 30)
            
            # 컬럼 정보
            columns = inspector.get_columns(table_name)
            print("컬럼 정보:")
            for col in columns:
                nullable = "NULL 가능" if col['nullable'] else "NOT NULL"
                default = f" (기본값: {col['default']})" if col['default'] else ""
                print(f"  - {col['name']}: {col['type']} {nullable}{default}")
            
            # 행 수 확인
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = result.scalar()
                print(f"총 행 수: {row_count:,}개")
            
            # 샘플 데이터 (처음 5개 행)
            if row_count > 0:
                print("\n샘플 데이터 (최대 5개 행):")
                df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 5", engine)
                print(df.to_string(index=False))
            else:
                print("데이터 없음")
            
            print("\n" + "=" * 50 + "\n")
        
        # 3. 전체 데이터베이스 요약
        print("📈 데이터베이스 요약")
        print("-" * 20)
        total_rows = 0
        for table_name in tables:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                total_rows += count
                print(f"{table_name}: {count:,}개 행")
        
        print(f"\n전체 데이터: {total_rows:,}개 행")
        
    except Exception as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")
        return False
    
    return True

if __name__ == "__main__":
    check_database()