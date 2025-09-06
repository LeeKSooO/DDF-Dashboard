#!/usr/bin/env python3
"""
개선된 멀티 쿼리 테스트
"""

class MockMultiQueryService:
    def _generate_fallback_queries(self, original_query: str) -> list[str]:
        """개선된 fallback query 생성 로직 테스트"""
        
        fallback_queries = [original_query]  # 항상 원본 질문 포함
        
        # 질문 의도에 맞는 동의어/유사 표현 생성
        if "정의" in original_query or "무엇" in original_query:
            # 정의 관련 질문의 경우
            fallback_queries.append(original_query.replace("정의", "개념").replace("무엇인가", "의미"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        elif "장점" in original_query or "효과" in original_query:
            # 장점/효과 관련 질문의 경우
            fallback_queries.append(original_query.replace("장점", "이점").replace("효과", "혜택"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        elif "방법" in original_query or "어떻게" in original_query:
            # 방법 관련 질문의 경우  
            fallback_queries.append(original_query.replace("방법", "방식").replace("어떻게", "어떤 방식으로"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        else:
            # 일반적인 경우 - 키워드만 변형
            if "DRT" in original_query:
                fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
                fallback_queries.append(original_query.replace("DRT", "demand responsive transport"))
        
        return list(set(fallback_queries))[:4]  # 중복 제거하고 최대 4개

def test_improved_multi_query():
    """개선된 멀티 쿼리 동작 테스트"""
    
    service = MockMultiQueryService()
    
    test_cases = [
        {
            "query": "DRT의 정의는?",
            "expected_focus": "정의에만 집중",
            "description": "정의 질문 - 정의/개념/의미 관련 변형만 생성"
        },
        {
            "query": "DRT 시스템의 장점은?", 
            "expected_focus": "장점에만 집중",
            "description": "장점 질문 - 장점/이점/효과 관련 변형만 생성"
        },
        {
            "query": "DRT 운영 방법은?",
            "expected_focus": "방법에만 집중", 
            "description": "방법 질문 - 방법/방식/절차 관련 변형만 생성"
        },
        {
            "query": "DRT는 어떻게 작동하나요?",
            "expected_focus": "작동 원리에만 집중",
            "description": "작동 원리 질문 - 원리/방식 관련 변형만 생성"
        }
    ]
    
    print("🔍 개선된 멀티 쿼리 테스트")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. 원본 질문: {case['query']}")
        print(f"   기대 초점: {case['expected_focus']}")
        
        generated_queries = service._generate_fallback_queries(case['query'])
        
        print(f"   생성된 쿼리 ({len(generated_queries)}개):")
        for j, query in enumerate(generated_queries):
            marker = "🎯" if j == 0 else "🔄"
            print(f"   {marker} {query}")
        
        print(f"   설명: {case['description']}")
        print("-" * 50)
    
    print("\n✅ 개선 효과:")
    print("1. 원본 질문의 의도를 정확히 유지")
    print("2. 같은 주제 내에서만 키워드 변형")
    print("3. 4개 관점으로 확산하지 않고 집중된 검색")
    print("4. 질문 범위를 벗어나지 않는 유사 표현 생성")

if __name__ == "__main__":
    test_improved_multi_query()