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
# 데이터베이스 스키마 정보 (SQL 생성용)
# =============================================================================

DATABASE_SCHEMA_PROMPT = """
당신은 PostgreSQL + TimescaleDB + PostGIS 전문 SQL 개발자입니다.
서울시 교통 데이터 분석을 위한 정확한 SQL 쿼리를 작성해야 합니다.

=== 데이터베이스 스키마 정보 ===

## 1. 기본 테이블 구조

### bus_stops (정류장 정보) - 20,590개
```sql
CREATE TABLE bus_stops (
    node_id VARCHAR(50) PRIMARY KEY,           -- 정류장ID (예: '103900057', '116900041') 
    node_name VARCHAR(200) NOT NULL,           -- 정류장명 (예: '강남역9번출구', '신분당선강남역', 'GS25', '철산교앞')
    node_num VARCHAR(20),                      -- 정류장번호 (예: '4659.0', '17560.0', '12499.0')
    coordinates_x DECIMAL(12, 8),              -- 경도
    coordinates_y DECIMAL(11, 8),              -- 위도
    coordinates GEOMETRY(POINT, 4326),         -- PostGIS 좌표
    is_active BOOLEAN DEFAULT TRUE             -- 사용여부
);
```

### spatial_mapping (정류장-구-동 관계) - 17,615개
```sql  
CREATE TABLE spatial_mapping (
    node_id VARCHAR(50) PRIMARY KEY,           -- 정류장ID (bus_stops.node_id와 연결)
    sgg_code VARCHAR(10) NOT NULL,             -- 구 코드 (예: '11680'=강남구, '11650'=서초구)
    sgg_name VARCHAR(50) NOT NULL,             -- 구명 (예: '강남구', '서초구', '종로구', '마포구')
    adm_code VARCHAR(20),                      -- 행정동 코드
    adm_name VARCHAR(100),                     -- 행정동명 (예: '삼성1동', '도곡1동', '역삼1동')
    is_seoul BOOLEAN DEFAULT TRUE              -- 서울시 소속 여부
);
```

### bus_routes (노선 정보)
```sql
CREATE TABLE bus_routes (
    route_id VARCHAR(50) PRIMARY KEY,          -- 노선ID
    route_name VARCHAR(100) NOT NULL,          -- 노선명
    route_type INTEGER NOT NULL,               -- 노선유형 (1:일반, 3:마을, 5:급행)
    start_point VARCHAR(100),                  -- 기점명
    end_point VARCHAR(100),                    -- 종점명
    is_operating BOOLEAN DEFAULT TRUE          -- 운행여부
);
```

## 2. 교통 이력 데이터 (TimescaleDB 하이퍼테이블)

### station_passenger_history (정류장별 승하차) - 13,136,256건
```sql
CREATE TABLE station_passenger_history (
    record_date DATE NOT NULL,                 -- 기준일자 (예: '2024-07-01')
    route_id VARCHAR(50) NOT NULL,             -- 노선ID  
    node_id VARCHAR(50) NOT NULL,              -- 정류장ID
    hour INTEGER NOT NULL,                     -- 시간 (0-23)
    route_name VARCHAR(100),                   -- 노선명
    station_name VARCHAR(200),                 -- 정류장명
    ride_passenger INTEGER DEFAULT 0,          -- 승차인원 (시간당)
    alight_passenger INTEGER DEFAULT 0,        -- 하차인원 (시간당)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (record_date, route_id, node_id, hour)
);
```

### section_passenger_history (구간별 승객수)
```sql
CREATE TABLE section_passenger_history (
    record_date DATE NOT NULL,                 -- 기준일자
    route_id VARCHAR(50) NOT NULL,             -- 노선ID
    from_node_id VARCHAR(50) NOT NULL,         -- 출발정류장ID
    to_node_id VARCHAR(50) NOT NULL,           -- 도착정류장ID  
    hour INTEGER NOT NULL,                     -- 시간 (0-23)
    passenger_count INTEGER DEFAULT NULL,      -- 해당 시간대 승객수
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
);
```

## 3. 집계 뷰 (Materialized Views)

### mv_district_monthly_traffic (구별 월간 교통량)
```sql
CREATE MATERIALIZED VIEW mv_district_monthly_traffic AS
SELECT 
    DATE_TRUNC('month', sph.record_date)::date as month_date,
    sm.sgg_code as district_code,
    sm.sgg_name as district_name,
    SUM(sph.ride_passenger) as total_ride,
    SUM(sph.alight_passenger) as total_alight,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic,
    COUNT(DISTINCT sm.node_id) as station_count
FROM station_passenger_history sph
INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sm.is_seoul = TRUE
GROUP BY DATE_TRUNC('month', sph.record_date), sm.sgg_code, sm.sgg_name;
```

## 4. 서울시 25개 구 목록 (정확한 한글명)
강남구, 강동구, 강북구, 강서구, 관악구, 광진구, 구로구, 금천구, 노원구, 도봉구, 
동대문구, 동작구, 마포구, 서대문구, 서초구, 성동구, 성북구, 송파구, 양천구, 
영등포구, 용산구, 은평구, 종로구, 중구, 중랑구

=== SQL 작성 규칙 ===

1. **JOIN 필수**: 정류장-구 관계는 반드시 spatial_mapping 테이블 경유
   ```sql
   FROM station_passenger_history sph
   INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id  
   INNER JOIN bus_stops bs ON sm.node_id = bs.node_id
   ```

2. **날짜 필터링**: record_date는 DATE 타입, 범위 검색 시 >= 와 < 사용
   ```sql
   WHERE sph.record_date >= '2024-07-01' 
     AND sph.record_date < '2024-08-01'  -- 7월 전체
   ```

3. **구/정류장 검색**: 한글 이름으로 정확히 매칭
   ```sql
   WHERE sm.sgg_name = '강남구'              -- 구 검색
   WHERE bs.node_name LIKE '%강남역%'        -- 정류장 검색  
   ```

4. **시간대 필터링**: hour 컬럼 사용 (0-23)
   ```sql
   WHERE sph.hour BETWEEN 6 AND 9           -- 출근시간
   WHERE sph.hour BETWEEN 18 AND 21         -- 퇴근시간
   ```

5. **집계 최적화**: 큰 데이터셋은 월별 집계 뷰 활용
   ```sql
   SELECT * FROM mv_district_monthly_traffic 
   WHERE district_name = '강남구' AND month_date = '2024-07-01'
   ```

6. **TOP N 조회**: 정확한 LIMIT과 ORDER BY 사용
   ```sql
   ORDER BY SUM(ride_passenger + alight_passenger) DESC LIMIT 10
   ```

=== 주의사항 ===
- 모든 한글 구명/정류장명은 실제 데이터와 정확히 일치해야 함
- PostgreSQL 문법 준수 (MySQL이나 다른 DB 문법 사용 금지)
- 큰 데이터셋 조회 시 적절한 인덱스 활용
- 날짜/시간 범위 지정 시 성능 고려
- 집계 함수 사용 시 GROUP BY 절 필수

이제 다음 자연어 질문을 위의 스키마를 바탕으로 정확한 PostgreSQL 쿼리로 변환하세요.
오직 SQL 쿼리만 반환하고, 설명이나 다른 텍스트는 포함하지 마세요.

질문: """

