"""
Question Classification Service for DRT RAG System
질문을 정성적/정량적/무관/혼합 유형으로 분류하는 서비스
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
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
    """DRT 도메인 특화 질문 분류 서비스"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.use_llm_classification = llm_service is not None

        # DRT 관련 키워드 패턴 정의
        self._drt_keywords = [
            'drt', '수요응답', '수요응답형', 'demand responsive', 'demand-responsive',
            '교통', '대중교통', '버스', '노선', '정류장', '승객', '운송', '모빌리티',
            '교통시스템', '교통서비스', '교통정책', '교통계획', '교통분석'
        ]

        # 정성적 질문 키워드
        self._qualitative_keywords = [
            '정의', '개념', '의미', '뜻', '무엇', '어떤', '설명', '소개',
            '장점', '단점', '이점', '효과', '혜택', '특징', '특성', '성격',
            '방법', '방식', '절차', '과정', '단계', '어떻게', '어떻게',
            '종류', '유형', '분류', '구분', '차이', '비교', '구성', '요소',
            '사례', '예시', '실제', '도입', '적용', '운영', '관리', '원리'
        ]

        # 정량적 질문 키워드
        self._quantitative_keywords = [
            '몇', '얼마', '수', '개수', '건수', '비율', '퍼센트', '%',
            '통계', '데이터', '수치', '지표', '측정', '분석', '현황', '실적',
            '증가', '감소', '변화', '추이', '경향', '패턴', '분포',
            '평균', '최대', '최소', '합계', '총', '전체', '부분',
            '시간별', '일별', '월별', '연도별', '지역별', '구별',
            '이용객', '승객', '승차', '하차', '운행', '빈도', '간격',
            '교통량', '통행량', '이용량', '승객수', '차량수', '건수',
            '조회', '확인', '검색', '찾기', '가져', '추출', '집계'
        ]

        # 혼합형 질문 키워드
        self._mixed_keywords = [
            '현황', '실태', '상황', '동향', '트렌드', '분석', '평가', '검토',
            '비교분석', '성과분석', '효과분석', '실증분석',
            '종합', '전반', '전체', '포괄', '상세', '자세'
        ]

        # 무관한 질문 패턴
        self._irrelevant_patterns = [
            r'날씨|weather|기후',
            r'음식|맛집|레스토랑|요리',
            r'영화|드라마|연예|게임|스포츠',
            r'주식|투자|금융|경제(?!.*교통)',
            r'건강|의료|병원|약',
            r'여행|관광(?!.*교통)',
            r'쇼핑|패션|화장품',
            r'정치(?!.*교통|.*정책)',
            r'hello|hi|안녕|감사|고마'
        ]

        logger.info(f"✅ Question classifier initialized (LLM-based: {self.use_llm_classification})")

    async def classify_question(self, question: str) -> ClassificationResult:
        """질문을 분류하여 유형 결정"""

        try:
            logger.info(f"🔍 Classifying question: {question[:50]}...")

            # 1. 기본 규칙 기반 분류
            rule_based_result = self._rule_based_classification(question)

            # 2. LLM 기반 분류 (옵션)
            if self.use_llm_classification:
                try:
                    llm_result = await self._llm_based_classification(question)
                    # LLM과 규칙 기반 결과 결합
                    final_result = self._combine_classification_results(rule_based_result, llm_result)
                except Exception as e:
                    logger.warning(f"LLM classification failed, using rule-based: {e}")
                    final_result = rule_based_result
            else:
                final_result = rule_based_result

            # 3. SQL/RAG 필요성 결정
            final_result.needs_sql = self._needs_sql_query(final_result.question_type)
            final_result.needs_rag = self._needs_rag_search(final_result.question_type)

            logger.info(f"✅ Question classified as: {final_result.question_type.value} (confidence: {final_result.confidence:.2f})")
            return final_result

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

    def _rule_based_classification(self, question: str) -> ClassificationResult:
        """규칙 기반 질문 분류"""

        question_lower = question.lower()
        detected_keywords = []

        # 1. 무관한 질문 체크 (우선순위 높음)
        for pattern in self._irrelevant_patterns:
            if re.search(pattern, question_lower):
                return ClassificationResult(
                    question_type=QuestionType.IRRELEVANT,
                    confidence=0.9,
                    reasoning=f"무관 패턴 감지: {pattern}",
                    keywords=[pattern],
                    needs_sql=False,
                    needs_rag=False
                )

        # 2. DRT 관련성 체크
        drt_related = any(keyword in question_lower for keyword in self._drt_keywords)
        if not drt_related:
            return ClassificationResult(
                question_type=QuestionType.IRRELEVANT,
                confidence=0.8,
                reasoning="DRT 관련 키워드 없음",
                keywords=[],
                needs_sql=False,
                needs_rag=False
            )

        # 3. 키워드별 점수 계산
        qualitative_score = 0
        quantitative_score = 0
        mixed_score = 0

        for keyword in self._qualitative_keywords:
            if keyword in question_lower:
                qualitative_score += 1
                detected_keywords.append(keyword)

        for keyword in self._quantitative_keywords:
            if keyword in question_lower:
                quantitative_score += 1
                detected_keywords.append(keyword)

        for keyword in self._mixed_keywords:
            if keyword in question_lower:
                mixed_score += 1
                detected_keywords.append(keyword)

        # 4. 패턴별 추가 점수
        # 숫자 패턴 체크 (정량적)
        if re.search(r'\d+|몇\s*개|얼마나|수치|데이터', question_lower):
            quantitative_score += 2
            detected_keywords.append("숫자패턴")

        # 정의/설명 패턴 체크 (정성적)
        if re.search(r'무엇.*인가|정의.*는|설명.*해|소개.*해', question_lower):
            qualitative_score += 2
            detected_keywords.append("정의패턴")

        # 비교분석 패턴 체크 (혼합)
        if re.search(r'분석.*해|현황.*알려|상세.*히|종합.*적', question_lower):
            mixed_score += 2
            detected_keywords.append("분석패턴")

        # 5. 최종 분류 결정
        max_score = max(qualitative_score, quantitative_score, mixed_score)

        if max_score == 0:
            # 키워드 매칭이 없으면 기본 정성적
            return ClassificationResult(
                question_type=QuestionType.QUALITATIVE,
                confidence=0.4,
                reasoning="기본값 (키워드 매칭 없음)",
                keywords=detected_keywords,
                needs_sql=False,
                needs_rag=True
            )

        # 혼합형 우선 체크
        if mixed_score > 0 and (qualitative_score > 0 or quantitative_score > 0):
            confidence = min(0.9, 0.6 + mixed_score * 0.1)
            return ClassificationResult(
                question_type=QuestionType.MIXED,
                confidence=confidence,
                reasoning=f"혼합형 키워드 감지 (정성:{qualitative_score}, 정량:{quantitative_score}, 혼합:{mixed_score})",
                keywords=detected_keywords,
                needs_sql=True,
                needs_rag=True
            )

        # 정량 vs 정성 결정
        if quantitative_score > qualitative_score:
            confidence = min(0.9, 0.6 + quantitative_score * 0.1)
            return ClassificationResult(
                question_type=QuestionType.QUANTITATIVE,
                confidence=confidence,
                reasoning=f"정량적 키워드 우세 (점수: {quantitative_score})",
                keywords=detected_keywords,
                needs_sql=True,
                needs_rag=False
            )
        else:
            confidence = min(0.9, 0.6 + qualitative_score * 0.1)
            return ClassificationResult(
                question_type=QuestionType.QUALITATIVE,
                confidence=confidence,
                reasoning=f"정성적 키워드 우세 (점수: {qualitative_score})",
                keywords=detected_keywords,
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
                        confidence = float(line.split(':', 1)[1].strip())
                        confidence = max(0.0, min(1.0, confidence))
                    except ValueError:
                        confidence = 0.5

                elif line.startswith('근거:'):
                    reasoning = line.split(':', 1)[1].strip()

                elif line.startswith('키워드:'):
                    keyword_str = line.split(':', 1)[1].strip()
                    keywords = [k.strip() for k in keyword_str.split(',') if k.strip()]

            return ClassificationResult(
                question_type=question_type,
                confidence=confidence,
                reasoning=f"LLM 분류: {reasoning}",
                keywords=keywords,
                needs_sql=False,  # 나중에 설정
                needs_rag=False   # 나중에 설정
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM classification response: {e}")
            return ClassificationResult(
                question_type=QuestionType.QUALITATIVE,
                confidence=0.3,
                reasoning="LLM 응답 파싱 실패",
                keywords=[],
                needs_sql=False,
                needs_rag=True
            )

    def _combine_classification_results(
        self,
        rule_result: ClassificationResult,
        llm_result: ClassificationResult
    ) -> ClassificationResult:
        """규칙 기반과 LLM 결과 결합"""

        # 무관한 질문의 경우 규칙 기반 우선
        if rule_result.question_type == QuestionType.IRRELEVANT:
            return rule_result

        # 신뢰도가 높은 결과 선택
        if rule_result.confidence > llm_result.confidence:
            primary = rule_result
            secondary = llm_result
        else:
            primary = llm_result
            secondary = rule_result

        # 키워드 결합
        combined_keywords = list(set(primary.keywords + secondary.keywords))

        # 평균 신뢰도 계산
        combined_confidence = (primary.confidence * 0.7 + secondary.confidence * 0.3)

        return ClassificationResult(
            question_type=primary.question_type,
            confidence=combined_confidence,
            reasoning=f"결합 분류 - 주: {primary.reasoning}, 보조: {secondary.reasoning}",
            keywords=combined_keywords,
            needs_sql=False,  # 나중에 설정
            needs_rag=False   # 나중에 설정
        )

    def _needs_sql_query(self, question_type: QuestionType) -> bool:
        """SQL 쿼리가 필요한지 판단"""
        return question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]

    def _needs_rag_search(self, question_type: QuestionType) -> bool:
        """RAG 문서 검색이 필요한지 판단"""
        return question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]

    async def health_check(self) -> bool:
        """서비스 상태 확인"""
        try:
            # 간단한 테스트 분류
            test_result = await self.classify_question("DRT가 무엇인가요?")
            return test_result.question_type == QuestionType.QUALITATIVE

        except Exception as e:
            logger.error(f"Question classifier health check failed: {e}")
            return False

    def get_classification_stats(self) -> Dict[str, Any]:
        """분류기 통계 정보"""
        return {
            "service_type": "Question Classifier",
            "supported_types": [t.value for t in QuestionType],
            "features": {
                "rule_based": True,
                "llm_based": self.use_llm_classification,
                "drt_keywords": len(self._drt_keywords),
                "qualitative_keywords": len(self._qualitative_keywords),
                "quantitative_keywords": len(self._quantitative_keywords)
            }
        }


class QuestionClassifierException(RAGServiceException):
    """질문 분류기 관련 예외"""
    pass