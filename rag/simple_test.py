#!/usr/bin/env python3
"""
질문 매칭 시스템만 간단히 테스트
"""
from rag_app_3 import QuestionMatcher, PREDEFINED_QUERIES

def test_question_matching():
    """질문 매칭 기능만 단독 테스트"""
    
    matcher = QuestionMatcher(PREDEFINED_QUERIES)
    
    # 테스트 케이스들
    test_questions = [
        # 정확한 매칭이 되어야 하는 질문들
        ("지난달 운행건수는?", True, "정확한 매칭"),
        ("운행건수는?", True, "축약형"),  
        ("총 운행건수 얼마나 되나요?", True, "유사 표현"),
        ("평균 승객수?", True, "축약형"),
        ("가장 바쁜 정류장은?", True, "정확한 매칭"),
        ("바쁜 정류장 어디야?", True, "구어체"),
        ("노선별 이용률은?", True, "정확한 매칭"),
        ("시간대별 패턴은?", True, "축약형"),
        
        # 매칭이 되면 안 되는 질문들 (임계값 70% 미만)
        ("오늘 날씨 어때?", False, "완전히 관련없는 질문"),
        ("파이썬 코딩 방법", False, "비교통 관련"),
        ("점심 뭐 먹을까?", False, "일상 질문"),
        ("DRT의 장점은?", False, "정성적 질문"),
        ("교통정책 분석", False, "모호한 질문"),
    ]
    
    print("🧪 질문 매칭 시스템 테스트")
    print("="*50)
    print(f"임계값: 70% (이상이면 SQL 매칭, 미만이면 문서 기반)")
    print("="*50)
    
    correct_predictions = 0
    total_tests = len(test_questions)
    
    for i, (question, should_match, description) in enumerate(test_questions, 1):
        print(f"\n[테스트 {i}] {description}")
        print(f"질문: '{question}'")
        
        match_result = matcher.find_best_match(question, threshold=70)
        is_matched = match_result is not None
        
        if is_matched:
            print(f"📊 SQL 매칭: '{match_result['question']}' (신뢰도: {match_result['confidence']:.1f}%)")
            prediction = "SQL 매칭"
        else:
            print("📚 SQL 매칭 없음 - 문서 기반")
            prediction = "문서 기반"
        
        # 예측 정확도 체크
        expected = "SQL 매칭" if should_match else "문서 기반"
        is_correct = (is_matched == should_match)
        
        if is_correct:
            print(f"✅ 정확 예측: {prediction}")
            correct_predictions += 1
        else:
            print(f"❌ 잘못된 예측: {prediction} (예상: {expected})")
        
        print("-" * 40)
    
    # 결과 요약
    accuracy = (correct_predictions / total_tests) * 100
    print(f"\n📊 테스트 결과:")
    print(f"정확도: {correct_predictions}/{total_tests} ({accuracy:.1f}%)")
    
    if accuracy >= 80:
        print("✅ 매칭 시스템이 잘 작동하고 있습니다!")
    else:
        print("⚠️ 매칭 시스템 개선이 필요합니다.")
    
    # 사용 가능한 SQL 질문 목록 표시
    print(f"\n📋 사용 가능한 SQL 질문 ({len(PREDEFINED_QUERIES)}개):")
    for i, q in enumerate(PREDEFINED_QUERIES.keys(), 1):
        print(f"  {i}. {q}")

if __name__ == "__main__":
    test_question_matching()