# =============================================================================
# CoT 향상된 Watson AI LLM 래퍼 클래스 (기존과 동일)
# =============================================================================

class CoTEnhancedWatsonXLLM(LLM):
    """CoT(Chain of Thought) 기능이 강화된 Watson AI LLM 래퍼"""
    
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
            "temperature": 0.1 if enable_cot else 0.3
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
        try:
            if self.enable_cot and "단계별" not in prompt and "step-by-step" not in prompt:
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
        self.reasoning_steps = []
        if "1단계:" in response:
            steps = response.split("단계:")
            for i, step in enumerate(steps[1:], 1):
                clean_step = step.split("🔍📊🧠✅")[0].strip()
                if clean_step:
                    self.reasoning_steps.append(f"단계{i}: {clean_step[:100]}...")
    
    def get_reasoning_steps(self) -> List[str]:
        return self.reasoning_steps.copy()

# =============================================================================
# SQL 생성 전용 클래스
# =============================================================================

class SQLGeneratorLLM:
    """자연어를 SQL로 변환하는 전용 LLM 클래스"""
    
    def __init__(self):
        parameters = {
            "decoding_method": "greedy",
            "min_new_tokens": 10,
            "max_new_tokens": 1000,
            "temperature": 0.0  # SQL 생성은 일관성이 중요하므로 temperature = 0
        }
        
        self.model = ModelInference(
            model_id=CHAT_MODEL,
            params=parameters,
            credentials=credentials,
            project_id=project_id
        )
    
    def generate_sql(self, question: str) -> str:
        """자연어 질문을 SQL 쿼리로 변환"""
        try:
            full_prompt = DATABASE_SCHEMA_PROMPT + question
            print(f"🔍 SQL 생성 중: {question}")
            
            response = self.model.generate_text(prompt=full_prompt)
            
            # SQL 쿼리만 추출 (```sql이나 다른 마크다운 제거)
            sql_query = self._extract_sql_from_response(response)
            
            print(f"✅ 생성된 SQL: {sql_query[:100]}...")
            return sql_query
            
        except Exception as e:
            print(f"⚠️ SQL 생성 오류: {str(e)}")
            return None
    
    def _extract_sql_from_response(self, response: str) -> str:
        """응답에서 SQL 쿼리만 추출"""
        # 일반적인 마크다운 코드 블록 제거
        if "```sql" in response:
            sql_part = response.split("```sql")[1].split("```")[0]
        elif "```" in response:
            sql_part = response.split("```")[1].split("```")[0]
        else:
            sql_part = response
        
        # SQL 쿼리 정리
        sql_query = sql_part.strip()
        
        # 불필요한 설명문 제거
        lines = sql_query.split('\n')
        sql_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--') and not line.startswith('#'):
                sql_lines.append(line)
        
        return ' '.join(sql_lines)

