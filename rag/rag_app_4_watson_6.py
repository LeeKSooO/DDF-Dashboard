import os
import logging
import shutil
import pandas as pd
import json
import hashlib
import re
from datetime import datetime, timedelta
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

# .env 파일에서 환경변수 로드 (기존 환경변수를 덮어쓰기 허용)
load_dotenv(override=True)

# 벡터 데이터베이스 패키지 로드 (최신 버전 우선)
# langchain-chroma는 최신 버전으로 더 나은 성능과 안정성을 제공
try:
    from langchain_chroma import Chroma
    print("🔧 새로운 langchain-chroma 패키지를 사용합니다.")
except ImportError:
    from langchain_community.vectorstores import Chroma
    print("⚠️ 기존 chroma 패키지를 사용합니다. 업그레이드를 권장합니다: pip install -U langchain-chroma")

# Llama 4 Maverick 모델 임포트
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

# PDF 처리 관련 불필요한 로깅 메시지 차단
# pypdf와 pdfminer는 많은 디버그 메시지를 출력하므로 ERROR 레벨로 제한
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# =============================================================================
# Watson AI 연결 설정
# =============================================================================

# Watson AI 인증 정보 설정
# 환경변수에서 API 키와 프로젝트 ID를 가져와 초기화
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",  # Watson AI 서비스 엔드포인트
    api_key=os.getenv("WATSONX_APIKEY"),      # .env 파일의 WATSONX_APIKEY
)
project_id = os.getenv("WATSONX_PROJECT_ID")  # .env 파일의 WATSONX_PROJECT_ID

# =============================================================================
# AI 모델 설정
# =============================================================================

# 임베딩 모델: 문서를 벡터로 변환하는 모델 (HuggingFace 무료 모델 사용)
# all-MiniLM-L12-v2는 성능과 속도의 균형이 좋은 모델
# EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
# microsoft사의 multilingual-MiniLM-L12-v2 모델 (한국어 지원 우수)
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
# 대화형 AI 모델: Watson AI의 Granite 모델 사용
# granite-3-8b-instruct는 한국어 지원이 우수한 지시 튜닝 모델
CHAT_MODEL = "ibm/granite-3-8b-instruct"
# CHAT_MODEL = "meta-llama/llama-3-3-70b-instruct"

# =============================================================================
# 데이터베이스 연결 설정
# =============================================================================

# PostgreSQL 연결 정보
# 정량분석을 위한 DRT 운행 데이터가 저장된 데이터베이스
DB_CONFIG = {
    'host': 'localhost',        # 데이터베이스 서버 주소
    'port': 5432,              # PostgreSQL 기본 포트
    'database': 'ddf_db',      # 데이터베이스 이름
    'user': 'ddf_user',        # 사용자 이름
    'password': 'ddf_password' # 비밀번호
}

# =============================================================================
# 대화 컨텍스트 관리자
# =============================================================================

class ConversationContext:
    """
    대화 상태와 컨텍스트를 관리하는 클래스
    
    주요 기능:
    - 대화 히스토리 추적
    - 매개변수 수집 상태 관리
    - 미완성 쿼리 추적
    """
    
    def __init__(self):
        self.conversation_history = []
        self.pending_query = None
        self.required_params = {}
        self.collected_params = {}
        self.waiting_for_params = False
        self.query_type = None
        
    def add_message(self, role: str, content: str):
        """대화 히스토리에 메시지 추가"""
        self.conversation_history.append({
            'role': role,  # 'user' or 'assistant'
            'content': content,
            'timestamp': datetime.now()
        })
    
    def set_pending_query(self, query_type: str, required_params: List[str]):
        """미완성 쿼리 설정"""
        self.pending_query = True
        self.query_type = query_type
        self.required_params = {param: None for param in required_params}
        self.waiting_for_params = True
        
    def update_param(self, param_name: str, value: Any):
        """매개변수 업데이트"""
        if param_name in self.required_params:
            self.required_params[param_name] = value
            self.collected_params[param_name] = value
    
    def get_missing_params(self) -> List[str]:
        """누락된 매개변수 목록 반환"""
        return [param for param, value in self.required_params.items() if value is None]
    
    def is_query_complete(self) -> bool:
        """쿼리에 필요한 모든 매개변수가 수집되었는지 확인"""
        return len(self.get_missing_params()) == 0
    
    def reset(self):
        """컨텍스트 리셋"""
        self.pending_query = None
        self.required_params = {}
        self.collected_params = {}
        self.waiting_for_params = False
        self.query_type = None

# =============================================================================
# 매개변수 추출기
# =============================================================================

