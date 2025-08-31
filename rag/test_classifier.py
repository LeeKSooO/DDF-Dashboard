#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG App 4 - 질문 분류기 테스트
"""

from enum import Enum
from typing import Dict, List
from fuzzywuzzy import fuzz

class QuestionType(Enum):
    IRRELEVANT = "irrelevant"
    QUANTITATIVE = "quantitative" 
    QUALITATIVE = "qualitative"
    MIXED = "mixed"

class QuestionClassifier:
    """
    질문을 분류하는 클래스
    """
    
    def __init__(self, predefined_queries: Dict):
        self.predefined_queries = predefined_queries
        self.quantitative_keywords = [
            "얼마나", "몇", "수", "통계", "데이터", "평균", "총", "최대", "최소",
            "비율", "퍼센트", "%", "건수", "횟수", "개수", "명", "시간대",
            "운행", "승객", "정류장", "노선", "이용률", "효율성", "실적"
        ]
        self.qualitative_keywords = [
            "어떻게", "왜", "무엇", "방법", "이유", "장점", "단점", "특징",
            "원리", "개념", "정의", "설명", "분석", "연구", "논문", "이론",
            "사례", "예시", "비교", "차이점", "유사점", "효과", "영향"
        ]
        self.irrelevant_keywords = [
            "안녕", "날씨", "음식", "여행", "취미", "영화", "음악", "스포츠",
            "게임", "연예인", "정치", "경제일반", "주식", "부동산일반"
        ]
        
    def classify_question(self, question: str) -> QuestionType:
        """
        질문을 4가지 유형으로 분류
        """
        question_lower = question.lower()
        
        print(f"🔍 질문 분석: '{question}'")
        
        # 1. 관련없는 질문 체크
        if self._is_irrelevant(question_lower):
            print("❌ 관련없는 질문으로 분류됨")
            return QuestionType.IRRELEVANT
        
        # 2. 정량분석 가능한 질문인지 체크 (SQL 매칭)
        has_quantitative = self._has_sql_match(question) or self._contains_keywords(question_lower, self.quantitative_keywords)
        
        # 3. 정성분석이 필요한 질문인지 체크
        has_qualitative = self._contains_keywords(question_lower, self.qualitative_keywords)
        
        print(f"📊 정량분석 키워드: {has_quantitative}")
        print(f"📚 정성분석 키워드: {has_qualitative}")
        
        # 4. 분류 결정
        if has_quantitative and has_qualitative:
            print("🔄 통합분석(정량+정성) 필요")
            return QuestionType.MIXED
        elif has_quantitative:
            print("📊 정량분석 필요")
            return QuestionType.QUANTITATIVE
        elif has_qualitative:
            print("📚 정성분석 필요")
            return QuestionType.QUALITATIVE
        else:
            # 키워드가 없어도 교통/DRT 관련이면 정성분석으로 처리
            if self._is_transport_related(question_lower):
                print("🚌 교통 관련 → 정성분석으로 처리")
                return QuestionType.QUALITATIVE
            else:
                print("❌ 관련없는 질문으로 최종 분류")
                return QuestionType.IRRELEVANT
    
    def _is_irrelevant(self, question: str) -> bool:
        """관련없는 질문인지 체크"""
        return self._contains_keywords(question, self.irrelevant_keywords)
    
    def _has_sql_match(self, question: str) -> bool:
        """SQL 매칭 가능한 질문인지 체크"""
        for mapped_question in self.predefined_queries.keys():
            similarity = fuzz.token_sort_ratio(question.lower(), mapped_question.lower())
            if similarity >= 60:  # 임계값
                print(f"🎯 SQL 매칭: '{mapped_question}' (유사도: {similarity}%)")
                return True
        return False
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """키워드 포함 여부 체크"""
        found_keywords = [keyword for keyword in keywords if keyword in text]
        if found_keywords:
            print(f"🔑 발견된 키워드: {found_keywords}")
        return len(found_keywords) > 0
    
    def _is_transport_related(self, question: str) -> bool:
        """교통/DRT 관련 질문인지 체크"""
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

def test_classifier():
    """
    질문 분류기 테스트
    """
    
    # 예시 SQL 쿼리
    predefined_queries = {
        "지난달 총 운행건수는?": {
            "sql": "SELECT COUNT(*) FROM operations",
            "description": "총 운행건수"
        },
        "평균 승객수는?": {
            "sql": "SELECT AVG(passengers) FROM operations", 
            "description": "평균 승객수"
        },
        "가장 바쁜 정류장은?": {
            "sql": "SELECT station_name FROM busy_stations",
            "description": "가장 바쁜 정류장"
        }
    }
    
    classifier = QuestionClassifier(predefined_queries)
    
    test_questions = [
        # 관련없는 질문
        "안녕하세요? 오늘 날씨가 어떤가요?",
        "좋아하는 음식이 뭔가요?",
        
        # 정량분석 질문
        "지난달 운행 건수는 몇 개인가요?",
        "평균 승객 수를 알려주세요",
        "가장 바쁜 정류장은 어디인가요?",
        "시간대별 이용률은?",
        
        # 정성분석 질문  
        "DRT의 장점은 무엇인가요?",
        "수요응답형 교통이란 무엇인가요?",
        "DRT 운영 방식을 설명해주세요",
        
        # 통합분석 질문
        "지난달 승객 수와 DRT의 효과를 분석해주세요",
        "운행 실적은 어떻고 DRT의 장점은 무엇인가요?",
        
        # 애매한 질문
        "DRT 관련 정보 주세요",
        "교통 상황이 어떤가요?"
    ]
    
    print("=" * 70)
    print("🤖 질문 분류기 테스트")
    print("=" * 70)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n[테스트 {i}] {question}")
        print("-" * 50)
        
        try:
            result = classifier.classify_question(question)
            print(f"✅ 분류 결과: {result.value}")
            
        except Exception as e:
            print(f"❌ 오류: {str(e)}")
        
        print("-" * 50)

def interactive_test():
    """
    대화형 테스트
    """
    predefined_queries = {
        "지난달 총 운행건수는?": {
            "sql": "SELECT COUNT(*) FROM operations",
            "description": "총 운행건수"
        },
        "평균 승객수는?": {
            "sql": "SELECT AVG(passengers) FROM operations", 
            "description": "평균 승객수"
        }
    }
    
    classifier = QuestionClassifier(predefined_queries)
    
    print("\n" + "=" * 70)
    print("🔍 질문 분류기 대화형 테스트")
    print("=" * 70)
    print("질문을 입력하면 자동으로 분류해드립니다.")
    print("종료하려면 'quit' 또는 '종료'를 입력하세요.")
    print("=" * 70)
    
    while True:
        try:
            question = input("\n질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 테스트를 종료합니다!")
                break
            
            if not question:
                continue
            
            print("\n" + "="*50)
            result = classifier.classify_question(question)
            print(f"✅ 최종 분류: {result.value}")
            print("="*50)
            
        except KeyboardInterrupt:
            print("\n\n👋 테스트를 종료합니다!")
            break
        except Exception as e:
            print(f"\n❌ 오류: {str(e)}")

if __name__ == "__main__":
    print("🚀 질문 분류기 테스트 시작")
    
    # 자동 테스트 실행
    test_classifier()
    
    # 대화형 테스트 실행
    interactive_test()