# =============================================================================
# 향상된 정량 분석기 (SQL 생성 기반)
# =============================================================================

class EnhancedQuantitativeAnalyzer:
    """LLM을 활용한 동적 SQL 생성 기반 정량 분석기"""
    
    def __init__(self, db_config: Dict, llm: CoTEnhancedWatsonXLLM):
        self.db_config = db_config
        self.llm = llm
        self.sql_generator = SQLGeneratorLLM()
        self.engine = self._create_connection()
    
    def analyze_with_dynamic_sql(self, question: str) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict], str]:
        """동적 SQL 생성을 통한 정량 분석"""
        
        if not self.engine:
            return None, "데이터베이스 연결이 없습니다.", None, "DB 연결 실패"
        
        print(f"📊 동적 SQL 생성 기반 분석 시작...")
        
        # 1단계: LLM을 통한 SQL 생성
        generated_sql = self.sql_generator.generate_sql(question)
        
        if not generated_sql:
            return None, "SQL 쿼리 생성에 실패했습니다.", None, "SQL 생성 실패"
        
        # 2단계: SQL 검증 및 실행
        try:
            print(f"🔍 SQL 실행 중...")
            with self.engine.connect() as conn:
                result = conn.execute(text(generated_sql))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    return None, "조회 결과가 없습니다.", None, f"SQL 실행 성공하지만 결과 없음"
                
                sql_info = {
                    'sql': generated_sql,
                    'description': f"동적 생성된 SQL: {question}",
                    'confidence': 90  # SQL 생성 기반이므로 높은 신뢰도
                }
                
                # 3단계: 결과 해석
                interpretation = self._interpret_data_with_cot(question, df, sql_info)
                
                print(f"✅ 동적 SQL 실행 성공 - {len(df)}행 {len(df.columns)}열 데이터 조회")
                return df, None, sql_info, interpretation
                
        except Exception as e:
            error_msg = f"SQL 실행 오류: {str(e)}"
            error_analysis = self._analyze_sql_error(question, generated_sql, str(e))
            print(f"⚠️ {error_msg}")
            return None, error_msg, {'sql': generated_sql, 'error': str(e)}, error_analysis
    
    def _interpret_data_with_cot(self, question: str, data: pd.DataFrame, sql_info: Dict) -> str:
        """데이터 분석 결과에 대한 CoT 해석"""
        
        data_summary = self._create_data_summary(data)
        
        cot_prompt = f"""
DRT 데이터 분석 전문가로서 다음 분석 결과를 단계별로 해석해주세요:

원래 질문: "{question}"
실행된 SQL: {sql_info['sql'][:200]}...
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
            return f"📈 동적 SQL 기반 데이터 해석:\n{response}"
        except Exception as e:
            return f"📈 기본 데이터 해석: {data_summary}"
    
    def _analyze_sql_error(self, question: str, sql: str, error: str) -> str:
        """SQL 오류 분석"""
        
        error_prompt = f"""
