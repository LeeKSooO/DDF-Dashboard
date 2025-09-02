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
from sqlalchemy import create_engine, text, inspect
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
            "min_new_tokens": 5,           # 최소 5토큰 생성
            "max_new_tokens": 300,         # SQL만 생성하므로 짧게
            "temperature": 0.0,            # 완전 결정적 생성
            "repetition_penalty": 1.1      # 반복 방지
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
# 데이터베이스 스키마 탐색기 클래스
# =============================================================================

class DatabaseSchemaExplorer:
    """
    데이터베이스 스키마 정보를 탐색하고 text-to-SQL 생성을 위한 컨텍스트를 제공하는 클래스
    """
    
    def __init__(self, db_config: Dict):
        """
        스키마 탐색기 초기화
        
        Args:
            db_config (Dict): PostgreSQL 연결 설정
        """
        self.db_config = db_config
        self.engine = self._create_connection()
        self.schema_cache = {}
    
    def _create_connection(self):
        """데이터베이스 연결 생성"""
        try:
            connection_string = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            )
            engine = create_engine(connection_string)
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("✅ 데이터베이스 스키마 탐색기 연결 성공!")
            
            return engine
            
        except Exception as e:
            print(f"❌ 데이터베이스 연결 실패: {str(e)}")
            return None
    
    def get_database_schema(self) -> str:
        """
        데이터베이스의 전체 스키마 정보를 문자열로 반환
        
        Returns:
            str: 테이블과 컬럼 정보를 포함한 스키마 문자열
        """
        if not self.engine:
            return "데이터베이스 연결이 없습니다."
        
        if "full_schema" in self.schema_cache:
            return self.schema_cache["full_schema"]
        
        try:
            inspector = inspect(self.engine)
            schema_info = []
            
            # 모든 테이블 정보 수집
            tables = inspector.get_table_names()
            
            for table in tables:
                columns = inspector.get_columns(table)
                schema_info.append(f"테이블: {table}")
                
                for column in columns:
                    col_info = f"  - {column['name']}: {column['type']}"
                    if not column.get('nullable', True):
                        col_info += " (NOT NULL)"
                    schema_info.append(col_info)
                
                schema_info.append("")  # 테이블 간 구분
            
            schema_text = "\n".join(schema_info)
            self.schema_cache["full_schema"] = schema_text
            
            print(f"📊 데이터베이스 스키마 정보 로드 완료 - {len(tables)}개 테이블")
            return schema_text
            
        except Exception as e:
            error_msg = f"스키마 정보 수집 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def get_sample_data(self, table_name: str, limit: int = 3) -> str:
        """
        특정 테이블의 샘플 데이터를 반환
        
        Args:
            table_name (str): 테이블 이름
            limit (int): 가져올 행 수
            
        Returns:
            str: 샘플 데이터 문자열
        """
        if not self.engine:
            return "데이터베이스 연결이 없습니다."
        
        cache_key = f"sample_{table_name}_{limit}"
        if cache_key in self.schema_cache:
            return self.schema_cache[cache_key]
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    sample_text = f"테이블 {table_name}에 데이터가 없습니다."
                else:
                    sample_text = f"테이블 {table_name} 샘플 데이터:\n{df.to_string(index=False)}"
                
                self.schema_cache[cache_key] = sample_text
                return sample_text
                
        except Exception as e:
            error_msg = f"샘플 데이터 조회 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

# =============================================================================
# Text-to-SQL 생성기 클래스
# =============================================================================

