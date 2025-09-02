import os
import logging
import shutil
import pandas as pd
import json
import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List, Tuple, Any
from fuzzywuzzy import fuzz
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

# =============================================================================
# 환경 설정 및 초기화
# =============================================================================

load_dotenv(override=True)

# =============================================================================
# Enums 정의
# =============================================================================

class QuestionType(Enum):
    IRRELEVANT = "irrelevant"
    QUANTITATIVE = "quantitative" 
    QUALITATIVE = "qualitative"
    MIXED = "mixed"

try:
    from langchain_chroma import Chroma
    print("🔧 새로운 langchain-chroma 패키지를 사용합니다.")
except ImportError:
    from langchain_community.vectorstores import Chroma
    print("⚠️ 기존 chroma 패키지를 사용합니다. 업그레이드를 권장합니다: pip install -U langchain-chroma")

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# =============================================================================
# Watson AI 연결 설정
# =============================================================================

credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    api_key=os.getenv("WATSONX_APIKEY"),
)
project_id = os.getenv("WATSONX_PROJECT_ID")

# =============================================================================
# AI 모델 설정
# =============================================================================

EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
CHAT_MODEL = "ibm/granite-3-8b-instruct"

# =============================================================================
# 데이터베이스 연결 설정
# =============================================================================

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ddf_db',
    'user': 'ddf_user',
    'password': 'ddf_password'
}

# =============================================================================
# CoT 향상된 Watson AI LLM 래퍼 클래스
# =============================================================================

