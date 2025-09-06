#!/usr/bin/env python3
"""
Test script to demonstrate the adaptive response system
"""

# Simple test to show the question type analysis and adaptive prompt generation
class MockRAGService:
    def _analyze_question_type(self, question: str) -> str:
        """Analyze question type and determine appropriate response strategy"""
        question_lower = question.lower()
        
        # 장점/효과 질문을 먼저 체크 (더 구체적인 키워드이므로)
        if any(keyword in question_lower for keyword in ["장점", "효과", "이점", "혜택", "좋은점", "도움"]):
            return "benefits"
        
        # 정의/개념 질문
        elif any(keyword in question_lower for keyword in ["정의는", "무엇인가", "개념", "의미", "뜻", "란 무엇"]):
            return "definition"
        
        # 방법/절차 질문
        elif any(keyword in question_lower for keyword in ["방법", "절차", "과정", "단계", "어떻게", "방식"]):
            return "procedure"
        
        # 사례/예시 질문
        elif any(keyword in question_lower for keyword in ["사례", "예시", "예", "실제", "도입", "적용"]):
            return "examples"
        
        # 비교/차이점 질문
        elif any(keyword in question_lower for keyword in ["차이", "비교", "다른점", "구별", "vs"]):
            return "comparison"
        
        # 포괄적 설명 요청
        elif any(keyword in question_lower for keyword in ["포괄적", "전체적", "종합적", "자세히", "상세히", "전반적"]):
            return "comprehensive"
        
        # 문제/해결 질문
        elif any(keyword in question_lower for keyword in ["문제", "해결", "개선", "최적화", "향상"]):
            return "problem_solution"
        
        # 특징/구성요소 질문
        elif any(keyword in question_lower for keyword in ["특징", "구성", "요소", "구조", "특성"]):
            return "characteristics"
        
        # 기본 질문 (단순 답변)
        else:
            return "general"
    
    def _create_adaptive_prompt(self, question: str, context: str, answer_type: str) -> str:
        """Create adaptive prompt based on question type"""
        
        base_context = f"질문: {question}\n참고자료:\n{context}\n\n"
        
        if answer_type == "definition":
            return base_context + """DRT 전문가로서 다음과 같이 간결하게 정의해주세요:

🔍 핵심 정의
- 질문에서 요구하는 개념의 핵심 정의를 명확하고 간결하게 제시

📝 핵심 특징 (2-3가지)
- 가장 중요한 특징이나 구성요소만 간략히 언급

답변:"""
        
        elif answer_type == "benefits":
            return base_context + """DRT 전문가로서 다음과 같이 장점을 설명해주세요:

✅ 주요 장점들
- 핵심적인 장점 3-5가지를 구체적으로 제시
- 각 장점에 대한 간략한 설명 포함

💡 실무적 효과
- 실제 도입 시 기대되는 효과나 개선점

답변:"""
        
        elif answer_type == "comprehensive":
            return base_context + """DRT 전문가로서 다음과 같이 포괄적으로 설명해주세요:

🔍 1단계: 기본 개념
- 핵심 정의와 개념 설명

📊 2단계: 구성 요소
- 주요 구성요소나 특징들

💡 3단계: 실무 적용
- 실제 운영 방식이나 절차

✅ 4단계: 효과와 전망
- 기대 효과와 향후 발전 방향

답변:"""
        
        else:  # general
            return base_context + """DRT 전문가로서 질문에 적절한 수준으로 답변해주세요:

💬 핵심 답변
- 질문에서 요구하는 정보를 명확하고 간결하게 제시
- 필요한 경우 추가 설명이나 배경 정보 포함

답변:"""

def test_adaptive_response():
    """Test the adaptive response system"""
    mock_service = MockRAGService()
    
    # Test questions with expected response types
    test_cases = [
        ("DRT의 정의는?", "definition", "정의 질문 - 간결한 정의와 핵심 특징만 제공"),
        ("DRT 시스템의 장점은 무엇인가요?", "benefits", "장점 질문 - 주요 장점들과 실무적 효과 제공"),
        ("DRT 시스템을 포괄적으로 설명해주세요", "comprehensive", "포괄적 설명 - 4단계 전체 과정으로 상세 설명"),
        ("DRT는 무엇인가요?", "definition", "정의 질문 - 개념 위주의 간결한 답변"),
        ("수요응답형 교통의 효과는?", "benefits", "효과/장점 질문 - 장점과 효과에 집중"),
    ]
    
    print("🧪 Adaptive Response System Test")
    print("=" * 60)
    
    for i, (question, expected_type, description) in enumerate(test_cases, 1):
        detected_type = mock_service._analyze_question_type(question)
        
        print(f"\n{i}. 질문: {question}")
        print(f"   예상 유형: {expected_type}")
        print(f"   탐지 유형: {detected_type}")
        print(f"   설명: {description}")
        print(f"   매칭: {'✅ 성공' if detected_type == expected_type else '❌ 실패'}")
        
        # Show the adaptive prompt structure
        context = "[예시 문서 내용]"
        prompt = mock_service._create_adaptive_prompt(question, context, detected_type)
        
        print(f"\n   생성된 프롬프트 구조:")
        lines = prompt.split('\n')
        for line in lines[3:8]:  # Show first few lines of the adaptive part
            if line.strip():
                print(f"   {line}")
        print("   ...")
        
        print("-" * 50)

if __name__ == "__main__":
    test_adaptive_response()