class TextToSQLGenerator:
    """
    자연어 질문을 SQL 쿼리로 변환하는 클래스
    """
    
    def __init__(self, schema_explorer: DatabaseSchemaExplorer):
        """
        Text-to-SQL 생성기 초기화
        
        Args:
            schema_explorer (DatabaseSchemaExplorer): 데이터베이스 스키마 탐색기
        """
        self.schema_explorer = schema_explorer
        self.llm = WatsonXLLM()
    
    def generate_sql(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        """
        자연어 질문을 SQL 쿼리로 변환
        
        Args:
            question (str): 자연어 질문
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (생성된 SQL, 에러 메시지)
        """
        schema_info = self.schema_explorer.get_database_schema()
        
        prompt = f"""PostgreSQL 전문가로서 주어진 스키마를 바탕으로 자연어 질문을 SQL 쿼리로 변환하세요.

스키마:
{schema_info}

중요 규칙:
- PostgreSQL 문법 사용
- SELECT 문만 생성 (INSERT/UPDATE/DELETE 금지)
- 정확한 테이블명과 컬럼명 사용
- 날짜는 DATE_TRUNC, CURRENT_DATE 사용
- SQL 쿼리만 반환 (설명 금지)
- 세미콜론(;) 없이 작성

예시:
질문: "지난달 총 운행 건수는?"
답변: SELECT COUNT(*) as total_operations FROM station_passenger_history WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND record_date < DATE_TRUNC('month', CURRENT_DATE)

질문: {question}
답변:"""
        
        try:
            print("🔄 자연어를 SQL로 변환 중...")
            response = self.llm.invoke(prompt)
            
            # 응답에서 SQL 쿼리만 추출 (```sql 태그 제거 등)
            sql_query = self._clean_sql_response(response)
            
            if not sql_query or sql_query.strip().lower().startswith(('insert', 'update', 'delete', 'drop', 'create', 'alter')):
                return None, "안전하지 않은 SQL 쿼리가 생성되었습니다."
            
            print(f"✅ SQL 생성 완료: {sql_query[:100]}...")
            return sql_query, None
            
        except Exception as e:
            error_msg = f"SQL 생성 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg
    
    def _clean_sql_response(self, response: str) -> str:
        """
        LLM 응답에서 SQL 쿼리만 추출하여 정리
        
        Args:
            response (str): LLM 응답
            
        Returns:
            str: 정리된 SQL 쿼리
        """
        # 공통 패턴들 제거
        cleaned = response.strip()
        
        # 중복/반복 패턴 제거: "질문:" 이후 모든 내용 제거
        if "질문:" in cleaned:
            cleaned = cleaned.split("질문:")[0].strip()
        
        # "답변:" 또는 "SQL:" 이후의 첫 번째 SQL문만 추출
        if "답변:" in cleaned:
            sql_parts = cleaned.split("답변:")
            if len(sql_parts) > 1:
                cleaned = sql_parts[1].strip()
        elif "SQL:" in cleaned:
            sql_parts = cleaned.split("SQL:")
            if len(sql_parts) > 1:
                cleaned = sql_parts[1].strip()
        
        # 다음 "질문:" 또는 "답변:" 전까지만 추출
        if "질문:" in cleaned:
            cleaned = cleaned.split("질문:")[0].strip()
        if "답변:" in cleaned and cleaned.count("답변:") > 0:
            cleaned = cleaned.split("답변:")[0].strip()
        
        # ```sql ``` 태그 제거
        if "```sql" in cleaned:
            cleaned = cleaned.split("```sql")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].strip()
        
        # 마지막 세미콜론 제거
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()
        
        # 여러 줄을 한 줄로 정리
        cleaned = " ".join(cleaned.split())
        
        # SELECT로 시작하지 않으면 SELECT 부분 찾기
        cleaned_upper = cleaned.upper()
        if not cleaned_upper.startswith("SELECT"):
            select_pos = cleaned_upper.find("SELECT")
            if select_pos != -1:
                cleaned = cleaned[select_pos:].strip()
        
        return cleaned

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
    """
    IRRELEVANT = "irrelevant"      # 관련없는 질문
    QUANTITATIVE = "quantitative"  # 정량분석 질문
    QUALITATIVE = "qualitative"    # 정성분석 질문
    MIXED = "mixed"               # 통합분석 질문

class QuestionClassifier:
    """
    사용자 질문을 4가지 유형으로 자동 분류하는 클래스 (Text-to-SQL 버전)
    """
    
    def __init__(self):
        """질문 분류기 초기화"""
        
        # 정량분석 관련 키워드 (숫자, 통계, 데이터 분석 관련)
        self.quantitative_keywords = [
            "얼마나", "몇", "수", "통계", "데이터", "평균", "총", "최대", "최소",
            "비율", "퍼센트", "%", "건수", "횟수", "개수", "명", "시간대",
            "운행", "승객", "정류장", "노선", "이용률", "효율성", "실적", "조회"
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
        
    def classify_question(self, question: str) -> QuestionType:
        """
        질문을 4가지 유형으로 자동 분류합니다.
        
        Args:
            question (str): 분류할 사용자 질문
            
        Returns:
            QuestionType: 분류된 질문 유형
        """
        question_lower = question.lower()
        
        # 1단계: 관련없는 질문 체크 (최우선)
        if self._is_irrelevant(question_lower):
            return QuestionType.IRRELEVANT
        
        # 2단계: 정량분석 가능한 질문인지 체크
        has_quantitative = self._contains_keywords(question_lower, self.quantitative_keywords)
        
        # 3단계: 정성분석이 필요한 질문인지 체크
        has_qualitative = self._contains_keywords(question_lower, self.qualitative_keywords)
        
        # 4단계: 분류 결정 로직
        if has_quantitative and has_qualitative:
            return QuestionType.MIXED        # 정량+정성 모두 필요
        elif has_quantitative:
            return QuestionType.QUANTITATIVE # 정량분석만 필요
        elif has_qualitative:
            return QuestionType.QUALITATIVE  # 정성분석만 필요
        else:
            # 5단계: 키워드 매칭 실패시 교통 관련성으로 최종 판단
            if self._is_transport_related(question_lower):
                return QuestionType.QUALITATIVE  # 교통 관련은 정성분석으로
            else:
                return QuestionType.IRRELEVANT   # 완전히 관련없음
    
    def _is_irrelevant(self, question: str) -> bool:
        """관련없는 질문인지 확인"""
        return self._contains_keywords(question, self.irrelevant_keywords)
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """텍스트에 지정된 키워드가 포함되어 있는지 확인"""
        return any(keyword in text for keyword in keywords)
    
    def _is_transport_related(self, question: str) -> bool:
        """교통/DRT 관련 질문인지 확인"""
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

# =============================================================================
# 정량 분석 시스템 (Text-to-SQL 기반)
# =============================================================================

class QuantitativeAnalyzer:
    """
    Text-to-SQL을 활용한 정량적 분석을 수행하는 클래스
    """
    
    def __init__(self, db_config: Dict):
        """
        정량분석기 초기화
        
        Args:
            db_config (Dict): PostgreSQL 연결 설정
        """
        self.db_config = db_config
        self.engine = self._create_connection()
        self.schema_explorer = DatabaseSchemaExplorer(db_config)
        self.sql_generator = TextToSQLGenerator(self.schema_explorer)
    
    def _create_connection(self):
        """PostgreSQL 데이터베이스 연결 생성"""
        try:
            connection_string = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            )
            
            engine = create_engine(connection_string)
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("✅ 정량분석 PostgreSQL 연결 성공!")
            
            return engine
            
        except Exception as e:
            print(f"❌ 데이터베이스 연결 실패: {str(e)}")
            print("🔧 연결 설정을 확인하세요:")
            print(f"   - 호스트: {self.db_config['host']}:{self.db_config['port']}")
            print(f"   - 데이터베이스: {self.db_config['database']}")
            print(f"   - 사용자: {self.db_config['user']}")
            return None
    
    def analyze(self, question: str) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
        """
        사용자 질문에 대한 정량적 분석을 수행합니다. (Text-to-SQL 사용)
        
        Args:
            question (str): 분석할 사용자 질문
            
        Returns:
            Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
                - DataFrame: 쿼리 실행 결과 (성공시)
                - str: 에러 메시지 (실패시)
                - Dict: SQL 정보
        """
        # 1. 데이터베이스 연결 확인
        if not self.engine:
            return None, "데이터베이스 연결이 없습니다.", None
        
        # 2. Text-to-SQL을 사용하여 SQL 쿼리 생성
        sql_query, error = self.sql_generator.generate_sql(question)
        
        if error or not sql_query:
            return None, error or "SQL 쿼리를 생성할 수 없습니다.", None
        
        print(f"📊 생성된 SQL로 데이터 조회 중...")
        
        # 3. 생성된 SQL 실행
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_query))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    return None, "조회 결과가 없습니다.", {
                        "sql": sql_query,
                        "description": "동적 생성된 SQL 쿼리",
                        "source": "text-to-sql"
                    }
                
                print(f"✅ SQL 실행 성공 - {len(df)}행 {len(df.columns)}열 데이터 조회")
                return df, None, {
                    "sql": sql_query,
                    "description": "동적 생성된 SQL 쿼리",
                    "source": "text-to-sql"
                }
                
        except Exception as e:
            error_msg = f"SQL 실행 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg, {
                "sql": sql_query,
                "description": "동적 생성된 SQL 쿼리 (실행 실패)",
                "source": "text-to-sql",
                "error": str(e)
            }

class QualitativeAnalyzer:
    """
    정성 분석 (Vector DB with Watson AI)
    
    주요 기능:
    - PDF 문서를 로드하고 청킹하여 벡터 데이터베이스에 저장
    - 이미 처리된 파일들을 추적하여 중복 처리 방지
    - RAG 체인을 통한 정성적 질문 분석
    - 벡터 데이터베이스 재사용으로 성능 최적화
    """
    
    def __init__(self):
        self.rag_chain = None
        self.vectorstore = None
        self.processed_files_path = "./processed_files.json"  # 처리된 파일 추적용
        self.processed_files_info = self._load_processed_files()
    
    def _load_processed_files(self) -> Dict:
        """
        이전에 처리된 파일 정보를 로드합니다.
        
        Returns:
            Dict: 파일명을 키로 하고 처리 정보(해시, 날짜 등)를 값으로 가지는 딕셔너리
        """
        try:
            if os.path.exists(self.processed_files_path):
                with open(self.processed_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 로드 실패: {e}")
        return {}
    
    def _save_processed_files(self):
        """
        처리된 파일 정보를 저장합니다.
        """
        try:
            with open(self.processed_files_path, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 처리된 파일 정보 저장 실패: {e}")
    
    def _get_file_hash(self, filepath: str) -> str:
        """
        파일의 MD5 해시를 계산합니다.
        
        Args:
            filepath (str): 해시를 계산할 파일 경로
            
        Returns:
            str: 파일의 MD5 해시값
        """
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _is_file_changed(self, filepath: str) -> bool:
        """
        파일이 이전 처리 시점보다 변경되었는지 확인합니다.
        
        Args:
            filepath (str): 확인할 파일 경로
            
        Returns:
            bool: 파일이 변경되었거나 새 파일이면 True
        """
        filename = os.path.basename(filepath)
        current_hash = self._get_file_hash(filepath)
        
        if filename not in self.processed_files_info:
            return True  # 새 파일
        
        stored_hash = self.processed_files_info[filename].get('hash', '')
        return current_hash != stored_hash
    
    def _update_processed_file_info(self, filepath: str, doc_count: int):
        """
        처리된 파일 정보를 업데이트합니다.
        
        Args:
            filepath (str): 처리된 파일 경로
            doc_count (int): 추출된 문서 수
        """
        filename = os.path.basename(filepath)
        self.processed_files_info[filename] = {
            'hash': self._get_file_hash(filepath),
            'processed_date': datetime.now().isoformat(),
            'document_count': doc_count,
            'file_size': os.path.getsize(filepath)
        }
    
    def initialize(self, papers_dir: str = "./papers/"):
        """
        RAG 시스템을 초기화합니다.
        
        이 메서드는 다음 단계를 수행합니다:
        1. Papers 디렉터리 검증
        2. 기존 벡터 데이터베이스 확인 및 재사용 여부 결정
        3. 새로운 또는 변경된 문서만 처리
        4. 벡터 데이터베이스 생성 또는 업데이트
        5. RAG 체인 구성
        
        Args:
            papers_dir (str): PDF 문서가 저장된 디렉터리 경로
            
        Returns:
            bool: 초기화 성공 여부
        """
        print("📚 정성분석용 RAG 시스템 초기화 중...")
        
        # 1. Papers 디렉터리 검증
        if not self._validate_papers_directory(papers_dir):
            return False
        
        # 2. 벡터 데이터베이스 경로 설정
        vectorstore_path = f"./chroma_db_watson_{EMBEDDING_MODEL.replace('/', '_').replace('-', '_')}"
        
        # 3. HuggingFace 임베딩 초기화
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cuda'},
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 64}
        )
        
        # 4. 기존 벡터 데이터베이스 확인
        existing_vectorstore_exists = os.path.exists(vectorstore_path)
        
        if existing_vectorstore_exists:
            print(f"🔍 기존 벡터 데이터베이스 발견: {vectorstore_path}")
            try:
                # 기존 벡터 데이터베이스 로드 시도
                self.vectorstore = Chroma(
                    persist_directory=vectorstore_path,
                    embedding_function=embeddings
                )
                print("✅ 기존 벡터 데이터베이스 로드 성공")
                
                # 새로운 또는 변경된 문서 확인
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
            # 5. 새 벡터 데이터베이스 생성
            docs = self._load_documents(papers_dir)
            if not docs:
                print("❌ 문서를 로드할 수 없습니다.")
                return False
            
            print(f"📄 총 {len(docs)}개 문서를 벡터 데이터베이스로 변환 중...")
            
            # 텍스트 분할 (청킹)
            splits = self._split_documents(docs)
            print(f"✂️ 문서를 {len(splits)}개 청크로 분할 완료")
            
            # 기존 데이터베이스 폴더가 있다면 삭제
            if os.path.exists(vectorstore_path):
                shutil.rmtree(vectorstore_path)
                print(f"🗑️ 기존 손상된 벡터 데이터베이스 삭제: {vectorstore_path}")
            
            # 새 벡터 데이터베이스 생성
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=vectorstore_path
            )
            print(f"✅ 새 벡터 데이터베이스 생성 완료: {vectorstore_path}")
        
        # 6. 처리된 파일 정보 저장
        self._save_processed_files()
        
        # 7. 검색기 구성
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}  # 상위 6개 관련 청크 검색
        )
        print("🔍 문서 검색기 구성 완료 (유사도 기반, k=6)")
        
        # 8. Few-shot RAG 체인 구성
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
        
        # Watson AI LLM 사용
        llm = WatsonXLLM()
        print("🤖 Watson AI LLM 초기화 완료")
        
        def format_docs(docs):
            """
            검색된 문서들을 LLM이 이해하기 쉬운 형태로 포맷팅합니다.
            
            Args:
                docs: 검색된 문서 리스트
                
            Returns:
                str: 포맷팅된 컨텍스트 문자열
            """
            context = "\n\n---\n\n".join([
                f"[문서 {i+1}]\n{doc.page_content}"
                for i, doc in enumerate(docs)
            ])
            
            # 간단한 컨텍스트 정보 출력
            print(f"📚 {len(docs)}개 문서 참조")
            
            return context
        
        # RAG 체인 파이프라인 구성
        # 질문 -> 문서 검색 -> 컨텍스트 포맷팅 -> 프롬프트 구성 -> LLM 추론 -> 답변 파싱
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
        """
        Papers 디렉터리가 유효한지 검증합니다.
        
        Args:
            papers_dir (str): 검증할 디렉터리 경로
            
        Returns:
            bool: 디렉터리가 유효하면 True
        """
        # 절대 경로로 변환
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
        
        # PDF 파일 존재 여부 확인
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
        """
        새로운 또는 변경된 문서만 반환합니다.
        
        Args:
            directory_path (str): 문서 디렉터리 경로
            
        Returns:
            List: 새로운/변경된 문서 리스트
        """
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
        """
        새로운 문서들을 기존 벡터 데이터베이스에 추가합니다.
        
        Args:
            new_files (List[str]): 추가할 파일 경로 리스트
        """
        if not new_files:
            return
        
        # 새 문서들 로드
        new_docs = []
        for filepath in new_files:
            docs = self._load_single_document(filepath)
            if docs:
                new_docs.extend(docs)
                # 처리된 파일 정보 업데이트
                self._update_processed_file_info(filepath, len(docs))
        
        if new_docs:
            # 텍스트 분할
            splits = self._split_documents(new_docs)
            
            # 기존 벡터 데이터베이스에 추가
            self.vectorstore.add_documents(splits)
            print(f"✅ {len(splits)}개 새 청크를 벡터 데이터베이스에 추가 완료")
    
    def _split_documents(self, docs: List) -> List:
        """
        문서를 청크 단위로 분할합니다.
        
        청킹 전략:
        - chunk_size: 1500 (각 청크의 최대 문자 수)
        - chunk_overlap: 300 (인접한 청크 간 겹치는 문자 수)
        - separators: 문서 구조를 고려한 구분자 우선순위
        
        Args:
            docs (List): 분할할 문서 리스트
            
        Returns:
            List: 분할된 청크 리스트
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,      # 각 청크의 최대 문자 수
            chunk_overlap=300,    # 인접 청크 간 겹치는 문자 수
            separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""]  # 구분자 우선순위
        )
        return text_splitter.split_documents(docs)
    
    def _load_single_document(self, filepath: str) -> List:
        """
        단일 PDF 파일을 로드합니다.
        
        Args:
            filepath (str): 로드할 PDF 파일 경로
            
        Returns:
            List: 로드된 문서 리스트
        """
        docs = []
        filename = os.path.basename(filepath)
        
        # PyMuPDFLoader 시도 (더 빠르고 정확함)
        try:
            loader = PyMuPDFLoader(filepath)
            docs = loader.load()
            print(f"✅ PyMuPDF로 로드 성공: {filename} ({len(docs)}페이지)")
            return docs
        except Exception as e:
            print(f"⚠️ PyMuPDF 로드 실패: {filename} - {str(e)}")
        
        # PyPDFLoader 시도 (백업 로더)
        try:
            loader = PyPDFLoader(filepath)
            docs = loader.load()
            print(f"✅ PyPDF로 로드 성공: {filename} ({len(docs)}페이지)")
            return docs
        except Exception as e:
            print(f"❌ 모든 로더 실패: {filename} - {str(e)}")
        
        return []
    
    def _load_documents(self, directory_path: str) -> List:
        """
        디렉터리의 모든 PDF 문서를 로드합니다.
        
        이 메서드는 다음을 수행합니다:
        1. 디렉터리에서 모든 PDF 파일 탐색
        2. 각 파일에 대해 최적의 로더 선택 (PyMuPDF -> PyPDF)
        3. 로드 성공/실패 로그 출력
        4. 처리된 파일 정보 업데이트
        
        Args:
            directory_path (str): PDF 파일들이 있는 디렉터리 경로
            
        Returns:
            List: 로드된 모든 문서의 리스트
        """
        all_docs = []
        pdf_files = []
        
        # 1. 모든 PDF 파일 경로 수집
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"📚 총 {len(pdf_files)}개의 PDF 파일을 발견했습니다.")
        
        # 2. 각 PDF 파일 로드
        successful_loads = 0
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            docs = self._load_single_document(pdf_path)
            
            if docs:
                all_docs.extend(docs)
                successful_loads += 1
                # 처리된 파일 정보 업데이트
                self._update_processed_file_info(pdf_path, len(docs))
            else:
                print(f"❌ 로드 실패: {filename}")
        
        print(f"📊 로드 결과: {successful_loads}/{len(pdf_files)}개 파일 성공, 총 {len(all_docs)}개 문서")
        return all_docs