class CoTEnhancedWatsonXLLM(LLM):
    """
    CoT(Chain of Thought) 기능이 강화된 Watson AI LLM 래퍼
    
    주요 개선사항:
    - 단계별 추론 과정 명시적 구조화
    - DRT 도메인 특화 추론 체인 지원
    - 중간 추론 단계 추적 및 검증 기능
    """
    
    model: Any = None
    enable_cot: bool = True
    reasoning_steps: List[str] = []
    
    def __init__(self, enable_cot: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.enable_cot = enable_cot
        self.reasoning_steps = []
        
        parameters = {
            "decoding_method": "greedy",
            "min_new_tokens": 10,
            "max_new_tokens": 2000,
            "temperature": 0.1 if enable_cot else 0.3  # CoT 모드에서는 더 일관성 있는 추론
        }
        
        self.model = ModelInference(
            model_id=CHAT_MODEL,
            params=parameters,
            credentials=credentials,
            project_id=project_id
        )
    
    @property
    def _llm_type(self) -> str:
        return "cot_enhanced_watson_x"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, 
              run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        """
        CoT 기능이 향상된 Watson AI 모델 호출
        
        Args:
            prompt (str): 입력 프롬프트 (CoT 구조 포함)
            
        Returns:
            str: 단계별 추론 과정이 포함된 응답
        """
        try:
            if self.enable_cot and "단계별" not in prompt and "step-by-step" not in prompt:
                # CoT 프롬프트 자동 개선
                prompt = self._enhance_prompt_with_cot(prompt)
            
            print("🧠 CoT 기반 Watson AI 추론 시작...")
            response = self.model.generate_text(prompt=prompt)
            
            if self.enable_cot:
                self._extract_reasoning_steps(response)
                
            return response
            
        except Exception as e:
            print(f"⚠️ CoT Watson AI 오류: {str(e)}")
            return "죄송합니다. CoT 추론 중 오류가 발생했습니다."
    
    def _enhance_prompt_with_cot(self, prompt: str) -> str:
        """
        일반 프롬프트를 CoT 구조로 개선
        
        DRT 도메인에 특화된 CoT 가이드라인:
        1. 문제 이해 단계
        2. 관련 정보 분석 단계  
        3. 논리적 추론 단계
        4. 결론 도출 단계
        """
        cot_prefix = """DRT(수요응답형 교통) 전문가로서 다음과 같이 단계별로 분석해주세요:

🔍 1단계: 문제 파악
- 질문의 핵심 요소를 명확히 파악합니다
- DRT 시스템의 어떤 측면과 관련되는지 식별합니다

📊 2단계: 정보 분석  
- 제공된 데이터나 문서 내용을 체계적으로 검토합니다
- 관련 DRT 이론이나 운영 원칙을 고려합니다

🧠 3단계: 논리적 추론
- 단계적으로 논리를 전개합니다
- 각 추론 단계의 근거를 명시합니다

✅ 4단계: 결론 도출
- 앞선 분석을 종합하여 최종 답변을 구성합니다
- 답변의 신뢰도와 한계점을 언급합니다

이제 다음 질문에 대해 위 단계를 따라 분석해주세요:

"""
        return cot_prefix + prompt
    
    def _extract_reasoning_steps(self, response: str) -> None:
        """응답에서 추론 단계를 추출하여 저장"""
        self.reasoning_steps = []
        if "1단계:" in response:
            steps = response.split("단계:")
            for i, step in enumerate(steps[1:], 1):
                clean_step = step.split("🔍�📊🧠✅")[0].strip()
                if clean_step:
                    self.reasoning_steps.append(f"단계{i}: {clean_step[:100]}...")
    
    def get_reasoning_steps(self) -> List[str]:
        """추론 단계 반환"""
        return self.reasoning_steps.copy()

# =============================================================================
# CoT 강화된 질문 분류 시스템
# =============================================================================

class CoTQuestionClassifier:
    """
    CoT 기법을 적용한 질문 분류기
    
    주요 개선사항:
    - 분류 과정에서의 단계별 추론 로직 명시
    - 각 분류 결정에 대한 근거 제시
    - 불확실한 경우에 대한 추론 체인 제공
    """
    
    def __init__(self, predefined_queries: Dict, llm: CoTEnhancedWatsonXLLM):
        self.predefined_queries = predefined_queries
        self.llm = llm
        
        # 기존 키워드 기반 분류는 유지
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

    def classify_question_with_cot(self, question: str) -> Tuple[QuestionType, str]:
        """
        CoT를 활용한 질문 분류 및 추론 과정 제공
        
        Returns:
            Tuple[QuestionType, str]: (분류 결과, 추론 과정)
        """
        # 기본 키워드 기반 분류 수행
        basic_classification = self._basic_classify(question)
        
        # 애매한 경우에만 CoT 적용하여 정밀 분류
        if basic_classification == "uncertain":
            return self._cot_classify(question)
        
        return basic_classification, f"키워드 기반으로 {basic_classification.value}로 분류되었습니다."
    
    def _basic_classify(self, question: str) -> QuestionType:
        """기존 키워드 기반 분류 (빠른 분류)"""
        question_lower = question.lower()
        
        if self._contains_keywords(question_lower, self.irrelevant_keywords):
            return QuestionType.IRRELEVANT
        
        has_quantitative = (self._has_sql_match(question) or 
                           self._contains_keywords(question_lower, self.quantitative_keywords))
        has_qualitative = self._contains_keywords(question_lower, self.qualitative_keywords)
        
        if has_quantitative and has_qualitative:
            return QuestionType.MIXED
        elif has_quantitative:
            return QuestionType.QUANTITATIVE
        elif has_qualitative:
            return QuestionType.QUALITATIVE
        elif self._is_transport_related(question_lower):
            return QuestionType.QUALITATIVE
        else:
            return "uncertain"  # CoT 분류 필요
    
    def _cot_classify(self, question: str) -> Tuple[QuestionType, str]:
        """
        CoT를 활용한 정밀 질문 분류
        
        애매한 경우나 복잡한 질문에 대해 단계별 추론으로 정확한 분류 수행
        """
        cot_prompt = f"""
DRT 전문가로서 다음 질문의 유형을 단계별로 분석해주세요:

질문: "{question}"

🔍 1단계: 질문 구성 요소 분석
- 질문에서 요구하는 정보의 성격을 파악합니다
- 숫자나 데이터를 요구하는지 (정량분석)
- 개념이나 설명을 요구하는지 (정성분석)
- DRT/교통과 관련이 있는지 확인합니다

📊 2단계: DRT 관련성 평가
- 수요응답형 교통, 대중교통, 모빌리티 관련 키워드 식별
- 교통 시스템 운영, 승객 서비스, 노선 관리 등과의 연관성 확인

🧠 3단계: 분석 유형 결정
- IRRELEVANT: DRT/교통과 무관한 질문
- QUANTITATIVE: 수치, 통계, 데이터 분석이 주목적
- QUALITATIVE: 개념, 이론, 방법론 설명이 주목적  
- MIXED: 정량+정성 분석이 모두 필요

✅ 4단계: 최종 분류
분류 결과: [IRRELEVANT/QUANTITATIVE/QUALITATIVE/MIXED]
근거: [구체적인 판단 근거 제시]
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            classification, reasoning = self._extract_classification_result(response)
            return classification, reasoning
        except Exception as e:
            print(f"⚠️ CoT 분류 오류: {e}")
            return QuestionType.QUALITATIVE, "CoT 분류 실패로 기본값 사용"
    
    def _extract_classification_result(self, response: str) -> Tuple[QuestionType, str]:
        """CoT 응답에서 분류 결과 추출"""
        response_upper = response.upper()
        
        if "IRRELEVANT" in response_upper:
            classification = QuestionType.IRRELEVANT
        elif "MIXED" in response_upper:
            classification = QuestionType.MIXED
        elif "QUANTITATIVE" in response_upper:
            classification = QuestionType.QUANTITATIVE
        elif "QUALITATIVE" in response_upper:
            classification = QuestionType.QUALITATIVE
        else:
            classification = QuestionType.QUALITATIVE  # 기본값
            
        return classification, response
    
    # 기존 헬퍼 메서드들은 그대로 유지
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)
    
    def _has_sql_match(self, question: str) -> bool:
        for mapped_question in self.predefined_queries.keys():
            similarity = fuzz.token_sort_ratio(question.lower(), mapped_question.lower())
            if similarity >= 60:
                return True
        return False
    
    def _is_transport_related(self, question: str) -> bool:
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

# =============================================================================
# CoT 강화된 정량 분석기
# =============================================================================

class CoTQuantitativeAnalyzer:
    """
    CoT 추론이 강화된 정량 분석기
    
    주요 개선사항:
    - SQL 쿼리 선택 과정의 단계별 추론
    - 데이터 분석 결과에 대한 해석 추론 체인
    - 오류 상황에서의 진단 추론
    """
    
    def __init__(self, db_config: Dict, predefined_queries: Dict, llm: CoTEnhancedWatsonXLLM):
        self.db_config = db_config
        self.predefined_queries = predefined_queries
        self.llm = llm
        self.engine = self._create_connection()
    
    def analyze_with_cot(self, question: str) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict], str]:
        """
        CoT를 활용한 정량 분석
        
        Returns:
            Tuple: (데이터, 에러, SQL정보, 추론과정)
        """
        if not self.engine:
            return None, "데이터베이스 연결이 없습니다.", None, "DB 연결 실패"
        
        # SQL 매칭을 CoT로 수행
        best_match, reasoning = self._find_best_sql_match_with_cot(question)
        
        if not best_match:
            return None, "매칭되는 SQL 쿼리를 찾을 수 없습니다.", None, reasoning
        
        print(f"📊 CoT 기반 데이터 조회 중...")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(best_match['sql']))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    return None, "조회 결과가 없습니다.", best_match, reasoning
                
                # 데이터 분석 결과에 대한 CoT 해석
                interpretation = self._interpret_data_with_cot(question, df, best_match)
                
                print(f"✅ CoT SQL 실행 성공 - {len(df)}행 {len(df.columns)}열 데이터 조회")
                return df, None, best_match, f"{reasoning}\n\n{interpretation}"
                
        except Exception as e:
            error_msg = f"SQL 실행 오류: {str(e)}"
            error_analysis = self._analyze_error_with_cot(question, best_match, str(e))
            print(f"⚠️ {error_msg}")
            return None, error_msg, best_match, f"{reasoning}\n\n{error_analysis}"
    
    def _find_best_sql_match_with_cot(self, question: str) -> Tuple[Optional[Dict], str]:
        """CoT를 활용한 SQL 쿼리 매칭"""
        
        # 기본 fuzzy matching 수행
        best_match = None
        best_score = 0
        
        for mapped_question, sql_info in self.predefined_queries.items():
            similarity_scores = [
                fuzz.ratio(question.lower(), mapped_question.lower()),
                fuzz.partial_ratio(question.lower(), mapped_question.lower()),
                fuzz.token_sort_ratio(question.lower(), mapped_question.lower())
            ]
            score = max(similarity_scores)
            
            if score > best_score and score >= 60:
                best_score = score
                best_match = {
                    'question': mapped_question,
                    'sql': sql_info['sql'],
                    'description': sql_info['description'],
                    'confidence': score
                }
        
        if best_match and best_score >= 80:
            reasoning = f"높은 유사도({best_score}%)로 SQL 쿼리 매칭 성공: {best_match['question']}"
            return best_match, reasoning
        elif best_match:
            # 중간 유사도에 대해 CoT 검증 수행
            return self._verify_sql_match_with_cot(question, best_match)
        else:
            reasoning = "기존 SQL 쿼리와 충분한 유사도를 찾지 못했습니다."
            return None, reasoning
    
    def _verify_sql_match_with_cot(self, question: str, candidate_match: Dict) -> Tuple[Optional[Dict], str]:
        """애매한 SQL 매칭에 대한 CoT 검증"""
        
        cot_prompt = f"""
DRT 데이터 분석 전문가로서 다음 질문과 SQL 쿼리의 적합성을 단계별로 분석해주세요:

사용자 질문: "{question}"
후보 SQL 쿼리: "{candidate_match['question']}"
유사도: {candidate_match['confidence']}%
쿼리 설명: {candidate_match['description']}

🔍 1단계: 질문 의도 파악
- 사용자가 원하는 정보의 핵심을 파악합니다

📊 2단계: SQL 쿼리 분석
- 후보 쿼리가 제공하는 데이터의 종류를 분석합니다
- 쿼리의 목적과 결과물을 평가합니다

🧠 3단계: 적합성 판단
- 질문 의도와 쿼리 결과의 일치도를 평가합니다
- 데이터가 질문에 답하기에 충분한지 판단합니다

✅ 4단계: 최종 결정
매칭 적합성: [GOOD/PARTIAL/POOR]
사용 권장도: [RECOMMEND/CAUTION/NOT_RECOMMEND]
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            
            if "RECOMMEND" in response.upper() or "GOOD" in response.upper():
                return candidate_match, f"CoT 검증 결과 SQL 매칭 승인:\n{response}"
            elif "CAUTION" in response.upper() or "PARTIAL" in response.upper():
                return candidate_match, f"CoT 검증 결과 조건부 승인:\n{response}"
            else:
                return None, f"CoT 검증 결과 SQL 매칭 거부:\n{response}"
                
        except Exception as e:
            return candidate_match, f"CoT 검증 실패, 기본 매칭 사용: {str(e)}"
    
    def _interpret_data_with_cot(self, question: str, data: pd.DataFrame, sql_info: Dict) -> str:
        """데이터 분석 결과에 대한 CoT 해석"""
        
        # 데이터 요약 생성
        data_summary = self._create_data_summary(data)
        
        cot_prompt = f"""
DRT 데이터 분석 전문가로서 다음 분석 결과를 단계별로 해석해주세요:

원래 질문: "{question}"
실행된 쿼리: {sql_info['description']}
데이터 요약: {data_summary}

🔍 1단계: 데이터 검토
- 조회된 데이터의 특성과 규모를 파악합니다
- 데이터 품질과 완성도를 평가합니다

📊 2단계: 핵심 지표 식별
- 질문과 관련된 주요 수치를 식별합니다
- 특이사항이나 주목할 만한 패턴을 찾습니다

🧠 3단계: DRT 관점 분석
- DRT 운영 관점에서 데이터의 의미를 해석합니다
- 교통 서비스 품질과의 연관성을 분석합니다

✅ 4단계: 결론 및 시사점
- 질문에 대한 직접적인 답변을 구성합니다
- 추가적인 분석이나 고려사항을 제시합니다

간단한 해석 (3-4문장):
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            return f"📈 CoT 데이터 해석:\n{response}"
        except Exception as e:
            return f"📈 기본 데이터 해석: {data_summary}"
    
    def _analyze_error_with_cot(self, question: str, sql_info: Dict, error: str) -> str:
        """오류 상황에 대한 CoT 분석"""
        
        cot_prompt = f"""
DRT 데이터베이스 관리자로서 다음 오류를 단계별로 분석해주세요:

질문: "{question}"
실행 시도된 SQL: {sql_info.get('description', 'Unknown')}
오류 메시지: {error}

🔍 1단계: 오류 유형 분류
- SQL 문법 오류, 테이블 접근 오류, 데이터 타입 오류 등을 구분합니다

📊 2단계: 원인 분석
- 오류가 발생한 구체적인 원인을 추정합니다
- 데이터베이스 스키마나 권한 문제 가능성을 검토합니다

🧠 3단계: 해결 방안 제시
- 즉시 적용 가능한 해결책을 제안합니다
- 근본적인 시스템 개선 방안을 고려합니다

✅ 4단계: 사용자 안내
사용자에게 제공할 오류 해석 및 대안을 제시합니다.

간단한 오류 분석:
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            return f"🔧 CoT 오류 분석:\n{response}"
        except Exception as e:
            return f"🔧 기본 오류 분석: {error}"
    
    def _create_data_summary(self, data: pd.DataFrame) -> str:
        """데이터 간단 요약 생성"""
        if data.empty:
            return "데이터 없음"
        
        summary_parts = [f"행수: {len(data)}", f"열수: {len(data.columns)}"]
        
        # 수치 데이터가 있는 경우 기본 통계
        numeric_cols = data.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            for col in numeric_cols[:2]:  # 최대 2개 열만
                val = data[col].iloc[0] if len(data) > 0 else 0
                if pd.notna(val):
                    summary_parts.append(f"{col}: {val}")
        
        return ", ".join(summary_parts)
    
    def _create_connection(self):
        """기존 DB 연결 로직 유지"""
        try:
            connection_string = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            )
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("✅ PostgreSQL 연결 성공!")
            return engine
        except Exception as e:
            print(f"⚠️ 데이터베이스 연결 실패: {str(e)}")
            return None

