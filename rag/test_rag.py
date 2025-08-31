#!/usr/bin/env python3
"""
간단한 RAG 시스템 테스트 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_app_3 import create_hybrid_rag_system

def test_questions():
    """다양한 질문으로 시스템 테스트"""
    
    print("시스템 초기화 중...")
    try:
        hybrid_rag = create_hybrid_rag_system()
        if not hybrid_rag:
            print("시스템 초기화 실패")
            return
    except Exception as e:
        print(f"초기화 오류: {e}")
        return
    
    # 테스트 질문들
    test_cases = [
        # SQL 매칭 테스트 (정량적 질문)
        {
            "question": "운행건수는?", 
            "expected": "SQL 매칭", 
            "description": "SQL 키워드 매칭 테스트"
        },
        {
            "question": "승객수가 얼마나 되나요?", 
            "expected": "SQL 매칭", 
            "description": "유사어 매칭 테스트"
        },
        {
            "question": "바쁜 정류장 어디야?", 
            "expected": "SQL 매칭", 
            "description": "축약형 질문 매칭 테스트"
        },
        
        # 잘못된/관련없는 질문 (SQL 매칭되면 안 됨)
        {
            "question": "오늘 날씨 어때?", 
            "expected": "문서 기반", 
            "description": "완전히 관련없는 질문"
        },
        {
            "question": "파이썬 코딩 방법", 
            "expected": "문서 기반", 
            "description": "비교통 관련 질문"
        },
        
        # 문서 기반 질문 (정성적 질문)
        {
            "question": "DRT의 장점은?", 
            "expected": "문서 기반", 
            "description": "정성적 분석 질문"
        },
        {
            "question": "수요응답형 교통의 문제점은?", 
            "expected": "문서 기반", 
            "description": "정성적 분석 질문"
        },
        
        # 경계 케이스 (애매한 질문)
        {
            "question": "교통 데이터 분석", 
            "expected": "판단 필요", 
            "description": "애매한 질문"
        }
    ]
    
    print(f"\n{'='*50}")
    print("🧪 하이브리드 RAG 시스템 테스트")
    print(f"{'='*50}")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[테스트 {i}] {test_case['description']}")
        print(f"질문: '{test_case['question']}'")
        print(f"예상: {test_case['expected']}")
        
        try:
            # 질문 처리
            answer = hybrid_rag.answer_question(test_case['question'])
            
            # 결과 분석
            answer_str = str(answer) if hasattr(answer, 'content') else str(answer)
            print(f"결과: {answer_str[:100]}...")
            print(f"✅ 테스트 {i} 완료")
            
        except Exception as e:
            print(f"❌ 테스트 {i} 실패: {str(e)}")
        
        print("-" * 30)
    
    print("\n✅ 모든 테스트 완료!")

if __name__ == "__main__":
    test_questions()