PostgreSQL 전문가로서 다음 SQL 오류를 분석해주세요:

질문: "{question}"
실행된 SQL: {sql}
오류 메시지: {error}

🔍 1단계: 오류 유형 분류
- SQL 문법 오류, 테이블 접근 오류, 데이터 타입 오류 등을 구분합니다

📊 2단계: 원인 분석
- 오류가 발생한 구체적인 원인을 추정합니다
- 스키마나 권한 문제 가능성을 검토합니다

🧠 3단계: 해결 방안 제시
- 즉시 적용 가능한 해결책을 제안합니다
- SQL 쿼리 수정 방향을 제시합니다

✅ 4단계: 사용자 안내
간단한 오류 분석과 해결 방향을 제시합니다.
"""
        
        try:
            response = self.llm.invoke(error_prompt)
            return f"🔧 SQL 오류 분석:\n{response}"
        except Exception as e:
            return f"🔧 기본 오류 분석: SQL 실행 중 오류 발생 - {error}"
    
    def _create_data_summary(self, data: pd.DataFrame) -> str:
        """데이터 간단 요약 생성"""
        if data.empty:
            return "데이터 없음"
        
        summary_parts = [f"행수: {len(data)}", f"열수: {len(data.columns)}"]
        
        # 첫 번째 행의 주요 데이터 표시
        if len(data) > 0:
            first_row = data.iloc[0]
            for col, val in first_row.items():
                if pd.notna(val) and len(summary_parts) < 5:
                    if isinstance(val, (int, float)):
                        val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                    summary_parts.append(f"{col}: {val}")
        
        return ", ".join(summary_parts)
    
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
                print("✅ PostgreSQL 연결 성공!")
            return engine
        except Exception as e:
            print(f"⚠️ 데이터베이스 연결 실패: {str(e)}")
            return None

# =============================================================================
# 기존 클래스들 유지 (CoTQuestionClassifier, CoTQualitativeAnalyzer, CoTResponseGenerator)
# =============================================================================

class CoTQuestionClassifier:
    """CoT 기법을 적용한 질문 분류기"""
    
    def __init__(self, llm: CoTEnhancedWatsonXLLM):
        self.llm = llm
        
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
        basic_classification = self._basic_classify(question)
        
        if basic_classification == "uncertain":
            return self._cot_classify(question)
        
        return basic_classification, f"키워드 기반으로 {basic_classification.value}로 분류되었습니다."
    
    def _basic_classify(self, question: str) -> QuestionType:
        question_lower = question.lower()
        
        if self._contains_keywords(question_lower, self.irrelevant_keywords):
            return QuestionType.IRRELEVANT
        
        has_quantitative = self._contains_keywords(question_lower, self.quantitative_keywords)
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
            return "uncertain"
    
    def _cot_classify(self, question: str) -> Tuple[QuestionType, str]:
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
            classification = QuestionType.QUALITATIVE
            
        return classification, response
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)
    
    def _is_transport_related(self, question: str) -> bool:
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

class CoTQualitativeAnalyzer:
    """CoT가 향상된 정성 분석기"""
    
    def __init__(self, llm: CoTEnhancedWatsonXLLM):
        self.llm = llm
        self.rag_chain = None
        self.vectorstore = None
        self.processed_files_path = "./processed_files.json"
        self.processed_files_info = self._load_processed_files()
    
    def analyze_with_cot(self, question: str) -> Tuple[str, str]:
        if not self.rag_chain:
            return "정성분석 시스템이 초기화되지 않았습니다.", "시스템 오류"
        
        try:
            answer = self.rag_chain.invoke(question)
            reasoning_steps = self.llm.get_reasoning_steps()
            
            if hasattr(answer, 'content'):
                return answer.content, "\n".join(reasoning_steps)
            return str(answer), "\n".join(reasoning_steps)
        except Exception as e:
            return f"정성분석 오류: {str(e)}", f"오류 발생: {str(e)}"
    
    def initialize(self, papers_dir: str = "./papers/") -> bool:
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
        
        self.rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | cot_prompt
            | self.llm
            | StrOutputParser()
        )
        
        print("🧠 CoT 강화 RAG 체인 파이프라인 구성 완료")
        print("✅ CoT 정성분석 RAG 시스템 준비 완료!")
        return True
    
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

class CoTResponseGenerator:
    """CoT 추론이 강화된 최종 응답 생성기"""
    
    def __init__(self, llm: CoTEnhancedWatsonXLLM):
        self.llm = llm
    
    def generate_final_response_with_cot(self, question: str, question_type: QuestionType,
                                       quantitative_data: Optional[pd.DataFrame] = None,
                                       quantitative_reasoning: Optional[str] = None,
                                       qualitative_answer: Optional[str] = None,
                                       qualitative_reasoning: Optional[str] = None,
                                       sql_info: Optional[Dict] = None) -> Tuple[str, str]:
        
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
        
        if data is None or data.empty:
            return "요청하신 데이터를 조회할 수 없습니다.", reasoning or "데이터 없음"
        
        formatted_data = self._format_dataframe_simple(data)
        
        cot_prompt = f"""