class ResponseGenerator:
    """
    최종 답변 생성기 (Watson AI 사용)
    """
    
    def __init__(self):
        self.llm = WatsonXLLM()
    
    def generate_final_response(self, question: str, question_type: QuestionType, 
                              quantitative_data: Optional[pd.DataFrame] = None, 
                              qualitative_answer: Optional[str] = None,
                              sql_info: Optional[Dict] = None) -> str:
        """최종 답변 생성"""
        
        if question_type == QuestionType.IRRELEVANT:
            return self._generate_irrelevant_response()
        
        elif question_type == QuestionType.QUANTITATIVE:
            return self._generate_quantitative_response(question, quantitative_data, sql_info)
        
        elif question_type == QuestionType.QUALITATIVE:
            return self._generate_qualitative_response(question, qualitative_answer)
        
        elif question_type == QuestionType.MIXED:
            return self._generate_mixed_response(question, quantitative_data, qualitative_answer, sql_info)
        
        else:
            return "죄송합니다. 질문을 처리할 수 없습니다."
    
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
        
        # 간결한 데이터 표시
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
        
        # RAG 답변이 이미 충분히 간결하다면 추가 요약 없이 바로 반환
        if len(qualitative_answer.strip()) < 500:  # 500자 이하면 바로 반환
            return qualitative_answer.strip()
        
        # 길 경우에만 간단한 요약 요청
        prompt = f"""다음 내용을 2-3문장으로 간단히 요약해주세요:

{qualitative_answer}"""
        
        try:
            response = self.llm.invoke(prompt)
            # 응답이 원본보다 길어지거나 이상하면 원본 그대로 반환
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
            # 단일 행 - 핵심 수치만 표시
            row = df.iloc[0]
            items = []
            for col, val in row.items():
                if pd.notna(val):
                    if isinstance(val, (int, float)):
                        val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                    items.append(f"{col}: {val}")
            return ", ".join(items[:3])  # 최대 3개 항목만
        else:
            # 여러 행 - 테이블 형태
            return df.head(3).to_string(index=False)  # 최대 3행만