class ParameterExtractor:
    """
    자연어에서 날짜, 지역, 기타 매개변수를 추출하는 클래스
    
    주요 기능:
    - 날짜 표현 파싱 (7월 2일, 2024-07-02, 지난달 등)
    - 지역명 추출 (강남구, 서울시 등)
    - 키워드 기반 매개변수 식별
    """
    
    def __init__(self):
        # 지역 키워드 패턴
        self.region_patterns = [
            r'([가-힣]+구)',  # ~구
            r'([가-힣]+시)',  # ~시
            r'([가-힣]+동)',  # ~동
            r'([가-힣]+면)',  # ~면
        ]
        
        # 날짜 패턴들
        self.date_patterns = [
            r'(\d{1,2})월\s*(\d{1,2})일',  # 7월 2일
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2024-07-02
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2024년 7월 2일
        ]
        
        # 기간 키워드
        self.period_keywords = {
            '오늘': 0,
            '어제': -1,
            '지난주': -7,
            '지난달': -30,
            '작년': -365
        }
    
    def extract_parameters(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 모든 매개변수를 추출합니다.
        
        Args:
            text (str): 분석할 텍스트
            
        Returns:
            Dict[str, Any]: 추출된 매개변수들
        """
        params = {}
        
        # 지역 추출
        region = self.extract_region(text)
        if region:
            params['region'] = region
            
        # 날짜 범위 추출
        date_range = self.extract_date_range(text)
        if date_range:
            params.update(date_range)
            
        return params
    
    def extract_region(self, text: str) -> Optional[str]:
        """지역명 추출"""
        for pattern in self.region_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    def extract_date_range(self, text: str) -> Dict[str, str]:
        """날짜 범위 추출"""
        result = {}
        
        # "7월 2일에서 7월 5일까지" 패턴
        range_pattern = r'(\d{1,2})월\s*(\d{1,2})일에서\s*(\d{1,2})월\s*(\d{1,2})일까지'
        match = re.search(range_pattern, text)
        if match:
            start_month, start_day, end_month, end_day = match.groups()
            current_year = datetime.now().year
            
            result['start_date'] = f"{current_year}-{int(start_month):02d}-{int(start_day):02d}"
            result['end_date'] = f"{current_year}-{int(end_month):02d}-{int(end_day):02d}"
            return result
        
        # 단일 날짜 패턴들
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 2:  # 월일 패턴
                    month, day = match.groups()
                    current_year = datetime.now().year
                    date_str = f"{current_year}-{int(month):02d}-{int(day):02d}"
                    result['start_date'] = date_str
                    result['end_date'] = date_str
                elif len(match.groups()) == 3:  # 년월일 패턴
                    year, month, day = match.groups()
                    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                    result['start_date'] = date_str
                    result['end_date'] = date_str
                break
        
        # 상대적 날짜 키워드
        for keyword, days_offset in self.period_keywords.items():
            if keyword in text:
                target_date = datetime.now() + timedelta(days=days_offset)
                date_str = target_date.strftime('%Y-%m-%d')
                result['start_date'] = date_str
                result['end_date'] = date_str
                break
                
        return result

# =============================================================================
# 동적 SQL 생성기
# =============================================================================

class DynamicQueryBuilder:
    """
    사용자 매개변수를 기반으로 동적 SQL 쿼리를 생성하는 클래스
    
    주요 기능:
    - 매개변수 기반 WHERE 절 동적 생성
    - 다양한 쿼리 타입 지원
    - SQL 인젝션 방지
    """
    
    def __init__(self):
        # 쿼리 템플릿들
        self.query_templates = {
            'operation_count': """
                SELECT 
                    COUNT(*) as total_operations,
                    SUM(ride_passenger + alight_passenger) as total_passengers,
                    COUNT(DISTINCT node_id) as active_stations,
                    AVG(ride_passenger + alight_passenger) as avg_passengers_per_operation
                FROM station_passenger_history 
                WHERE 1=1
            """,
            'daily_stats': """
                SELECT 
                    record_date,
                    COUNT(*) as daily_operations,
                    SUM(ride_passenger + alight_passenger) as daily_passengers
                FROM station_passenger_history 
                WHERE 1=1
            """,
            'station_stats': """
                SELECT 
                    node_id,
                    node_name,
                    COUNT(*) as operations,
                    SUM(ride_passenger + alight_passenger) as total_passengers
                FROM station_passenger_history 
                WHERE 1=1
            """
        }
    
    def build_query(self, query_type: str, params: Dict[str, Any]) -> str:
        """
        매개변수를 기반으로 동적 쿼리 생성
        
        Args:
            query_type (str): 쿼리 타입
            params (Dict[str, Any]): 쿼리 매개변수들
            
        Returns:
            str: 완성된 SQL 쿼리
        """
        if query_type not in self.query_templates:
            raise ValueError(f"지원하지 않는 쿼리 타입: {query_type}")
        
        base_query = self.query_templates[query_type]
        conditions = []
        
        # 날짜 조건 추가
        if params.get('start_date'):
            conditions.append(f"record_date >= '{params['start_date']}'")
        if params.get('end_date'):
            conditions.append(f"record_date <= '{params['end_date']}'")
        
        # 지역 조건 추가 (region 컬럼이 있다고 가정)
        if params.get('region'):
            conditions.append(f"region = '{params['region']}'")
        
        # 승객 수 필터 (운행이 있었던 경우만)
        conditions.append("(ride_passenger > 0 OR alight_passenger > 0)")
        
        # WHERE 절 결합
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # GROUP BY 추가 (필요한 경우)
        if query_type == 'daily_stats':
            base_query += " GROUP BY record_date ORDER BY record_date"
        elif query_type == 'station_stats':
            base_query += " GROUP BY node_id, node_name ORDER BY total_passengers DESC"
        
        return base_query
    
    def get_required_params(self, query_type: str) -> List[str]:
        """쿼리 타입별 필수 매개변수 반환"""
        param_requirements = {
            'operation_count': ['start_date', 'end_date'],
            'daily_stats': ['start_date', 'end_date'], 
            'station_stats': ['start_date', 'end_date']
        }
        return param_requirements.get(query_type, [])

# =============================================================================
# Watson AI LLM 래퍼 클래스
# =============================================================================

class WatsonXLLM(LLM):
    """
    Watson AI를 LangChain LLM 인터페이스로 래핑하는 클래스
    
    주요 기능:
    - Watson AI의 ModelInference를 LangChain의 LLM 인터페이스로 통합
    - 디버깅을 위한 상세한 프롬프트 및 응답 출력
    - 에러 처리 및 사용자 친화적 오류 메시지 제공
    - 한국어 프롬프트에 최적화된 파라미터 설정
    """
    
    model: Any = None
    
    def __init__(self, **kwargs):
        """Watson AI 모델 초기화"""
        super().__init__(**kwargs)
        
        # Watson AI 모델 생성 파라미터 설정
        # - decoding_method: "greedy"는 가장 확률이 높은 토큰을 선택 (일관성 높음)
        # - min_new_tokens: 최소 생성 토큰 수
        # - max_new_tokens: 최대 생성 토큰 수 (너무 길면 응답 시간 증가)
        # - temperature: 0.1로 낮게 설정하여 일관되고 예측 가능한 답변 생성
        parameters = {
            "decoding_method": "greedy",    # 탐욕적 디코딩 (일관성 우선)
            "min_new_tokens": 10,          # 최소 10토큰 생성
            "max_new_tokens": 2000,        # 최대 2000토큰 생성
            "temperature": 0.1             # 낮은 온도로 일관성 향상
        }
        
        # Watson AI ModelInference 객체 생성
        self.model = ModelInference(
            model_id=CHAT_MODEL,        # 사용할 모델 ID
            params=parameters,          # 생성 파라미터
            credentials=credentials,    # 인증 정보
            project_id=project_id      # Watson 프로젝트 ID
        )
    
    @property
    def _llm_type(self) -> str:
        return "watson_x"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Watson AI 모델을 호출하여 응답을 생성합니다.
        
        Args:
            prompt (str): 모델에 전송할 프롬프트
            stop (Optional[List[str]]): 생성 중단 토큰 (미사용)
            run_manager (Optional[CallbackManagerForLLMRun]): 콜백 매니저 (미사용)
            **kwargs: 추가 키워드 인자
            
        Returns:
            str: 모델이 생성한 응답 텍스트
        """
        try:
            print("🤖 Watson AI 응답 생성 중...")
            response = self.model.generate_text(prompt=prompt)
            return response
            
        except Exception as e:
            print(f"❌ Watson AI 오류: {str(e)}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다."

# =============================================================================
# 질문 분류 시스템
# =============================================================================

class QuestionType(Enum):
    """
    사용자 질문의 유형을 정의하는 열거형
    
    IRRELEVANT: DRT/교통과 무관한 질문
    QUANTITATIVE: 정량적 데이터 분석이 필요한 질문 (SQL 쿼리 사용)
    QUALITATIVE: 정성적 분석이 필요한 질문 (논문/문서 기반 RAG 사용)
    MIXED: 정량+정성 분석이 모두 필요한 복합 질문
    INCOMPLETE: 매개변수가 부족한 미완성 질문
    """
    IRRELEVANT = "irrelevant"      # 관련없는 질문
    QUANTITATIVE = "quantitative"  # 정량분석 질문
    QUALITATIVE = "qualitative"    # 정성분석 질문
    MIXED = "mixed"               # 통합분석 질문
    INCOMPLETE = "incomplete"     # 미완성 질문

class QuestionClassifier:
    """
    사용자 질문을 5가지 유형으로 자동 분류하는 클래스
    
    분류 로직:
    1. 키워드 기반 분류 (정량/정성/관련없음)
    2. SQL 매칭 가능성 확인 (fuzzy matching 사용)
    3. DRT/교통 관련성 검사
    4. 매개변수 완성도 확인
    5. 최종 유형 결정 (단일 또는 복합)
    
    주요 기능:
    - 한국어 키워드 기반 의도 분석
    - 기존 SQL 쿼리와의 유사도 매칭
    - 관련없는 질문 필터링
    - 복합 질문 감지
    - 미완성 질문 탐지
    """
    
    def __init__(self, predefined_queries: Dict, parameter_extractor: ParameterExtractor):
        """
        질문 분류기 초기화
        
        Args:
            predefined_queries (Dict): 사전 정의된 SQL 쿼리 매핑
            parameter_extractor (ParameterExtractor): 매개변수 추출기
        """
        self.predefined_queries = predefined_queries
        self.parameter_extractor = parameter_extractor
        
        # 정량분석 관련 키워드 (숫자, 통계, 데이터 분석 관련)
        self.quantitative_keywords = [
            "얼마나", "몇", "수", "통계", "데이터", "평균", "총", "최대", "최소",
            "비율", "퍼센트", "%", "건수", "횟수", "개수", "명", "시간대",
            "운행", "승객", "정류장", "노선", "이용률", "효율성", "실적"
        ]
        
        # 정성분석 관련 키워드 (개념, 이론, 분석 관련)
        self.qualitative_keywords = [
            "어떻게", "왜", "무엇", "방법", "이유", "장점", "단점", "특징",
            "원리", "개념", "정의", "설명", "분석", "연구", "논문", "이론",
            "사례", "예시", "비교", "차이점", "유사점", "효과", "영향"
        ]
        
        # 관련없는 질문 키워드 (DRT/교통과 무관한 주제)
        self.irrelevant_keywords = [
            "안녕", "날씨", "음식", "여행", "취미", "영화", "음악", "스포츠",
            "게임", "연예인", "정치", "경제일반", "주식", "부동산일반"
        ]
        
        # 불완전한 질문 패턴들
        self.incomplete_patterns = [
            r"어떤.*찾",  # "어떤 운행건수를 찾아줘?"
            r"뭔가.*알고",  # "뭔가 알고 싶어"
            r".*정보.*필요",  # "정보가 필요해"
        ]
        
    def classify_question(self, question: str, context: ConversationContext = None) -> Tuple[QuestionType, Dict]:
        """
        질문을 5가지 유형으로 자동 분류합니다.
        
        분류 알고리즘:
        1. 관련없는 질문 먼저 필터링
        2. 불완전한 질문 패턴 확인
        3. 정량분석 가능성 확인 (SQL 매칭 + 키워드)
        4. 정성분석 필요성 확인 (키워드 기반)
        5. 복합 분석 필요시 MIXED 타입 반환
        6. 교통 관련이지만 분류 불가시 QUALITATIVE로 처리
        
        Args:
            question (str): 분류할 사용자 질문
            context (ConversationContext): 대화 컨텍스트
            
        Returns:
            Tuple[QuestionType, Dict]: 분류된 질문 유형과 추가 정보
        """
        question_lower = question.lower()
        classification_info = {}
        
        # 1단계: 관련없는 질문 체크 (최우선)
        if self._is_irrelevant(question_lower):
            return QuestionType.IRRELEVANT, classification_info
        
        # 2단계: 불완전한 질문 패턴 체크
        if self._is_incomplete_question(question):
            # 어떤 종류의 정보를 원하는지 추정
            query_type = self._guess_query_type(question)
            classification_info['suggested_query_type'] = query_type
            classification_info['missing_params'] = self._get_typical_missing_params(query_type)
            return QuestionType.INCOMPLETE, classification_info
        
        # 3단계: 매개변수 추출 시도
        extracted_params = self.parameter_extractor.extract_parameters(question)
        classification_info['extracted_params'] = extracted_params
        
        # 4단계: 정량분석 가능한 질문인지 체크
        # SQL 매칭 가능하거나 정량분석 키워드 포함시
        has_quantitative = (self._has_sql_match(question) or 
                           self._contains_keywords(question_lower, self.quantitative_keywords))
        
        # 5단계: 정성분석이 필요한 질문인지 체크
        has_qualitative = self._contains_keywords(question_lower, self.qualitative_keywords)
        
        # 6단계: 매개변수 완성도 확인
        if has_quantitative:
            query_type = self._determine_query_type(question)
            required_params = self._get_required_params_for_query(query_type)
            missing_params = [p for p in required_params if p not in extracted_params]
            
            if missing_params:
                classification_info['query_type'] = query_type
                classification_info['missing_params'] = missing_params
                return QuestionType.INCOMPLETE, classification_info
        
        # 7단계: 분류 결정 로직
        if has_quantitative and has_qualitative:
            return QuestionType.MIXED, classification_info        # 정량+정성 모두 필요
        elif has_quantitative:
            classification_info['query_type'] = self._determine_query_type(question)
            return QuestionType.QUANTITATIVE, classification_info # 정량분석만 필요
        elif has_qualitative:
            return QuestionType.QUALITATIVE, classification_info  # 정성분석만 필요
        else:
            # 8단계: 키워드 매칭 실패시 교통 관련성으로 최종 판단
            if self._is_transport_related(question_lower):
                return QuestionType.QUALITATIVE, classification_info  # 교통 관련은 정성분석으로
            else:
                return QuestionType.IRRELEVANT, classification_info   # 완전히 관련없음
    
    def _is_irrelevant(self, question: str) -> bool:
        """관련없는 질문인지 확인합니다."""
        return self._contains_keywords(question, self.irrelevant_keywords)
    
    def _is_incomplete_question(self, question: str) -> bool:
        """불완전한 질문인지 확인합니다."""
        for pattern in self.incomplete_patterns:
            if re.search(pattern, question):
                return True
        return False
    
    def _guess_query_type(self, question: str) -> str:
        """불완전한 질문에서 의도하는 쿼리 타입을 추정합니다."""
        if "운행" in question and "건수" in question:
            return "operation_count"
        elif "통계" in question or "현황" in question:
            return "daily_stats"
        elif "정류장" in question:
            return "station_stats"
        return "operation_count"  # 기본값
    
    def _get_typical_missing_params(self, query_type: str) -> List[str]:
        """쿼리 타입별 일반적으로 필요한 매개변수들을 반환합니다."""
        return ['region', 'start_date', 'end_date']
    
    def _determine_query_type(self, question: str) -> str:
        """질문에서 쿼리 타입을 결정합니다."""
        if "일별" in question or "날짜별" in question:
            return "daily_stats"
        elif "정류장" in question or "역" in question:
            return "station_stats"
        else:
            return "operation_count"
    
    def _get_required_params_for_query(self, query_type: str) -> List[str]:
        """쿼리 타입별 필수 매개변수를 반환합니다."""
        return ['start_date', 'end_date']  # 기본적으로 날짜는 필수
    
    def _has_sql_match(self, question: str) -> bool:
        """기존 SQL 쿼리와 매칭 가능한 질문인지 확인합니다."""
        for mapped_question in self.predefined_queries.keys():
            similarity = fuzz.token_sort_ratio(question.lower(), mapped_question.lower())
            if similarity >= 60:
                return True
        return False
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """텍스트에 지정된 키워드가 포함되어 있는지 확인합니다."""
        return any(keyword in text for keyword in keywords)
    
    def _is_transport_related(self, question: str) -> bool:
        """교통/DRT 관련 질문인지 확인합니다."""
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

# =============================================================================
# 정량 분석 시스템 (PostgreSQL 기반) - 동적 쿼리 지원
# =============================================================================

class QuantitativeAnalyzer:
    """
    PostgreSQL 데이터베이스를 활용한 정량적 분석을 수행하는 클래스
    동적 쿼리 생성 기능이 추가되었습니다.
    
    주요 기능:
    - PostgreSQL 연결 관리
    - 동적 SQL 쿼리 생성 및 실행
    - 매개변수 기반 쿼리 커스터마이징
    - 에러 처리 및 로깅
    
    데이터 소스:
    - DRT 운행 데이터
    - 승객 통계
    - 정류장 이용 현황
    - 시간별/일별 운행 패턴
    """
    
    def __init__(self, db_config: Dict, predefined_queries: Dict):
        """
        정량분석기 초기화
        
        Args:
            db_config (Dict): PostgreSQL 연결 설정
            predefined_queries (Dict): 사전 정의된 SQL 쿼리 매핑
        """
        self.db_config = db_config
        self.predefined_queries = predefined_queries
        self.engine = self._create_connection()
        self.query_builder = DynamicQueryBuilder()
    
    def _create_connection(self):
        """PostgreSQL 데이터베이스 연결을 생성하고 테스트합니다."""
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
            print(f"❌ 데이터베이스 연결 실패: {str(e)}")
            print("🔧 연결 설정을 확인하세요:")
            print(f"   - 호스트: {self.db_config['host']}:{self.db_config['port']}")
            print(f"   - 데이터베이스: {self.db_config['database']}")
            print(f"   - 사용자: {self.db_config['user']}")
            return None
    
    def analyze(self, question: str, params: Dict[str, Any] = None, query_type: str = None) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
        """
        사용자 질문에 대한 정량적 분석을 수행합니다.
        
        처리 과정:
        1. 데이터베이스 연결 확인
        2. 동적 쿼리 생성 (매개변수 기반) 또는 기존 SQL 매칭
        3. SQL 실행 및 결과 반환
        4. 에러 처리 및 로깅
        
        Args:
            question (str): 분석할 사용자 질문
            params (Dict[str, Any]): 쿼리 매개변수들
            query_type (str): 쿼리 타입
            
        Returns:
            Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
                - DataFrame: 쿼리 실행 결과 (성공시)
                - str: 에러 메시지 (실패시)
                - Dict: 사용된 SQL 정보
        """
        if not self.engine:
            return None, "데이터베이스 연결이 없습니다.", None
        
        sql_info = {}
        
        # 동적 쿼리 생성 우선 시도
        if params and query_type:
            try:
                sql_query = self.query_builder.build_query(query_type, params)
                sql_info = {
                    'sql': sql_query,
                    'type': 'dynamic',
                    'query_type': query_type,
                    'params': params
                }
                print(f"🔧 동적 쿼리 생성: {query_type}")
            except Exception as e:
                print(f"⚠️ 동적 쿼리 생성 실패: {e}")
                # 기존 매칭 방식으로 폴백
                best_match = self._find_best_sql_match(question)
                if not best_match:
                    return None, "매칭되는 SQL 쿼리를 찾을 수 없습니다.", None
                sql_info = best_match
        else:
            # 기존 SQL 매칭 방식
            best_match = self._find_best_sql_match(question)
            if not best_match:
                return None, "매칭되는 SQL 쿼리를 찾을 수 없습니다.", None
            sql_info = best_match
        
        print(f"📊 데이터 조회 중...")
        
        # SQL 실행
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_info['sql']))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    return None, "조회 결과가 없습니다.", sql_info
                
                print(f"✅ SQL 실행 성공 - {len(df)}행 {len(df.columns)}열 데이터 조회")
                return df, None, sql_info
                
        except Exception as e:
            error_msg = f"SQL 실행 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg, sql_info
    
    def _find_best_sql_match(self, question: str) -> Optional[Dict]:
        """기존의 SQL 매칭 로직을 유지합니다."""
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
                    'confidence': score,
                    'type': 'predefined'
                }
        
        return best_match

