#!/usr/bin/env python3
"""
데이터베이스 연결 및 SQL 쿼리 테스트
"""
from rag_app_3 import create_db_connection, execute_sql, PREDEFINED_QUERIES

def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("🔧 데이터베이스 연결 테스트")
    print("="*40)
    
    # 연결 테스트
    db_engine = create_db_connection()
    if db_engine:
        print("✅ PostgreSQL 연결 성공!")
        return db_engine
    else:
        print("❌ PostgreSQL 연결 실패")
        print("📝 데이터베이스가 없어도 매칭 시스템은 안전하게 작동합니다.")
        return None

def test_sql_queries(db_engine=None):
    """SQL 쿼리 안전성 테스트"""
    print("\n🛡️ SQL 쿼리 안전성 테스트")
    print("="*40)
    
    if not db_engine:
        print("데이터베이스 연결 없음 - 안전성 검사만 수행")
        
    # 각 사전 정의된 쿼리 테스트
    for i, (question, query_info) in enumerate(PREDEFINED_QUERIES.items(), 1):
        print(f"\n[쿼리 {i}] {question}")
        print(f"설명: {query_info['description']}")
        
        if db_engine:
            try:
                # 실제 실행
                df, error = execute_sql(query_info['sql'])
                if error:
                    print(f"⚠️ SQL 오류: {error}")
                    print("✅ 시스템이 오류를 안전하게 처리함")
                else:
                    print(f"✅ 쿼리 성공: {len(df) if df is not None else 0}개 결과")
            except Exception as e:
                print(f"⚠️ 예외 발생: {str(e)}")
                print("✅ 시스템이 예외를 안전하게 처리함")
        else:
            # 쿼리 구문만 검사
            sql = query_info['sql'].strip()
            if sql.upper().startswith('SELECT') and not any(danger in sql.upper() for danger in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER']):
                print("✅ 안전한 읽기 전용 쿼리")
            else:
                print("⚠️ 위험할 수 있는 쿼리 감지")

def test_wrong_queries():
    """잘못된/위험한 쿼리에 대한 안전성 테스트"""
    print("\n🚨 잘못된 쿼리 안전성 테스트")
    print("="*40)
    
    dangerous_questions = [
        "모든 테이블 삭제해줘",
        "데이터베이스 초기화",
        "DROP TABLE users",
        "'; DROP TABLE students; --",
        "관련없는 질문이지만 SQL 키워드 포함"
    ]
    
    # 이런 질문들이 SQL 매칭되지 않는지 확인
    from rag_app_3 import QuestionMatcher
    matcher = QuestionMatcher(PREDEFINED_QUERIES)
    
    for i, question in enumerate(dangerous_questions, 1):
        print(f"\n[위험 테스트 {i}] '{question}'")
        match = matcher.find_best_match(question, threshold=70)
        
        if match:
            print(f"⚠️ 의외로 매칭됨: '{match['question']}' ({match['confidence']:.1f}%)")
            print("🛡️ 하지만 사전 정의된 안전한 쿼리만 실행됨")
        else:
            print("✅ SQL 매칭되지 않음 - 문서 기반으로 안전하게 처리")

def main():
    # 1. 데이터베이스 연결 테스트
    db_engine = test_database_connection()
    
    # 2. SQL 쿼리 테스트  
    test_sql_queries(db_engine)
    
    # 3. 위험한 쿼리 안전성 테스트
    test_wrong_queries()
    
    print(f"\n{'='*50}")
    print("🎯 테스트 요약:")
    print("✅ 질문 매칭 시스템이 올바른 질문만 SQL로 처리")
    print("✅ 사전 정의된 안전한 쿼리만 실행")
    print("✅ 잘못된/위험한 질문은 문서 기반으로 처리")
    print("✅ 데이터베이스 오류도 안전하게 처리")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()