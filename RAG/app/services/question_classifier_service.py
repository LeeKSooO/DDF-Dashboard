"""
Question Classification Service for DRT RAG System (LLM-only version)
질문을 정성적/정량적/무관/혼합 유형으로 분류하는 서비스 (LLM 전용)
"""

import logging
import re
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

from app.services.llm_service import LLMService
from app.core.exceptions import RAGServiceException

logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """질문 유형 분류"""
    QUALITATIVE = "qualitative"     # 정성적 - 개념, 정의, 설명, 장점 등
    QUANTITATIVE = "quantitative"   # 정량적 - 수치, 통계, 데이터 요청
    IRRELEVANT = "irrelevant"       # 무관 - DRT와 관련 없는 질문
    MIXED = "mixed"                 # 혼합 - 정성적 설명 + 정량적 데이터 모두 필요


@dataclass
class ClassificationResult:
    """분류 결과 데이터 클래스"""
    question_type: QuestionType
    confidence: float  # 0.0 ~ 1.0
    reasoning: str     # 분류 근거
    keywords: List[str]  # 감지된 키워드들
    needs_sql: bool    # SQL 쿼리 필요 여부
    needs_rag: bool    # 문서 RAG 필요 여부


class QuestionClassifierService:
    """DRT 도메인 특화 질문 분류 서비스 (LLM 전용)"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        if not llm_service:
            raise ValueError("LLM service is required for question classification")

        logger.info("✅ Question classifier initialized (LLM-only mode)")

    async def classify_question(self, question: str) -> ClassificationResult:
        """질문을 분류하여 유형 결정 (LLM 전용)"""

        try:
            logger.info(f"🔍 Classifying question: {question[:50]}...")

            # LLM 기반 분류 실행
            result = await self._llm_based_classification(question)

            # SQL/RAG 필요성 결정
            result.needs_sql = self._needs_sql_query(result.question_type)
            result.needs_rag = self._needs_rag_search(result.question_type)

            logger.info(f"✅ Question classified as: {result.question_type.value} (confidence: {result.confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"❌ Question classification failed: {e}")
            # 폴백: 기본 정성적 질문으로 분류
            return ClassificationResult(
                question_type=QuestionType.QUALITATIVE,
                confidence=0.3,
                reasoning="분류 실패로 인한 기본값",
                keywords=[],
                needs_sql=False,
                needs_rag=True
            )

    async def _llm_based_classification(self, question: str) -> ClassificationResult:
        """LLM 기반 질문 분류"""

        if not self.llm_service or not self.llm_service.langchain_llm:
            raise Exception("LLM service not available")

        classification_prompt = f"""다음 질문을 DRT(수요응답형 교통) 관련 질문으로 분류해주세요.

질문: "{question}"

분류 기준:
1. QUALITATIVE (정성적): 개념, 정의, 설명, 장점, 방법 등을 묻는 질문
2. QUANTITATIVE (정량적): 수치, 통계, 데이터, 구체적인 숫자를 요구하는 질문
3. MIXED (혼합): 정성적 설명과 정량적 데이터가 모두 필요한 질문
4. IRRELEVANT (무관): DRT나 교통과 관련 없는 질문

다음 형식으로만 답변하세요:
분류: [QUALITATIVE|QUANTITATIVE|MIXED|IRRELEVANT]
신뢰도: [0.0-1.0]
근거: [분류 이유]
키워드: [감지된 키워드들]"""

        try:
            response = await self.llm_service.generate_text(classification_prompt)
            return self._parse_llm_classification_response(response)

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            raise

    def _parse_llm_classification_response(self, response: str) -> ClassificationResult:
        """LLM 분류 응답 파싱"""

        try:
            lines = response.strip().split('\n')

            # 기본값
            question_type = QuestionType.QUALITATIVE
            confidence = 0.5
            reasoning = "LLM 응답 파싱 실패"
            keywords = []

            for line in lines:
                line = line.strip()

                if line.startswith('분류:'):
                    type_str = line.split(':', 1)[1].strip().upper()
                    if type_str == 'QUALITATIVE':
                        question_type = QuestionType.QUALITATIVE
                    elif type_str == 'QUANTITATIVE':
                        question_type = QuestionType.QUANTITATIVE
                    elif type_str == 'MIXED':
                        question_type = QuestionType.MIXED
                    elif type_str == 'IRRELEVANT':
                        question_type = QuestionType.IRRELEVANT

                elif line.startswith('신뢰도:'):
                    try:
                        confidence_str = line.split(':', 1)[1].strip()
                        confidence = float(confidence_str)
                        confidence = max(0.0, min(1.0, confidence))  # 0-1 범위 제한
                    except ValueError:
                        confidence = 0.5

                elif line.startswith('근거:'):
                    reasoning = line.split(':', 1)[1].strip()

                elif line.startswith('키워드:'):
                    keywords_str = line.split(':', 1)[1].strip()
                    if keywords_str:
                        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]

            return ClassificationResult(
                question_type=question_type,
                confidence=confidence,
                reasoning=reasoning,
                keywords=keywords,
                needs_sql=False,  # 후에 설정됨
                needs_rag=False   # 후에 설정됨
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return ClassificationResult(
                question_type=QuestionType.QUALITATIVE,
                confidence=0.3,
                reasoning="LLM 응답 파싱 실패",
                keywords=[],
                needs_sql=False,
                needs_rag=True
            )

    def _needs_sql_query(self, question_type: QuestionType) -> bool:
        """질문 유형에 따른 SQL 쿼리 필요 여부 결정"""
        return question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]

    def _needs_rag_search(self, question_type: QuestionType) -> bool:
        """질문 유형에 따른 RAG 검색 필요 여부 결정"""
        return question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]

    def get_classification_stats(self) -> Dict[str, Any]:
        """분류 통계 정보 반환"""
        return {
            "classifier_type": "LLM-only",
            "supported_types": [t.value for t in QuestionType],
            "features": [
                "LLM-based classification",
                "Context-aware reasoning",
                "High accuracy classification",
                "Domain-specific knowledge"
            ]
        }