class SmartRAGSystem:
    """
    통합 스마트 RAG 시스템 (Watson AI 기반 - Text-to-SQL 버전)
    """
    
    def __init__(self, papers_dir: str = "./papers/"):
        # 중복 방지를 위한 응답 캐시
        self.response_cache = {}
        
        # 기존 사전 정의된 SQL 쿼리들 (주석 처리 - 필요시 활성화 가능)
        # self.predefined_queries = {
        #     "지난달 총 운행건수는?": {
        #         "sql": """
        #             SELECT 
        #                 COUNT(*) as total_operations,
        #                 SUM(ride_passenger + alight_passenger) as total_passengers,
        #                 COUNT(DISTINCT node_id) as active_stations
        #             FROM station_passenger_history 
        #             WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
        #               AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
        #               AND (ride_passenger > 0 OR alight_passenger > 0)
        #         """,
        #         "description": "지난 달 총 운행 건수 및 승객 통계"
        #     },
        #     "평균 승객수는?": {
        #         "sql": """
        #             SELECT 
        #                 ROUND(AVG(ride_passenger + alight_passenger), 2) as avg_passengers,
        #                 SUM(ride_passenger + alight_passenger) as total_passengers
        #             FROM station_passenger_history 
        #             WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
        #               AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
        #         """,
        #         "description": "평균 승객수 통계"
        #     }
        # }
        
        # 컴포넌트 초기화 (Text-to-SQL 버전)
        self.classifier = QuestionClassifier()  # predefined_queries 제거
        self.quantitative_analyzer = QuantitativeAnalyzer(DB_CONFIG)  # predefined_queries 제거
        self.qualitative_analyzer = QualitativeAnalyzer()
        self.response_generator = ResponseGenerator()
        
        # 정성분석 시스템 초기화
        if not self.qualitative_analyzer.initialize(papers_dir):
            print("⚠️ 정성분석 시스템 초기화 실패 - 정량분석만 사용 가능")
    
    def answer_question(self, question: str) -> str:
        """질문에 대한 통합 분석 및 답변 (Text-to-SQL 사용)"""
        # 캐시 확인
        question_key = question.strip().lower()
        if question_key in self.response_cache:
            print("💾 캐시된 답변 반환")
            return self.response_cache[question_key]
        
        print(f"🔍 분석 중...")
        
        # 1. 질문 분류
        question_type = self.classifier.classify_question(question)
        
        # 2. 질문 유형별 처리
        quantitative_data = None
        qualitative_answer = None
        sql_info = None
        
        if question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]:
            quantitative_data, error, sql_info = self.quantitative_analyzer.analyze(question)
        
        if question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]:
            qualitative_answer = self.qualitative_analyzer.analyze(question)
        
        # 3. 최종 답변 생성
        final_answer = self.response_generator.generate_final_response(
            question, question_type, quantitative_data, qualitative_answer, sql_info
        )
        
        # 답변 처리 및 캐시 저장
        if hasattr(final_answer, 'content'):
            result = final_answer.content
        else:
            result = str(final_answer)
            
        self.response_cache[question_key] = result
        return result