DRT 데이터 분석 전문가로서 다음 정량분석 결과를 단계별로 해석하여 답변해주세요:

질문: "{question}"
분석된 데이터: {formatted_data}
분석 과정: {reasoning or "동적 SQL 생성 기반 분석"}

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
            full_reasoning = f"📊 동적 SQL 기반 정량분석 추론과정:\n{reasoning}\n\n🧠 CoT 해석과정:\n{response}"
            
            if "최종 답변" in response:
                final_answer = response.split("최종 답변")[-1].strip().strip(":")
            else:
                final_answer = response.strip()
                
            return final_answer, full_reasoning
            
        except Exception as e:
            simple_answer = f"데이터 조회 결과: {formatted_data}"
            return simple_answer, reasoning or "동적 SQL 기반 분석"
    
    def _generate_qualitative_response_with_cot(self, question: str, qualitative_answer: Optional[str], 
                                              reasoning: Optional[str]) -> Tuple[str, str]:
        
        if not qualitative_answer:
            return "정성적 분석 결과를 가져올 수 없습니다.", reasoning or "분석 실패"
        
        if len(qualitative_answer.strip()) < 500:
            return qualitative_answer.strip(), reasoning or "RAG 분석 완료"
        
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
{quantitative_reasoning or "동적 SQL 기반 정량분석"}

📚 정성분석:  
{qualitative_reasoning or "정성분석 없음"}

🧠 CoT 통합과정:
{response}
"""
            
            if "통합 답변" in response:
                final_answer = response.split("통합 답변")[-1].strip().strip(":")
            else:
                final_answer = response.strip()
                
            return final_answer, full_reasoning
            
        except Exception as e:
            result_parts = []
            if data_text:
                result_parts.append(f"정량분석: {data_text}")
            if qualitative_answer:
                result_parts.append(f"정성분석: {qualitative_answer[:100]}...")
            
            basic_answer = "\n\n".join(result_parts)
            basic_reasoning = f"정량: {quantitative_reasoning}\n정성: {qualitative_reasoning}"
            
            return basic_answer, basic_reasoning
    
    def _generate_irrelevant_response(self) -> Tuple[str, str]:
        response = """죄송합니다. 저는 DRT(수요응답형 교통) 및 교통 시스템 분야 전문 분석 어시스턴트입니다.

교통, DRT, 모빌리티, 대중교통 관련 질문을 해주시면 정량적 데이터 분석과 정성적 연구 자료를 바탕으로 전문적인 답변을 드리겠습니다.