# =============================================================================
# CoT 강화된 정성 분석기 (기존 QualitativeAnalyzer 개선)
# =============================================================================

class CoTQualitativeAnalyzer:
    """
    CoT가 향상된 정성 분석기
    
    기존 RAG 시스템에 더 구조화된 CoT 추론 과정 도입
    """
    
    def __init__(self, llm: CoTEnhancedWatsonXLLM):
        self.llm = llm
        self.rag_chain = None
        self.vectorstore = None
        self.processed_files_path = "./processed_files.json"
        self.processed_files_info = self._load_processed_files()
    
    def analyze_with_cot(self, question: str) -> Tuple[str, str]:
        """
        CoT가 강화된 정성 분석
        
        Returns:
            Tuple[str, str]: (답변, 추론과정)
        """
        if not self.rag_chain:
            return "정성분석 시스템이 초기화되지 않았습니다.", "시스템 오류"
        
        try:
            # RAG 체인에 CoT 구조 적용
            answer = self.rag_chain.invoke(question)
            reasoning_steps = self.llm.get_reasoning_steps()
            
            if hasattr(answer, 'content'):
                return answer.content, "\n".join(reasoning_steps)
            return str(answer), "\n".join(reasoning_steps)
        except Exception as e:
            return f"정성분석 오류: {str(e)}", f"오류 발생: {str(e)}"
    
    def initialize(self, papers_dir: str = "./papers/") -> bool:
        """RAG 시스템 초기화 (기존 로직 + CoT 프롬프트 개선)"""
        print("📚 CoT 강화 정성분석용 RAG 시스템 초기화 중...")
        
        if not self._validate_papers_directory(papers_dir):
            return False
        
        vectorstore_path = f"./chroma_db_watson_{EMBEDDING_MODEL.replace('/', '_').replace('-', '_')}"
        
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cuda'},
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 64}
        )
        
        existing_vectorstore_exists = os.path.exists(vectorstore_path)
        
        if existing_vectorstore_exists:
            try:
                self.vectorstore = Chroma(
                    persist_directory=vectorstore_path,
                    embedding_function=embeddings
                )
                print("✅ 기존 벡터 데이터베이스 로드 성공")
                
                new_or_changed_docs = self._get_new_or_changed_documents(papers_dir)
                if new_or_changed_docs:
                    print(f"📄 새로운/변경된 문서 {len(new_or_changed_docs)}개 발견 - 벡터 데이터베이스 업데이트 중...")
                    self._add_documents_to_vectorstore(new_or_changed_docs)
                
            except Exception as e:
                print(f"⚠️ 기존 벡터 데이터베이스 로드 실패: {e}")
                existing_vectorstore_exists = False
        
        if not existing_vectorstore_exists:
            docs = self._load_documents(papers_dir)
            if not docs:
                print("⚠️ 문서를 로드할 수 없습니다.")
                return False
            
            print(f"📄 총 {len(docs)}개 문서를 벡터 데이터베이스로 변환 중...")
            splits = self._split_documents(docs)
            
            if os.path.exists(vectorstore_path):
                shutil.rmtree(vectorstore_path)
            
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=vectorstore_path
            )
        
        self._save_processed_files()
        
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}
        )
        
        # CoT가 강화된 프롬프트 템플릿
        cot_prompt = PromptTemplate(
            template="""당신은 DRT(수요응답형 교통) 전문 분석가입니다.

다음과 같이 단계별로 분석하여 답변해주세요:

🔍 1단계: 질문 이해
질문에서 요구하는 정보의 핵심을 파악하고, DRT 시스템의 어떤 측면과 관련되는지 식별합니다.

📚 2단계: 문헌 검토  
제공된 참고자료를 체계적으로 검토하고, 질문과 관련된 핵심 정보를 추출합니다.

🧠 3단계: 전문적 분석
DRT 이론과 실무 경험을 바탕으로 단계적 논리를 전개하며, 각 추론의 근거를 명시합니다.

✅ 4단계: 종합 답변
앞선 분석을 종합하여 구체적이고 실용적인 답변을 제공하며, 필요시 추가 고려사항을 언급합니다.

예시 분석:
질문: DRT의 장점은 무엇인가요?

🔍 1단계: 질문 이해 → DRT 시스템의 고유 장점과 기존 교통수단 대비 우위점 파악 필요

📚 2단계: 문헌 검토 → 문헌에서 "문전수송 서비스"와 "운행 효율성" 언급 확인

🧠 3단계: 전문적 분석 → 
- 승객 관점: 문전수송으로 편의성 향상
- 운영 관점: 수요 기반 최적화로 효율성 증대  
- 사회적 관점: 교통소외지역 접근성 개선

✅ 4단계: 종합 답변 → DRT의 주요 장점은 개인 맞춤형 이동서비스 제공, 운영 효율성 향상, 교통 형평성 개선입니다.

이제 다음 질문에 대해 위 단계를 따라 분석해주세요:

질문: {question}
참고자료:
{context}

단계별 분석:""",
            input_variables=["question", "context"]
        )
        
        def format_docs(docs):
            context = "\n\n---\n\n".join([
                f"[문서 {i+1}]\n{doc.page_content}"
                for i, doc in enumerate(docs)
            ])
            print(f"📚 {len(docs)}개 문서 참조")
            return context
        
        # CoT 강화된 RAG 체인 구성
        self.rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | cot_prompt
            | self.llm
            | StrOutputParser()
        )
        
        print("🧠 CoT 강화 RAG 체인 파이프라인 구성 완료")
        print("✅ CoT 정성분석 RAG 시스템 준비 완료!")
        return True
    
    # 나머지 메서드들은 기존과 동일하게 유지
    def _load_processed_files(self) -> Dict:
        try:
            if os.path.exists(self.processed_files_path):
                with open(self.processed_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 로드 실패: {e}")
        return {}
    
    def _save_processed_files(self):
        try:
            with open(self.processed_files_path, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 저장 실패: {e}")
    
    def _validate_papers_directory(self, papers_dir: str) -> bool:
        abs_path = os.path.abspath(papers_dir)
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            print(f"⚠️ Papers 디렉터리가 존재하지 않습니다: {abs_path}")
            return False
        
        pdf_count = sum(1 for root, dirs, files in os.walk(abs_path) 
                       for file in files if file.lower().endswith('.pdf'))
        if pdf_count == 0:
            print(f"⚠️ Papers 디렉터리에 PDF 파일이 없습니다: {abs_path}")
            return False
        
        print(f"✅ Papers 디렉터리 검증 완료 - {pdf_count}개 PDF 파일 발견")
        return True
    
    def _get_new_or_changed_documents(self, directory_path: str) -> List:
        new_or_changed_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    filepath = os.path.join(root, file)
                    if self._is_file_changed(filepath):
                        new_or_changed_files.append(filepath)
        return new_or_changed_files
    
    def _is_file_changed(self, filepath: str) -> bool:
        filename = os.path.basename(filepath)
        current_hash = self._get_file_hash(filepath)
        
        if filename not in self.processed_files_info:
            return True
        
        stored_hash = self.processed_files_info[filename].get('hash', '')
        return current_hash != stored_hash
    
    def _get_file_hash(self, filepath: str) -> str:
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _add_documents_to_vectorstore(self, new_files: List[str]):
        if not new_files:
            return
        
        new_docs = []
        for filepath in new_files:
            docs = self._load_single_document(filepath)
            if docs:
                new_docs.extend(docs)
                self._update_processed_file_info(filepath, len(docs))
        
        if new_docs:
            splits = self._split_documents(new_docs)
            self.vectorstore.add_documents(splits)
            print(f"✅ {len(splits)}개 새 청크를 벡터 데이터베이스에 추가 완료")
    
    def _update_processed_file_info(self, filepath: str, doc_count: int):
        filename = os.path.basename(filepath)
        self.processed_files_info[filename] = {
            'hash': self._get_file_hash(filepath),
            'processed_date': datetime.now().isoformat(),
            'document_count': doc_count,
            'file_size': os.path.getsize(filepath)
        }
    
    def _split_documents(self, docs: List) -> List:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""]
        )
        return text_splitter.split_documents(docs)
    
    def _load_single_document(self, filepath: str) -> List:
        docs = []
        filename = os.path.basename(filepath)
        
        try:
            loader = PyMuPDFLoader(filepath)
            docs = loader.load()
            print(f"✅ PyMuPDF로 로드 성공: {filename} ({len(docs)}페이지)")
            return docs
        except Exception as e:
            print(f"⚠️ PyMuPDF 로드 실패: {filename} - {str(e)}")
        
        try:
            loader = PyPDFLoader(filepath)
            docs = loader.load()
            print(f"✅ PyPDF로 로드 성공: {filename} ({len(docs)}페이지)")
            return docs
        except Exception as e:
            print(f"⚠️ 모든 로더 실패: {filename} - {str(e)}")
        
        return []
    
    def _load_documents(self, directory_path: str) -> List:
        all_docs = []
        pdf_files = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"📚 총 {len(pdf_files)}개의 PDF 파일을 발견했습니다.")
        
        successful_loads = 0
        for pdf_path in pdf_files:
            docs = self._load_single_document(pdf_path)
            if docs:
                all_docs.extend(docs)
                successful_loads += 1
                self._update_processed_file_info(pdf_path, len(docs))
        
        print(f"📊 로드 결과: {successful_loads}/{len(pdf_files)}개 파일 성공, 총 {len(all_docs)}개 문서")
        return all_docs