def interactive_chat(rag_system: SmartRAGSystem):
    """대화형 채팅 인터페이스"""
    print("=" * 80)
    print("🤖 Watson AI 기반 스마트 DRT 분석 어시스턴트 (Text-to-SQL 버전)")
    print("=" * 80)
    print("✨ 자동으로 질문을 분류하여 최적의 분석 방법을 선택합니다")
    print("📊 정량분석: LLM 기반 Text-to-SQL로 동적 쿼리 생성")
    print("📚 정성분석: 논문/문서 기반 (Watson AI 모델)") 
    print("🔄 통합분석: 정량+정성 데이터 결합 (Watson AI 추론)")
    print("❌ 관련없는 질문: 정중히 안내")
    print("🎯 특징: 데이터베이스 스키마를 실시간 탐색하여 SQL 자동 생성!")
    print("\n종료하려면 'quit' 또는 '종료'를 입력하세요.")
    print("=" * 80)
    
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
            print(f"\n🤖 최종 답변:")
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
        
        print(f"🚀 Watson AI 기반 스마트 RAG 시스템 초기화 중 (Text-to-SQL 버전)...")
        print(f"📡 모델: {CHAT_MODEL}")
        print(f"🔗 임베딩: {EMBEDDING_MODEL}")
        print(f"🎯 특징: LLM 기반 Text-to-SQL로 데이터베이스 스키마를 실시간 탐색!")
        
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