# =============================================================================
# 정성 분석 시스템 (기존 코드 유지)
# =============================================================================

class QualitativeAnalyzer:
    """정성 분석 (Vector DB with Watson AI) - 기존 코드 유지"""
    
    def __init__(self):
        self.rag_chain = None
        self.vectorstore = None
        self.processed_files_path = "./processed_files.json"
        self.processed_files_info = self._load_processed_files()
    
    def _load_processed_files(self) -> Dict:
        """이전에 처리된 파일 정보를 로드합니다."""
        try:
            if os.path.exists(self.processed_files_path):
                with open(self.processed_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 로드 실패: {e}")
        return {}
    
    def _save_processed_files(self):
        """처리된 파일 정보를 저장합니다."""
        try:
            with open(self.processed_files_path, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 저장 실패: {e}")
    
    def _get_file_hash(self, filepath: str) -> str:
        """파일의 MD5 해시를 계산합니다."""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _is_file_changed(self, filepath: str) -> bool:
        """파일이 이전 처리 시점보다 변경되었는지 확인합니다."""
        filename = os.path.basename(filepath)
        current_hash = self._get_file_hash(filepath)
        
        if filename not in self.processed_files_info:
            return True
        
        stored_hash = self.processed_files_info[filename].get('hash', '')
        return current_hash != stored_hash
    
    def _update_processed_file_info(self, filepath: str, doc_count: int):
        """처리된 파일 정보를 업데이트합니다."""
        filename = os.path.basename(filepath)
        self.processed_files_info[filename] = {
            'hash': self._get_file_hash(filepath),
            'processed_date': datetime.now().isoformat(),
            'document_count': doc_count,
            'file_size': os.path.getsize(filepath)
        }
    
    def initialize(self, papers_dir: str = "./papers/"):
        """RAG 시스템을 초기화합니다."""
        print("📚 정성분석용 RAG 시스템 초기화 중...")
        
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
            print(f"🔍 기존 벡터 데이터베이스 발견: {vectorstore_path}")
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
                else:
                    print("✅ 모든 문서가 이미 처리됨 - 기존 벡터 데이터베이스 사용")
                    
            except Exception as e:
                print(f"⚠️ 기존 벡터 데이터베이스 로드 실패: {e}")
                print("🔄 새로운 벡터 데이터베이스 생성 중...")
                existing_vectorstore_exists = False
        
        if not existing_vectorstore_exists:
            docs = self._load_documents(papers_dir)
            if not docs:
                print("❌ 문서를 로드할 수 없습니다.")
                return False
            
            print(f"📄 총 {len(docs)}개 문서를 벡터 데이터베이스로 변환 중...")
            
            splits = self._split_documents(docs)
            print(f"✂️ 문서를 {len(splits)}개 청크로 분할 완료")
            
            if os.path.exists(vectorstore_path):
                shutil.rmtree(vectorstore_path)
                print(f"🗑️ 기존 손상된 벡터 데이터베이스 삭제: {vectorstore_path}")
            
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=vectorstore_path
            )
            print(f"✅ 새 벡터 데이터베이스 생성 완료: {vectorstore_path}")
        
        self._save_processed_files()
        
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}
        )
        print("🔍 문서 검색기 구성 완료 (유사도 기반, k=6)")
        
        prompt = PromptTemplate(
            template="""당신은 DRT(수요응답형 교통) 전문 분석가입니다.

예시 1:
질문: DRT의 장점은 무엇인가요?
참고자료: [문서] DRT는 기존 대중교통의 한계를 보완하는 혁신적 서비스로, 문전수송 서비스 제공과 운행 효율성 향상이 주요 장점입니다.
답변: DRT의 주요 장점은 문전수송 서비스로 승객 편의성을 높이고, 수요 기반 운행으로 운영 효율성을 향상시키며, 교통소외지역의 이동권을 보장한다는 점입니다.

예시 2:
질문: DRT 운영 최적화 방법은?
참고자료: [문서] 동적 라우팅 알고리즘과 실시간 수요 예측을 통해 차량 배치를 최적화하며, AI 기반 스케줄링으로 대기시간을 단축시킵니다.
답변: DRT 최적화는 동적 라우팅 알고리즘으로 실시간 경로 조정, AI 기반 수요 예측으로 차량 배치 효율화, 그리고 스케줄링 최적화를 통한 승객 대기시간 단축이 핵심입니다.

예시 3:
질문: DRT와 기존 버스의 차이점은?
참고자료: [문서] 고정노선 버스는 정해진 경로와 시간표로 운행하지만, DRT는 승객 수요에 따라 유연하게 경로와 시간을 조정합니다.
답변: 기존 버스는 고정된 노선과 시간표로 운행하는 반면, DRT는 승객의 실시간 수요에 따라 경로와 운행시간을 유연하게 조정하여 더 개인화된 교통서비스를 제공합니다.

질문: {question}
참고자료:
{context}
답변:""",
            input_variables=["question", "context"]
        )
        
        llm = WatsonXLLM()
        print("🤖 Watson AI LLM 초기화 완료")
        
        def format_docs(docs):
            """검색된 문서들을 LLM이 이해하기 쉬운 형태로 포맷팅합니다."""
            context = "\n\n---\n\n".join([
                f"[문서 {i+1}]\n{doc.page_content}"
                for i, doc in enumerate(docs)
            ])
            
            print(f"📚 {len(docs)}개 문서 참조")
            
            return context
        
        self.rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        print("⛓️ RAG 체인 파이프라인 구성 완료")
        
        print("✅ 정성분석 RAG 시스템 준비 완료!")
        return True
    
    def analyze(self, question: str) -> str:
        """정성 분석 수행"""
        if not self.rag_chain:
            return "정성분석 시스템이 초기화되지 않았습니다."
        
        try:
            answer = self.rag_chain.invoke(question)
            if hasattr(answer, 'content'):
                return answer.content
            return str(answer)
        except Exception as e:
            return f"정성분석 오류: {str(e)}"
    
    def _validate_papers_directory(self, papers_dir: str) -> bool:
        """Papers 디렉터리가 유효한지 검증합니다."""
        abs_path = os.path.abspath(papers_dir)
        print(f"📁 Papers 디렉터리 확인: {abs_path}")
        
        if not os.path.exists(abs_path):
            print(f"❌ Papers 디렉터리가 존재하지 않습니다: {abs_path}")
            print("💡 다음 중 하나를 시도해보세요:")
            print(f"   - 디렉터리 생성: mkdir -p {abs_path}")
            print(f"   - 다른 경로 사용 (예: './papers/', '/absolute/path/to/papers/')")
            return False
        
        if not os.path.isdir(abs_path):
            print(f"❌ 지정된 경로가 디렉터리가 아닙니다: {abs_path}")
            return False
        
        pdf_count = 0
        for root, dirs, files in os.walk(abs_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_count += 1
        
        if pdf_count == 0:
            print(f"⚠️ Papers 디렉터리에 PDF 파일이 없습니다: {abs_path}")
            print("💡 PDF 파일을 추가한 후 다시 시도하세요.")
            return False
        
        print(f"✅ Papers 디렉터리 검증 완료 - {pdf_count}개 PDF 파일 발견")
        return True
    
    def _get_new_or_changed_documents(self, directory_path: str) -> List:
        """새로운 또는 변경된 문서만 반환합니다."""
        new_or_changed_files = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    filepath = os.path.join(root, file)
                    if self._is_file_changed(filepath):
                        new_or_changed_files.append(filepath)
                        print(f"📄 새로운/변경된 파일: {os.path.basename(filepath)}")
        
        return new_or_changed_files
    
    def _add_documents_to_vectorstore(self, new_files: List[str]):
        """새로운 문서들을 기존 벡터 데이터베이스에 추가합니다."""
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
    
    def _split_documents(self, docs: List) -> List:
        """문서를 청크 단위로 분할합니다."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""]
        )
        return text_splitter.split_documents(docs)
    
    def _load_single_document(self, filepath: str) -> List:
        """단일 PDF 파일을 로드합니다."""
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
            print(f"❌ 모든 로더 실패: {filename} - {str(e)}")
        
        return []
    
    def _load_documents(self, directory_path: str) -> List:
        """디렉터리의 모든 PDF 문서를 로드합니다."""
        all_docs = []
        pdf_files = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"📚 총 {len(pdf_files)}개의 PDF 파일을 발견했습니다.")
        
        successful_loads = 0
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            docs = self._load_single_document(pdf_path)
            
            if docs:
                all_docs.extend(docs)
                successful_loads += 1
                self._update_processed_file_info(pdf_path, len(docs))
            else:
                print(f"❌ 로드 실패: {filename}")
        
        print(f"📊 로드 결과: {successful_loads}/{len(pdf_files)}개 파일 성공, 총 {len(all_docs)}개 문서")
        return all_docs

# =============================================================================
# 답변 생성기 (기존 코드 유지 + 대화형 기능 추가)
# =============================================================================

class ResponseGenerator:
    """최종 답변 생성기 (Watson AI 사용) - 대화형 기능 추가"""
    
    def __init__(self):
        self.llm = WatsonXLLM()
    
    def generate_final_response(self, question: str, question_type: QuestionType, 
                              quantitative_data: Optional[pd.DataFrame] = None, 
                              qualitative_answer: Optional[str] = None,
                              sql_info: Optional[Dict] = None,
                              classification_info: Optional[Dict] = None) -> str:
        """최종 답변 생성 - 대화형 기능 추가"""
        
        if question_type == QuestionType.IRRELEVANT:
            return self._generate_irrelevant_response()
        
        elif question_type == QuestionType.INCOMPLETE:
            return self._generate_incomplete_response(classification_info)
        
        elif question_type == QuestionType.QUANTITATIVE:
            return self._generate_quantitative_response(question, quantitative_data, sql_info)
        
        elif question_type == QuestionType.QUALITATIVE:
            return self._generate_qualitative_response(question, qualitative_answer)
        
        elif question_type == QuestionType.MIXED:
            return self._generate_mixed_response(question, quantitative_data, qualitative_answer, sql_info)
        
        else:
            return "죄송합니다. 질문을 처리할 수 없습니다."
    
    def _generate_incomplete_response(self, classification_info: Dict) -> str:
        """불완전한 질문에 대한 추가 정보 요청 응답 생성"""
        missing_params = classification_info.get('missing_params', [])
        suggested_query_type = classification_info.get('suggested_query_type', 'operation_count')
        
        response = "더 정확한 분석을 위해 추가 정보가 필요합니다.\n\n"
        
        if 'region' in missing_params:
            response += "🏙️ **지역 정보**: 어떤 구나 시의 정보를 찾고 계신가요?\n"
            response += "   예시: 강남구, 서초구, 서울시 등\n\n"
        
        if 'start_date' in missing_params or 'end_date' in missing_params:
            response += "📅 **날짜 범위**: 어떤 기간의 데이터를 조회하시겠어요?\n"
            response += "   예시: 7월 2일에서 7월 5일까지\n"
            response += "   예시: 2024-07-02부터 2024-07-05까지\n"
            response += "   예시: 지난주, 지난달\n\n"
        
        response += "💡 **예시 질문**: '7월 2일에서 7월 5일까지 강남구의 운행 건수를 찾고 있습니다.'"
        
        return response
    
    def _generate_irrelevant_response(self) -> str:
        return """죄송합니다. 저는 DRT(수요응답형 교통) 및 교통 시스템 분야 전문 분석 어시스턴트입니다. 
        
교통, DRT, 모빌리티, 대중교통 관련 질문을 해주시면 정량적 데이터 분석과 정성적 연구 자료를 바탕으로 전문적인 답변을 드리겠습니다.

예시 질문:
- 지난달 운행 건수는?
- DRT의 장점은 무엇인가요?
- 수요응답형 교통 시스템은 어떻게 작동하나요?"""
    
    def _generate_quantitative_response(self, question: str, data: pd.DataFrame, sql_info: Dict) -> str:
        if data is None or data.empty:
            return "요청하신 데이터를 조회할 수 없습니다."
        
        formatted_data = self._format_dataframe_simple(data)
        
        prompt = f"""당신은 DRT(수요응답형 교통) 데이터 분석 전문가입니다.

예시 1:
질문: 지난달 총 운행 건수는?
데이터: total_operations: 1,247, total_passengers: 3,891, active_stations: 45
답변: 지난달 총 운행 건수는 1,247건이며, 총 3,891명의 승객이 이용했고 45개 정류장이 활성화되었습니다.

예시 2:
질문: 평균 승객 수는?
데이터: avg_passengers: 3.2, total_passengers: 4,158
답변: 평균 승객 수는 3.2명이며, 총 승객 수는 4,158명으로 집계되었습니다.

질문: {question}
데이터: {formatted_data}
답변:"""
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            return formatted_data
    
    def _generate_qualitative_response(self, question: str, qualitative_answer: str) -> str:
        if not qualitative_answer:
            return "정성적 분석 결과를 가져올 수 없습니다."
        
        if len(qualitative_answer.strip()) < 500:
            return qualitative_answer.strip()
        
        prompt = f"""다음 내용을 2-3문장으로 간단히 요약해주세요:

{qualitative_answer}"""
        
        try:
            response = self.llm.invoke(prompt)
            if len(response) > len(qualitative_answer) or "-> " in response or "사용" in response[:20]:
                return qualitative_answer.strip()
            return response.strip()
        except Exception as e:
            return qualitative_answer.strip()
    
    def _generate_mixed_response(self, question: str, quantitative_data: pd.DataFrame, 
                               qualitative_answer: str, sql_info: Dict) -> str:
        
        data_text = ""
        if quantitative_data is not None and not quantitative_data.empty:
            data_text = self._format_dataframe_simple(quantitative_data)
        
        prompt = f"""당신은 DRT(수요응답형 교통) 통합 분석 전문가입니다.

예시 1:
질문: 지난달 승객 수와 DRT 효과를 분석해주세요.
데이터: total_passengers: 3,891, avg_passengers: 3.1
분석: DRT는 기존 대중교통 대비 30% 높은 승객 만족도를 보이며, 특히 교통소외지역 접근성이 크게 개선되었습니다.
답변: 지난달 총 3,891명이 DRT를 이용했으며(평균 3.1명), 이는 기존 대중교통 대비 30% 높은 승객 만족도와 교통소외지역 접근성 개선 효과를 보여줍니다.

예시 2:
질문: 운행 실적과 DRT 장점을 함께 설명해주세요.
데이터: total_operations: 1,247건
분석: DRT의 주요 장점은 문전수송과 수요 기반 유연 운행입니다.
답변: 지난 달 1,247건의 운행 실적을 기록했으며, DRT의 핵심 장점인 문전수송 서비스와 수요 기반 유연 운행을 통해 높은 서비스 품질을 제공했습니다.

질문: {question}
데이터: {data_text if data_text else "데이터 없음"}
분석: {qualitative_answer if qualitative_answer else "분석 없음"}
답변:"""
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            result = f"데이터: {data_text}\n"
            result += f"분석: {qualitative_answer}"
            return result
    
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
# 통합 스마트 RAG 시스템 - 대화형 기능 추가
# =============================================================================

class SmartRAGSystem:
    """
    통합 스마트 RAG 시스템 (Watson AI 기반) - 대화형 매개변수 수집 기능 추가
    """
    
    def __init__(self, papers_dir: str = "./papers/"):
        # 대화 컨텍스트 관리
        self.context = ConversationContext()
        self.parameter_extractor = ParameterExtractor()
        
        # 중복 방지를 위한 응답 캐시
        self.response_cache = {}
        
        # 예시 SQL 쿼리 (실제 테이블 구조에 맞게 수정 필요)
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
        
        # 컴포넌트 초기화
        self.classifier = QuestionClassifier(self.predefined_queries, self.parameter_extractor)
        self.quantitative_analyzer = QuantitativeAnalyzer(DB_CONFIG, self.predefined_queries)
        self.qualitative_analyzer = QualitativeAnalyzer()
        self.response_generator = ResponseGenerator()
        
        # 정성분석 시스템 초기화
        if not self.qualitative_analyzer.initialize(papers_dir):
            print("⚠️ 정성분석 시스템 초기화 실패 - 정량분석만 사용 가능")
    
    def answer_question(self, question: str) -> str:
        """질문에 대한 통합 분석 및 답변 (대화형 기능 포함)"""
        # 대화 히스토리에 추가
        self.context.add_message('user', question)
        
        # 캐시 확인 (대화형 질문은 캐싱하지 않음)
        question_key = question.strip().lower()
        if not self.context.waiting_for_params and question_key in self.response_cache:
            print("💾 캐시된 답변 반환")
            return self.response_cache[question_key]
        
        print(f"🔍 분석 중...")
        
        # 대화 컨텍스트가 매개변수를 기다리는 중인지 확인
        if self.context.waiting_for_params:
            return self._handle_parameter_collection(question)
        
        # 1. 질문 분류
        question_type, classification_info = self.classifier.classify_question(question, self.context)
        
        # 2. 불완전한 질문 처리
        if question_type == QuestionType.INCOMPLETE:
            self._setup_parameter_collection(classification_info)
            final_answer = self.response_generator.generate_final_response(
                question, question_type, classification_info=classification_info
            )
            self.context.add_message('assistant', final_answer)
            return final_answer
        
        # 3. 질문 유형별 처리
        quantitative_data = None
        qualitative_answer = None
        sql_info = None
        
        if question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]:
            # 동적 쿼리를 위한 매개변수 사용
            params = classification_info.get('extracted_params', {})
            query_type = classification_info.get('query_type', 'operation_count')
            quantitative_data, error, sql_info = self.quantitative_analyzer.analyze(
                question, params, query_type
            )
        
        if question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]:
            qualitative_answer = self.qualitative_analyzer.analyze(question)
        
        # 4. 최종 답변 생성
        final_answer = self.response_generator.generate_final_response(
            question, question_type, quantitative_data, qualitative_answer, sql_info, classification_info
        )
        
        # 답변 처리 및 캐시 저장
        if hasattr(final_answer, 'content'):
            result = final_answer.content
        else:
            result = str(final_answer)
            
        # 대화형이 아닌 완성된 질문만 캐싱
        if question_type != QuestionType.INCOMPLETE:
            self.response_cache[question_key] = result
            
        self.context.add_message('assistant', result)
        return result
    
    def _setup_parameter_collection(self, classification_info: Dict):
        """매개변수 수집 설정"""
        query_type = classification_info.get('suggested_query_type', 'operation_count')
        missing_params = classification_info.get('missing_params', ['region', 'start_date', 'end_date'])
        
        self.context.set_pending_query(query_type, missing_params)
    
    def _handle_parameter_collection(self, user_input: str) -> str:
        """사용자로부터 매개변수 수집 처리"""
        # 사용자 입력에서 매개변수 추출
        extracted_params = self.parameter_extractor.extract_parameters(user_input)
        
        # 추출된 매개변수 업데이트
        for param_name, value in extracted_params.items():
            self.context.update_param(param_name, value)
        
        # 아직 부족한 매개변수가 있는지 확인
        missing_params = self.context.get_missing_params()
        
        if missing_params:
            # 여전히 부족한 매개변수가 있음
            response = "추가 정보를 확인했습니다! 하지만 아직 더 필요한 정보가 있습니다:\n\n"
            
            for param in missing_params:
                if param == 'region':
                    response += "🏙️ **지역**: 어느 구나 시의 데이터인가요?\n"
                elif param == 'start_date':
                    response += "📅 **시작 날짜**: 언제부터의 데이터인가요?\n"
                elif param == 'end_date':
                    response += "📅 **종료 날짜**: 언제까지의 데이터인가요?\n"
            
            return response
        
        # 모든 매개변수가 수집됨 - 쿼리 실행
        print("✅ 모든 매개변수 수집 완료 - 데이터 조회 중...")
        
        # 정량 분석 실행
        quantitative_data, error, sql_info = self.quantitative_analyzer.analyze(
            "사용자 요청", self.context.collected_params, self.context.query_type
        )
        
        # 결과 생성
        if quantitative_data is not None:
            # 성공적으로 데이터를 조회함
            final_answer = self.response_generator.generate_final_response(
                "동적 쿼리 결과", QuestionType.QUANTITATIVE, 
                quantitative_data, None, sql_info
            )
        else:
            # 데이터 조회 실패
            final_answer = f"죄송합니다. 데이터 조회에 실패했습니다: {error}"
        
        # 컨텍스트 리셋
        self.context.reset()
        
        return final_answer

# =============================================================================
# 대화형 인터페이스 (업데이트됨)
# =============================================================================

def interactive_chat(rag_system: SmartRAGSystem):
    """대화형 채팅 인터페이스 - 매개변수 수집 기능 포함"""
    print("=" * 80)
    print("🤖 Watson AI 기반 스마트 DRT 분석 어시스턴트 (대화형 매개변수 수집 버전)")
    print("=" * 80)
    print("✨ 자동으로 질문을 분류하여 최적의 분석 방법을 선택합니다")
    print("📊 정량분석: PostgreSQL 데이터 기반")
    print("📚 정성분석: 논문/문서 기반 (Watson AI 모델)") 
    print("🔄 통합분석: 정량+정성 데이터 결합 (Watson AI 추론)")
    print("💬 대화형 매개변수 수집: 부족한 정보를 단계별로 수집")
    print("❌ 관련없는 질문: 정중히 안내")
    print("🎯 특징: Few-shot 프롬프팅으로 일관되고 전문적인 DRT 답변 제공!")
    print("\n종료하려면 'quit' 또는 '종료'를 입력하세요.")
    print("=" * 80)
    print("\n💡 **시작해보세요!**")
    print("예시: '어떤 운행건수를 찾아줘?' → 시스템이 단계별로 필요한 정보를 요청합니다!")
    
    while True:
        try:
            question = input("\n🔍 질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 이용해주셔서 감사합니다!")
                break
            
            if not question:
                continue
            
            print(f"\n{'='*60}")
            answer = rag_system.answer_question(question)
            print(f"\n🤖 답변:")
            print("="*60)
            print(answer)
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def main():
    """메인 함수"""
    try:
        # Watson AI 연결 확인
        if not credentials.api_key or not project_id:
            print("❌ Watson AI 자격증명이 설정되지 않았습니다.")
            print("환경변수 WATSONX_APIKEY와 WATSONX_PROJECT_ID를 설정해주세요.")
            return
        
        print(f"🚀 Watson AI 기반 스마트 RAG 시스템 초기화 중 (대화형 매개변수 수집 버전)...")
        print(f"📡 모델: {CHAT_MODEL}")
        print(f"🔗 임베딩: {EMBEDDING_MODEL}")
        print(f"🎯 특징: 대화형 매개변수 수집으로 정확한 데이터 분석 제공!")
        
        # 시스템 생성
        rag_system = SmartRAGSystem()
        
        # 대화형 모드
        interactive_chat(rag_system)
        
    except Exception as e:
        print(f"❌ 시스템 초기화 실패: {str(e)}")
        print("\n환경 설정을 확인하세요:")
        print("1. Watson AI 자격증명 (WATSONX_APIKEY, WATSONX_PROJECT_ID)")
        print("2. papers/ 폴더의 PDF 파일 존재 여부") 
        print("3. PostgreSQL 연결 설정")
        print("4. 필요한 패키지 설치 여부")

if __name__ == "__main__":
    main()