# =============================================================================
# CoT 강화된 응답 생성기
# =============================================================================

class CoTResponseGenerator:
    """
    CoT 추론이 강화된 최종 응답 생성기
    
    주요 개선사항:
    - 각 응답 유형별 단계별 추론 과정 포함
    - 정량+정성 데이터 통합 시 논리적 연결 과정 명시
    - 불확실성이나 한계점에 대한 투명한 언급
    """
    
    def __init__(self, llm: CoTEnhancedWatsonXLLM):
        self.llm = llm
    
    def generate_final_response_with_cot(self, question: str, question_type: QuestionType,
                                       quantitative_data: Optional[pd.DataFrame] = None,
                                       quantitative_reasoning: Optional[str] = None,
                                       qualitative_answer: Optional[str] = None,
                                       qualitative_reasoning: Optional[str] = None,
                                       sql_info: Optional[Dict] = None) -> Tuple[str, str]:
        """
        CoT가 강화된 최종 응답 생성
        
        Returns:
            Tuple[str, str]: (최종답변, 전체추론과정)
        """
        
        if question_type == QuestionType.IRRELEVANT:
            return self._generate_irrelevant_response()
        
        elif question_type == QuestionType.QUANTITATIVE:
            return self._generate_quantitative_response_with_cot(
                question, quantitative_data, quantitative_reasoning, sql_info)
        
        elif question_type == QuestionType.QUALITATIVE:
            return self._generate_qualitative_response_with_cot(
                question, qualitative_answer, qualitative_reasoning)
        
        elif question_type == QuestionType.MIXED:
            return self._generate_mixed_response_with_cot(
                question, quantitative_data, quantitative_reasoning,
                qualitative_answer, qualitative_reasoning, sql_info)
        
        else:
            return "죄송합니다. 질문을 처리할 수 없습니다.", "분류 오류 발생"
    
    def _generate_quantitative_response_with_cot(self, question: str, data: Optional[pd.DataFrame], 
                                               reasoning: Optional[str], sql_info: Optional[Dict]) -> Tuple[str, str]:
        """정량분석 결과의 CoT 기반 응답 생성"""
        
        if data is None or data.empty:
            return "요청하신 데이터를 조회할 수 없습니다.", reasoning or "데이터 없음"
        
        formatted_data = self._format_dataframe_simple(data)
        
        cot_prompt = f"""
DRT 데이터 분석 전문가로서 다음 정량분석 결과를 단계별로 해석하여 답변해주세요:

질문: "{question}"
분석된 데이터: {formatted_data}
분석 과정: {reasoning or "기본 분석"}

🔍 1단계: 데이터 검증
- 조회된 데이터가 질문에 적합한지 확인합니다
- 데이터의 신뢰성과 완성도를 평가합니다

📊 2단계: 핵심 수치 해석
- 질문과 직접 관련된 주요 수치를 식별합니다
- DRT 운영 관점에서 수치의 의미를 해석합니다

🧠 3단계: 맥락적 분석
- 수치가 DRT 서비스 품질에 미치는 영향을 분석합니다
- 업계 표준이나 목표 대비 수준을 평가합니다

✅ 4단계: 결론 및 권고
- 명확하고 구체적인 답변을 구성합니다
- 필요시 추가 분석이나 개선 방향을 제시합니다

최종 답변 (간단명료하게):
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            full_reasoning = f"📊 정량분석 추론과정:\n{reasoning}\n\n🧠 CoT 해석과정:\n{response}"
            
            # 응답에서 "최종 답변" 부분만 추출하여 간단한 답변 생성
            if "최종 답변" in response:
                final_answer = response.split("최종 답변")[-1].strip().strip(":")
            else:
                final_answer = response.strip()
                
            return final_answer, full_reasoning
            
        except Exception as e:
            simple_answer = f"데이터 조회 결과: {formatted_data}"
            return simple_answer, reasoning or "기본 분석"
    
    def _generate_qualitative_response_with_cot(self, question: str, qualitative_answer: Optional[str], 
                                              reasoning: Optional[str]) -> Tuple[str, str]:
        """정성분석 결과의 CoT 기반 응답 생성"""
        
        if not qualitative_answer:
            return "정성적 분석 결과를 가져올 수 없습니다.", reasoning or "분석 실패"
        
        # 이미 RAG에서 CoT가 적용되었으므로, 추가 요약이나 정제만 수행
        if len(qualitative_answer.strip()) < 500:
            return qualitative_answer.strip(), reasoning or "RAG 분석 완료"
        
        # 긴 답변의 경우 핵심 요약
        summary_prompt = f"""