예시 질문:
- 지난달 운행 건수는?
- DRT의 장점은 무엇인가요?
- 수요응답형 교통 시스템은 어떻게 작동하나요?"""
        
        reasoning = "질문 분류 결과: 교통/DRT와 관련 없는 질문으로 판단되어 안내 메시지를 제공합니다."
        
        return response, reasoning
    
    def _format_dataframe_simple(self, df: pd.DataFrame) -> str:
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
# CoT 통합 스마트 RAG 시스템 (Enhanced)
# =============================================================================

class EnhancedCoTSmartRAGSystem:
    """동적 SQL 생성이 통합된 향상된 CoT RAG 시스템"""
    
    def __init__(self, papers_dir: str = "./papers/", enable_cot: bool = True):
        print(f"🧠 Enhanced CoT {'활성화' if enable_cot else '비활성화'} 모드로 시스템 초기화")
        print("🔥 동적 SQL 생성 기능 활성화!")
        
        self.enable_cot = enable_cot
        self.response_cache = {}
        
        # CoT 강화된 컴포넌트들 초기화 (동적 SQL 생성 포함)
        self.llm = CoTEnhancedWatsonXLLM(enable_cot=enable_cot)
        self.classifier = CoTQuestionClassifier(self.llm)
        self.quantitative_analyzer = EnhancedQuantitativeAnalyzer(DB_CONFIG, self.llm)  # 새로운 분석기
        self.qualitative_analyzer = CoTQualitativeAnalyzer(self.llm)
        self.response_generator = CoTResponseGenerator(self.llm)
        
        # 정성분석 시스템 초기화
        if not self.qualitative_analyzer.initialize(papers_dir):
            print("⚠️ 정성분석 시스템 초기화 실패 - 정량분석만 사용 가능")
    
    def answer_question_with_cot(self, question: str) -> Dict[str, Any]:
        """CoT가 적용된 질문 분석 및 답변 생성 (동적 SQL 생성 포함)"""
        
        # 캐시 확인
        question_key = question.strip().lower()
        if question_key in self.response_cache:
            print("💾 캐시된 답변 반환")
            return self.response_cache[question_key]
        
        print(f"🧠 Enhanced CoT + 동적 SQL 생성 기반 종합 분석 시작...")
        
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
            print("📊 2a단계: 동적 SQL 생성 기반 정량분석 중...")
            quantitative_data, quantitative_error, sql_info, quantitative_reasoning = \
                self.quantitative_analyzer.analyze_with_dynamic_sql(question)
        
        if question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]:
            print("📚 2b단계: CoT 정성분석 중...")
            if self.enable_cot:
                qualitative_answer, qualitative_reasoning = \
                    self.qualitative_analyzer.analyze_with_cot(question)
            else:
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
            'cot_enabled': self.enable_cot,
            'dynamic_sql_enabled': True,  # 동적 SQL 생성 활성화 표시
            'sql_info': sql_info  # SQL 정보 추가
        }
        
        # 캐시 저장
        self.response_cache[question_key] = result
        return result
    
    def _basic_qualitative_analysis(self, question: str) -> str:
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
        confidence = 0.5  # 기본값
        
        if question_type == QuestionType.IRRELEVANT:
            confidence = 0.9
        elif question_type == QuestionType.QUANTITATIVE:
            if quantitative_data is not None and not quantitative_data.empty:
                confidence = 0.9  # 동적 SQL 생성 기반이므로 높은 신뢰도
                if sql_info and 'error' not in sql_info:
                    confidence = 0.95
        elif question_type == QuestionType.QUALITATIVE:
            if qualitative_answer and len(qualitative_answer.strip()) > 50:
                confidence = 0.75
        elif question_type == QuestionType.MIXED:
            data_conf = 0.45 if quantitative_data is not None else 0.0
            qual_conf = 0.35 if qualitative_answer else 0.0
            confidence = min(0.9, 0.2 + data_conf + qual_conf)
        
        return round(confidence, 2)
    
    def _get_analysis_type_description(self, question_type: QuestionType) -> str:
        descriptions = {
            QuestionType.IRRELEVANT: "관련없는 질문 - 안내메시지 제공",
            QuestionType.QUANTITATIVE: "정량분석 - 동적 SQL 생성 기반 데이터베이스 분석",
            QuestionType.QUALITATIVE: "정성분석 - 문서 기반 개념 및 이론 분석", 
            QuestionType.MIXED: "통합분석 - 동적 SQL 데이터 + 정성분석 결합"
        }
        return descriptions.get(question_type, "알 수 없는 분석 유형")

# =============================================================================
# 대화형 인터페이스 (Enhanced)
# =============================================================================

def interactive_chat_with_enhanced_cot(rag_system: EnhancedCoTSmartRAGSystem):
    """동적 SQL 생성이 통합된 Enhanced CoT 대화형 채팅 인터페이스"""
    print("=" * 80)
    print("🔥 Enhanced CoT + 동적 SQL 생성 Watson AI 기반 스마트 DRT 분석 어시스턴트")
    print("=" * 80)
    print("✨ Chain of Thought 추론으로 투명하고 해석가능한 분석을 제공합니다")
    print("🔍 단계별 추론 과정을 통해 더 신뢰할 수 있는 답변을 생성합니다")
    print("🔥 동적 SQL 생성: 자연어 질문을 실시간 SQL로 변환하여 데이터베이스 조회")
    print("📊 정량분석: 실제 서울시 교통 데이터 + CoT 해석")
    print("📚 정성분석: 논문/문서 기반 RAG + CoT 추론")
    print("🔄 통합분석: 동적 SQL 데이터 + 정성 분석을 CoT로 논리적 결합")
    print("⚠️ 관련없는 질문: CoT 분류로 정확한 안내")
    print("🎯 특징: 모든 답변에 추론 과정과 신뢰도 점수 제공!")
    print("\n명령어:")
    print("- 'reasoning': 마지막 답변의 상세 추론과정 보기")
    print("- 'confidence': 마지막 답변의 신뢰도 정보 보기") 
    print("- 'sql': 마지막 정량분석에서 사용된 SQL 쿼리 보기")
    print("- 'cot on/off': CoT 모드 전환")
    print("- 'quit' 또는 '종료': 프로그램 종료")
    print("=" * 80)
    
    last_result = None
    
    while True:
        try:
            question = input(f"\n🔍 질문 (Enhanced CoT + 동적 SQL: {'ON' if rag_system.enable_cot else 'OFF'}): ").strip()
            
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
                print(f"동적 SQL: {'예' if last_result.get('dynamic_sql_enabled', False) else '아니오'}")
                print("="*60)
                continue
            
            if question.lower() == 'sql' and last_result:
                print(f"\n{'='*60}")
                print("🔍 사용된 SQL 쿼리:")
                print("="*60)
                sql_info = last_result.get('sql_info')
                if sql_info and 'sql' in sql_info:
                    print(f"SQL: {sql_info['sql']}")
                    print(f"설명: {sql_info.get('description', 'N/A')}")
                else:
                    print("정량분석이 수행되지 않았거나 SQL 정보가 없습니다.")
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
            print("🔥 Enhanced CoT + 동적 SQL 분석 진행 중...")
            
            result = rag_system.answer_question_with_cot(question)
            last_result = result
            
            print(f"\n🤖 최종 답변 (신뢰도: {result['confidence']:.0%}):")
            print("="*60)
            print(result['answer'])
            print("="*60)
            print(f"📋 분석유형: {result['analysis_type']}")
            if result.get('dynamic_sql_enabled'):
                print("🔥 동적 SQL 생성 활성화")
            if rag_system.enable_cot:
                print("💡 상세 추론과정을 보려면 'reasoning' 입력")
                print("📊 신뢰도 상세정보를 보려면 'confidence' 입력")
                print("🔍 사용된 SQL을 보려면 'sql' 입력")
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n⚠️ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def main():
    """Enhanced CoT 메인 함수"""
    try:
        if not credentials.api_key or not project_id:
            print("⚠️ Watson AI 자격증명이 설정되지 않았습니다.")
            print("환경변수 WATSONX_APIKEY와 WATSONX_PROJECT_ID를 설정해주세요.")
            return
        
        print(f"🚀 Enhanced CoT + 동적 SQL 생성 Watson AI 기반 스마트 RAG 시스템 초기화 중...")
        print(f"🧠 Chain of Thought: 활성화")
        print(f"🔥 동적 SQL 생성: 활성화")
        print(f"🔡 모델: {CHAT_MODEL}")
        print(f"🔗 임베딩: {EMBEDDING_MODEL}")
        print(f"🎯 특징: 자연어→SQL 변환 + 단계별 추론으로 완전 자동화된 데이터 분석!")
        
        # Enhanced CoT 시스템 생성
        enhanced_rag_system = EnhancedCoTSmartRAGSystem(enable_cot=True)
        
        # 대화형 모드
        interactive_chat_with_enhanced_cot(enhanced_rag_system)
        
    except Exception as e:
        print(f"⚠️ 시스템 초기화 실패: {str(e)}")
        print("\n환경 설정을 확인하세요:")
        print("1. Watson AI 자격증명 (WATSONX_APIKEY, WATSONX_PROJECT_ID)")
        print("2. papers/ 폴더의 PDF 파일 존재 여부")
        print("3. PostgreSQL 연결 설정") 
        print("4. 필요한 패키지 설치 여부")

if __name__ == "__main__":
    main()