다음 DRT 분석 내용을 3-4문장으로 핵심만 간추려 주세요:

{qualitative_answer}

핵심 요약:
"""
        
        try:
            summary = self.llm.invoke(summary_prompt)
            full_reasoning = f"📚 정성분석 추론과정:\n{reasoning}\n\n🧠 원문 분석:\n{qualitative_answer[:200]}..."
            
            if len(summary) < len(qualitative_answer):
                return summary.strip(), full_reasoning
            else:
                return qualitative_answer.strip(), reasoning or "정성분석 완료"
                
        except Exception as e:
            return qualitative_answer.strip(), reasoning or "정성분석 완료"
    
    def _generate_mixed_response_with_cot(self, question: str, 
                                        quantitative_data: Optional[pd.DataFrame],
                                        quantitative_reasoning: Optional[str],
                                        qualitative_answer: Optional[str],
                                        qualitative_reasoning: Optional[str],
                                        sql_info: Optional[Dict]) -> Tuple[str, str]:
        """통합분석 결과의 CoT 기반 응답 생성"""
        
        data_text = ""
        if quantitative_data is not None and not quantitative_data.empty:
            data_text = self._format_dataframe_simple(quantitative_data)
        
        cot_prompt = f"""
DRT 통합분석 전문가로서 정량데이터와 정성분석을 단계별로 결합하여 종합답변을 구성해주세요:

질문: "{question}"

정량분석 결과: {data_text or "정량데이터 없음"}
정성분석 결과: {qualitative_answer or "정성분석 없음"}

🔍 1단계: 정보 통합성 검토
- 정량데이터와 정성분석이 일관된 방향을 제시하는지 확인합니다
- 상충되는 부분이 있다면 그 원인을 파악합니다

📊 2단계: 상호보완 분석
- 정량데이터로 뒷받침되는 정성적 주장을 식별합니다  
- 정성분석으로 해석되는 정량적 패턴을 찾습니다

🧠 3단계: 종합적 해석
- 양쪽 분석을 결합한 더 깊은 인사이트를 도출합니다
- DRT 운영과 정책에 미치는 실질적 함의를 분석합니다

✅ 4단계: 통합 결론
- 정량과 정성 분석을 자연스럽게 연결한 종합답변을 구성합니다
- 분석의 한계점과 추가 고려사항을 언급합니다

통합 답변:
"""
        
        try:
            response = self.llm.invoke(cot_prompt)
            full_reasoning = f"""
🔄 통합분석 추론과정:

📊 정량분석:
{quantitative_reasoning or "정량분석 없음"}

📚 정성분석:  
{qualitative_reasoning or "정성분석 없음"}

🧠 CoT 통합과정:
{response}
"""
            
            # 통합 답변 부분 추출
            if "통합 답변" in response:
                final_answer = response.split("통합 답변")[-1].strip().strip(":")
            else:
                final_answer = response.strip()
                
            return final_answer, full_reasoning
            
        except Exception as e:
            # 기본 통합 답변 생성
            result_parts = []
            if data_text:
                result_parts.append(f"정량분석: {data_text}")
            if qualitative_answer:
                result_parts.append(f"정성분석: {qualitative_answer[:100]}...")
            
            basic_answer = "\n\n".join(result_parts)
            basic_reasoning = f"정량: {quantitative_reasoning}\n정성: {qualitative_reasoning}"
            
            return basic_answer, basic_reasoning
    
    def _generate_irrelevant_response(self) -> Tuple[str, str]:
        """관련없는 질문에 대한 응답"""
        response = """죄송합니다. 저는 DRT(수요응답형 교통) 및 교통 시스템 분야 전문 분석 어시스턴트입니다.

교통, DRT, 모빌리티, 대중교통 관련 질문을 해주시면 정량적 데이터 분석과 정성적 연구 자료를 바탕으로 전문적인 답변을 드리겠습니다.

예시 질문:
- 지난달 운행 건수는?
- DRT의 장점은 무엇인가요?
- 수요응답형 교통 시스템은 어떻게 작동하나요?"""
        
        reasoning = "질문 분류 결과: 교통/DRT와 관련 없는 질문으로 판단되어 안내 메시지를 제공합니다."
        
        return response, reasoning
    
    def _format_dataframe_simple(self, df: pd.DataFrame) -> str:
        """DataFrame을 간단한 형태로 변환"""
        if df.empty:
            return "데이터 없음"
        
        if len(df) == 1:
            row = df.iloc[0]
            items = []
            for col, val in row.items():
                if pd.notna(val):
                    if isinstance(val, (int, float)):
                        val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                    items.append(f"{col}: {val}")
            return ", ".join(items[:3])
        else:
            return df.head(3).to_string(index=False)

# =============================================================================
# CoT 통합 스마트 RAG 시스템
# =============================================================================

class CoTSmartRAGSystem:
    """
    CoT(Chain of Thought) 추론이 통합된 스마트 RAG 시스템
    
    주요 특징:
    - 질문 분류부터 최종 답변까지 전 과정에 CoT 적용
    - 각 분석 단계별 추론 과정 추적 및 제공  
    - DRT 도메인 특화 단계별 추론 구조
    - 투명하고 해석 가능한 AI 시스템
    """
    
    def __init__(self, papers_dir: str = "./papers/", enable_cot: bool = True):
        print(f"🧠 CoT {'활성화' if enable_cot else '비활성화'} 모드로 시스템 초기화")
        
        self.enable_cot = enable_cot
        self.response_cache = {}
        
        # 예시 SQL 쿼리
        self.predefined_queries = {
            "지난달 총 운행건수는?": {
                "sql": """
                    SELECT 
                        COUNT(*) as total_operations,
                        SUM(ride_passenger + alight_passenger) as total_passengers,
                        COUNT(DISTINCT node_id) as active_stations
                    FROM station_passenger_history 
                    WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
                      AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
                      AND (ride_passenger > 0 OR alight_passenger > 0)
                """,
                "description": "지난 달 총 운행 건수 및 승객 통계"
            },
            "평균 승객수는?": {
                "sql": """
                    SELECT 
                        ROUND(AVG(ride_passenger + alight_passenger), 2) as avg_passengers,
                        SUM(ride_passenger + alight_passenger) as total_passengers
                    FROM station_passenger_history 
                    WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
                      AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
                """,
                "description": "평균 승객수 통계"
            }
        }
        
        # CoT 강화된 컴포넌트들 초기화
        self.llm = CoTEnhancedWatsonXLLM(enable_cot=enable_cot)
        self.classifier = CoTQuestionClassifier(self.predefined_queries, self.llm)
        self.quantitative_analyzer = CoTQuantitativeAnalyzer(DB_CONFIG, self.predefined_queries, self.llm)
        self.qualitative_analyzer = CoTQualitativeAnalyzer(self.llm)
        self.response_generator = CoTResponseGenerator(self.llm)
        
        # 정성분석 시스템 초기화
        if not self.qualitative_analyzer.initialize(papers_dir):
            print("⚠️ 정성분석 시스템 초기화 실패 - 정량분석만 사용 가능")
    
    def answer_question_with_cot(self, question: str) -> Dict[str, Any]:
        """
        CoT가 적용된 질문 분석 및 답변 생성
        
        Returns:
            Dict: {
                'answer': 최종답변,
                'reasoning': 전체추론과정,
                'classification': 질문분류,
                'classification_reasoning': 분류추론과정,
                'analysis_type': 분석유형,
                'confidence': 신뢰도
            }
        """
        
        # 캐시 확인
        question_key = question.strip().lower()
        if question_key in self.response_cache:
            print("💾 캐시된 답변 반환")
            return self.response_cache[question_key]
        
        print(f"🧠 CoT 기반 종합 분석 시작...")
        
        # 1단계: CoT 질문 분류
        print("🔍 1단계: CoT 질문 분류 중...")
        if self.enable_cot:
            question_type, classification_reasoning = self.classifier.classify_question_with_cot(question)
        else:
            question_type = self.classifier._basic_classify(question)
            classification_reasoning = f"기본 분류: {question_type.value}"
        
        print(f"   분류 결과: {question_type.value}")
        
        # 2단계: 유형별 CoT 분석 수행
        quantitative_data, quantitative_error, sql_info, quantitative_reasoning = None, None, None, ""
        qualitative_answer, qualitative_reasoning = None, ""
        
        if question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]:
            print("📊 2a단계: CoT 정량분석 중...")
            if self.enable_cot:
                quantitative_data, quantitative_error, sql_info, quantitative_reasoning = \
                    self.quantitative_analyzer.analyze_with_cot(question)
            else:
                # 기본 정량분석 (기존 방식)
                quantitative_data, quantitative_error, sql_info = \
                    self._basic_quantitative_analysis(question)
                quantitative_reasoning = "기본 정량분석 수행"
        
        if question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]:
            print("📚 2b단계: CoT 정성분석 중...")
            if self.enable_cot:
                qualitative_answer, qualitative_reasoning = \
                    self.qualitative_analyzer.analyze_with_cot(question)
            else:
                # 기본 정성분석 (기존 방식)
                qualitative_answer = self._basic_qualitative_analysis(question)
                qualitative_reasoning = "기본 정성분석 수행"
        
        # 3단계: CoT 최종 응답 생성
        print("✅ 3단계: CoT 최종응답 생성 중...")
        if self.enable_cot:
            final_answer, full_reasoning = self.response_generator.generate_final_response_with_cot(
                question, question_type, quantitative_data, quantitative_reasoning,
                qualitative_answer, qualitative_reasoning, sql_info
            )
        else:
            final_answer = self._basic_response_generation(
                question, question_type, quantitative_data, qualitative_answer, sql_info
            )
            full_reasoning = f"분류: {classification_reasoning}\n정량: {quantitative_reasoning}\n정성: {qualitative_reasoning}"
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(question_type, quantitative_data, qualitative_answer, sql_info)
        
        # 결과 구성
        result = {
            'answer': final_answer,
            'reasoning': full_reasoning,
            'classification': question_type.value,
            'classification_reasoning': classification_reasoning,
            'analysis_type': self._get_analysis_type_description(question_type),
            'confidence': confidence,
            'cot_enabled': self.enable_cot
        }
        
        # 캐시 저장
        self.response_cache[question_key] = result
        return result
    
    def _basic_quantitative_analysis(self, question: str) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
        """기본 정량분석 (CoT 없는 버전)"""
        # 기존 QuantitativeAnalyzer의 analyze 메서드와 유사한 로직
        return None, "CoT 비활성화 모드에서는 정량분석이 제한됩니다.", None
    
    def _basic_qualitative_analysis(self, question: str) -> str:
        """기본 정성분석 (CoT 없는 버전)"""
        if self.qualitative_analyzer.rag_chain:
            try:
                return self.qualitative_analyzer.rag_chain.invoke(question)
            except:
                return "정성분석 수행 중 오류가 발생했습니다."
        return "정성분석 시스템이 초기화되지 않았습니다."
    
    def _basic_response_generation(self, question: str, question_type: QuestionType,
                                 quantitative_data: Optional[pd.DataFrame],
                                 qualitative_answer: Optional[str],
                                 sql_info: Optional[Dict]) -> str:
        """기본 응답 생성 (CoT 없는 버전)"""
        if question_type == QuestionType.IRRELEVANT:
            return "죄송합니다. DRT 관련 질문을 해주세요."
        elif question_type == QuestionType.QUANTITATIVE:
            if quantitative_data is not None:
                return f"정량분석 결과: {quantitative_data.to_string(index=False)}"
            return "정량 데이터를 조회할 수 없습니다."
        elif question_type == QuestionType.QUALITATIVE:
            return qualitative_answer or "정성분석 결과를 제공할 수 없습니다."
        else:  # MIXED
            parts = []
            if quantitative_data is not None:
                parts.append(f"데이터: {quantitative_data.iloc[0].to_dict()}")
            if qualitative_answer:
                parts.append(f"분석: {qualitative_answer}")
            return "\n\n".join(parts) if parts else "종합분석을 수행할 수 없습니다."
    
    def _calculate_confidence(self, question_type: QuestionType, 
                            quantitative_data: Optional[pd.DataFrame],
                            qualitative_answer: Optional[str],
                            sql_info: Optional[Dict]) -> float:
        """답변 신뢰도 계산"""
        confidence = 0.5  # 기본값
        
        if question_type == QuestionType.IRRELEVANT:
            confidence = 0.9  # 관련없는 질문은 확실히 판단 가능
        elif question_type == QuestionType.QUANTITATIVE:
            if quantitative_data is not None and not quantitative_data.empty:
                confidence = 0.85
                if sql_info and sql_info.get('confidence', 0) > 80:
                    confidence = 0.9
        elif question_type == QuestionType.QUALITATIVE:
            if qualitative_answer and len(qualitative_answer.strip()) > 50:
                confidence = 0.75
        elif question_type == QuestionType.MIXED:
            data_conf = 0.4 if quantitative_data is not None else 0.0
            qual_conf = 0.4 if qualitative_answer else 0.0
            confidence = min(0.9, 0.2 + data_conf + qual_conf)
        
        return round(confidence, 2)
    
    def _get_analysis_type_description(self, question_type: QuestionType) -> str:
        """분석 유형 설명"""
        descriptions = {
            QuestionType.IRRELEVANT: "관련없는 질문 - 안내메시지 제공",
            QuestionType.QUANTITATIVE: "정량분석 - 데이터베이스 기반 수치 분석",
            QuestionType.QUALITATIVE: "정성분석 - 문서 기반 개념 및 이론 분석", 
            QuestionType.MIXED: "통합분석 - 정량데이터 + 정성분석 결합"
        }
        return descriptions.get(question_type, "알 수 없는 분석 유형")

# =============================================================================
# 유틸리티 함수
# =============================================================================

# =============================================================================
# 대화형 인터페이스
# =============================================================================

def interactive_chat_with_cot(rag_system: CoTSmartRAGSystem):
    """CoT 기능이 강화된 대화형 채팅 인터페이스"""
    print("=" * 80)
    print("🧠 CoT 강화 Watson AI 기반 스마트 DRT 분석 어시스턴트")
    print("=" * 80)
    print("✨ Chain of Thought 추론으로 투명하고 해석가능한 분석을 제공합니다")
    print("🔍 단계별 추론 과정을 통해 더 신뢰할 수 있는 답변을 생성합니다")
    print("📊 정량분석: PostgreSQL 데이터 + CoT 해석")
    print("📚 정성분석: 논문/문서 기반 RAG + CoT 추론")
    print("🔄 통합분석: 정량+정성 데이터를 CoT로 논리적 결합")
    print("⚠️ 관련없는 질문: CoT 분류로 정확한 안내")
    print("🎯 특징: 모든 답변에 추론 과정과 신뢰도 점수 제공!")
    print("\n명령어:")
    print("- 'reasoning': 마지막 답변의 상세 추론과정 보기")
    print("- 'confidence': 마지막 답변의 신뢰도 정보 보기") 
    print("- 'cot on/off': CoT 모드 전환")
    print("- 'quit' 또는 '종료': 프로그램 종료")
    print("=" * 80)
    
    last_result = None
    
    while True:
        try:
            question = input(f"\n🔍 질문 (CoT: {'ON' if rag_system.enable_cot else 'OFF'}): ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 이용해주셔서 감사합니다!")
                break
            
            if question.lower() == 'reasoning' and last_result:
                print(f"\n{'='*60}")
                print("🧠 상세 추론 과정:")
                print("="*60)
                print(last_result['reasoning'])
                print("="*60)
                continue
            
            if question.lower() == 'confidence' and last_result:
                print(f"\n{'='*60}")
                print("📊 신뢰도 정보:")
                print("="*60)
                print(f"분류: {last_result['classification']}")
                print(f"분석유형: {last_result['analysis_type']}")
                print(f"신뢰도: {last_result['confidence']:.0%}")
                print(f"CoT 사용: {'예' if last_result['cot_enabled'] else '아니오'}")
                print("="*60)
                continue
            
            if question.lower() in ['cot on', 'cot off']:
                new_state = question.lower() == 'cot on'
                rag_system.enable_cot = new_state
                rag_system.llm.enable_cot = new_state
                print(f"🧠 CoT 모드가 {'활성화' if new_state else '비활성화'}되었습니다.")
                continue
            
            if not question:
                continue
            
            print(f"\n{'='*60}")
            print("🧠 CoT 분석 진행 중...")
            
            result = rag_system.answer_question_with_cot(question)
            last_result = result
            
            print(f"\n🤖 최종 답변 (신뢰도: {result['confidence']:.0%}):")
            print("="*60)
            print(result['answer'])
            print("="*60)
            print(f"📋 분석유형: {result['analysis_type']}")
            if rag_system.enable_cot:
                print("💡 상세 추론과정을 보려면 'reasoning' 입력")
                print("📊 신뢰도 상세정보를 보려면 'confidence' 입력")
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n⚠️ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def main():
    """CoT 강화된 메인 함수"""
    try:
        # Watson AI 연결 확인
        if not credentials.api_key or not project_id:
            print("⚠️ Watson AI 자격증명이 설정되지 않았습니다.")
            print("환경변수 WATSONX_APIKEY와 WATSONX_PROJECT_ID를 설정해주세요.")
            return
        
        print(f"🚀 CoT 강화 Watson AI 기반 스마트 RAG 시스템 초기화 중...")
        print(f"🧠 Chain of Thought: 활성화")
        print(f"🔡 모델: {CHAT_MODEL}")
        print(f"🔗 임베딩: {EMBEDDING_MODEL}")
        print(f"🎯 특징: 단계별 추론과정으로 해석가능하고 신뢰할 수 있는 AI!")
        
        # CoT 시스템 생성
        cot_rag_system = CoTSmartRAGSystem(enable_cot=True)
        
# ========================================
        # 테스트 비활성화
        # ========================================
        # print("\n🧪 CoT 시스템 기능 테스트:")
        # test_questions = [
        #     "안녕하세요?",  # 관련없는 질문 → CoT 분류
        #     "지난달 운행 건수는?",  # 정량분석 → CoT SQL 매칭 + 해석  
        #     "DRT의 장점은 무엇인가요?",  # 정성분석 → CoT RAG
        #     "지난달 승객 수와 DRT 효과를 분석해주세요"  # 통합분석 → CoT 결합
        # ]
        # 
        # for i, q in enumerate(test_questions, 1):
        #     print(f"\n[CoT 테스트 {i}] {q}")
        #     try:
        #         result = cot_rag_system.answer_question_with_cot(q)
        #         preview = result['answer'][:100] + "..." if len(result['answer']) > 100 else result['answer']
        #         print(f"✅ 답변: {preview}")
        #         print(f"📋 분석: {result['analysis_type']} (신뢰도: {result['confidence']:.0%})")
        #     except Exception as e:
        #         print(f"⚠️ 오류: {str(e)}")
        # 
        # print("\n✅ CoT 테스트 완료! 대화형 모드를 시작합니다.\n")
        
        # 대화형 모드
        interactive_chat_with_cot(cot_rag_system)
        
    except Exception as e:
        print(f"⚠️ 시스템 초기화 실패: {str(e)}")
        print("\n환경 설정을 확인하세요:")
        print("1. Watson AI 자격증명 (WATSONX_APIKEY, WATSONX_PROJECT_ID)")
        print("2. papers/ 폴더의 PDF 파일 존재 여부")
        print("3. PostgreSQL 연결 설정") 
        print("4. 필요한 패키지 설치 여부")

if __name__ == "__main__":
    main()
