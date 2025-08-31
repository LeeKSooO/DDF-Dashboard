import os
import logging
import shutil
import pandas as pd
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

# .env 파일 로드
load_dotenv(override=True)

# 새로운 chroma 패키지 사용 (없으면 기존 것 사용)
try:
    from langchain_chroma import Chroma
    print("새로운 langchain-chroma 패키지를 사용합니다.")
except ImportError:
    from langchain_community.vectorstores import Chroma
    print("기존 chroma 패키지를 사용합니다. 업그레이드를 권장합니다: pip install -U langchain-chroma")

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

# 로깅 레벨 설정
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# Watson AI 설정
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    api_key=os.getenv("WATSONX_APIKEY"),
)
project_id = os.getenv("WATSONX_PROJECT_ID")

# 모델 설정
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"  # HuggingFace 임베딩 사용
CHAT_MODEL = "ibm/granite-3-8b-instruct"  # Watson AI 모델

# PostgreSQL 연결 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ddf_db',
    'user': 'ddf_user',
    'password': 'ddf_password'
}

class WatsonXLLM(LLM):
    """Watson AI를 LangChain LLM으로 래핑하는 클래스"""
    
    model: Any = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 모델 파라미터 설정
        parameters = {
            "decoding_method": "greedy",
            "min_new_tokens": 10,
            "max_new_tokens": 2000,
            "temperature": 0.1
        }
        
        # Watson AI 모델 초기화
        self.model = ModelInference(
            model_id=CHAT_MODEL,
            params=parameters,
            credentials=credentials,
            project_id=project_id
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
        """Watson AI 모델 호출"""
        try:
            response = self.model.generate_text(prompt=prompt)
            return response
        except Exception as e:
            print(f"Watson AI 모델 호출 중 오류: {e}")
            return "죄송합니다. 모델 응답 생성 중 오류가 발생했습니다."

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
        
        # 1. 관련없는 질문 체크
        if self._is_irrelevant(question_lower):
            return QuestionType.IRRELEVANT
        
        # 2. 정량분석 가능한 질문인지 체크 (SQL 매칭)
        has_quantitative = self._has_sql_match(question) or self._contains_keywords(question_lower, self.quantitative_keywords)
        
        # 3. 정성분석이 필요한 질문인지 체크
        has_qualitative = self._contains_keywords(question_lower, self.qualitative_keywords)
        
        # 4. 분류 결정
        if has_quantitative and has_qualitative:
            return QuestionType.MIXED
        elif has_quantitative:
            return QuestionType.QUANTITATIVE
        elif has_qualitative:
            return QuestionType.QUALITATIVE
        else:
            # 키워드가 없어도 교통/DRT 관련이면 정성분석으로 처리
            if self._is_transport_related(question_lower):
                return QuestionType.QUALITATIVE
            else:
                return QuestionType.IRRELEVANT
    
    def _is_irrelevant(self, question: str) -> bool:
        """관련없는 질문인지 체크"""
        return self._contains_keywords(question, self.irrelevant_keywords)
    
    def _has_sql_match(self, question: str) -> bool:
        """SQL 매칭 가능한 질문인지 체크"""
        for mapped_question in self.predefined_queries.keys():
            similarity = fuzz.token_sort_ratio(question.lower(), mapped_question.lower())
            if similarity >= 60:  # 임계값
                return True
        return False
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """키워드 포함 여부 체크"""
        return any(keyword in text for keyword in keywords)
    
    def _is_transport_related(self, question: str) -> bool:
        """교통/DRT 관련 질문인지 체크"""
        transport_keywords = [
            "drt", "교통", "버스", "택시", "승객", "운행", "정류장", "노선",
            "대중교통", "수요응답", "모빌리티", "이동", "운송", "차량"
        ]
        return self._contains_keywords(question, transport_keywords)

class QuantitativeAnalyzer:
    """
    정량 분석 (PostgreSQL 데이터)
    """
    
    def __init__(self, db_config: Dict, predefined_queries: Dict):
        self.db_config = db_config
        self.predefined_queries = predefined_queries
        self.engine = self._create_connection()
    
    def _create_connection(self):
        """PostgreSQL 연결"""
        try:
            connection_string = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            engine = create_engine(connection_string)
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("✅ PostgreSQL 연결 성공!")
            
            return engine
        except Exception as e:
            print(f"❌ 데이터베이스 연결 실패: {str(e)}")
            return None
    
    def analyze(self, question: str) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
        """정량 분석 수행"""
        if not self.engine:
            return None, "데이터베이스 연결이 없습니다.", None
        
        # SQL 매핑 찾기
        best_match = self._find_best_sql_match(question)
        
        if not best_match:
            return None, "매칭되는 SQL 쿼리를 찾을 수 없습니다.", None
        
        # SQL 실행
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(best_match['sql']))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                
                if df.empty:
                    return None, "조회 결과가 없습니다.", best_match
                
                return df, None, best_match
                
        except Exception as e:
            return None, f"SQL 실행 오류: {str(e)}", best_match
    
    def _find_best_sql_match(self, question: str) -> Optional[Dict]:
        """가장 유사한 SQL 쿼리 찾기"""
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
        
        return best_match

class QualitativeAnalyzer:
    """
    정성 분석 (Vector DB with Watson AI)
    """
    
    def __init__(self):
        self.rag_chain = None
    
    def initialize(self, papers_dir: str = "../papers/"):
        """RAG 시스템 초기화"""
        print("📚 정성분석용 RAG 시스템 초기화 중...")
        
        # 문서 로드
        docs = self._load_documents(papers_dir)
        if not docs:
            print("❌ 문서를 로드할 수 없습니다.")
            return False
        
        # 텍스트 분할
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""]
        )
        splits = text_splitter.split_documents(docs)
        
        # HuggingFace 임베딩 사용
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        vectorstore_path = f"./chroma_db_watson_{EMBEDDING_MODEL.replace('/', '_').replace('-', '_')}"
        
        if os.path.exists(vectorstore_path):
            shutil.rmtree(vectorstore_path)
        
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=vectorstore_path
        )
        
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}
        )
        
        # RAG 체인 구성
        prompt = PromptTemplate(
            template="""당신은 DRT(수요응답형 교통) 전문가입니다.
제공된 문서를 바탕으로 질문에 정확하고 상세하게 답변하세요.

**참고 문서:**
{context}

**질문:** {question}

**답변:**""",
            input_variables=["question", "context"]
        )
        
        # Watson AI LLM 사용
        llm = WatsonXLLM()
        
        def format_docs(docs):
            return "\n\n---\n\n".join([
                f"[문서 {i+1}]\n{doc.page_content}"
                for i, doc in enumerate(docs)
            ])
        
        self.rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        
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
    
    def _load_documents(self, directory_path: str):
        """문서 로드"""
        all_docs = []
        pdf_files = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"총 {len(pdf_files)}개의 PDF 파일을 찾았습니다.")
        
        for pdf_path in pdf_files:
            success = False
            
            # PyMuPDFLoader 시도
            try:
                loader = PyMuPDFLoader(pdf_path)
                docs = loader.load()
                all_docs.extend(docs)
                print(f"✓ 로드 성공: {os.path.basename(pdf_path)}")
                success = True
            except Exception:
                pass
            
            # PyPDFLoader 시도
            if not success:
                try:
                    loader = PyPDFLoader(pdf_path)
                    docs = loader.load()
                    all_docs.extend(docs)
                    print(f"✓ 로드 성공: {os.path.basename(pdf_path)}")
                except Exception:
                    print(f"✗ 로드 실패: {os.path.basename(pdf_path)}")
        
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
            return "요청하신 정량적 데이터를 조회할 수 없습니다."
        
        # 데이터 포맷팅
        formatted_data = self._format_dataframe(data, sql_info.get('description', '데이터'))
        
        prompt = f"""당신은 DRT 전문가입니다. 다음 정량적 데이터를 분석하여 전문적인 인사이트를 제공하세요.

**질문:** {question}

**데이터 결과:**
{formatted_data}

**분석 요청:**
1. 데이터의 주요 특징과 의미 해석
2. 운영상의 시사점
3. 개선 방안 제안

**전문가 분석:**"""
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            return f"분석 중 오류가 발생했습니다: {str(e)}\n\n원본 데이터:\n{formatted_data}"
    
    def _generate_qualitative_response(self, question: str, qualitative_answer: str) -> str:
        if not qualitative_answer:
            return "정성적 분석 결과를 가져올 수 없습니다."
        
        prompt = f"""당신은 DRT 전문가입니다. 다음 정성적 분석 결과를 검토하고 보완하여 최종 답변을 작성하세요.

**질문:** {question}

**정성분석 결과:**
{qualitative_answer}

**요청사항:**
- 위 분석을 검토하고 더 명확하고 체계적으로 정리
- 실무적 적용 방안 추가
- 필요시 추가적인 전문 지식 보완

**최종 전문가 답변:**"""
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            return qualitative_answer  # 오류 시 원본 반환
    
    def _generate_mixed_response(self, question: str, quantitative_data: pd.DataFrame, 
                               qualitative_answer: str, sql_info: Dict) -> str:
        
        # 정량 데이터 포맷팅
        formatted_data = ""
        if quantitative_data is not None and not quantitative_data.empty:
            formatted_data = self._format_dataframe(quantitative_data, sql_info.get('description', '데이터'))
        
        prompt = f"""당신은 DRT 전문가입니다. 정량적 데이터와 정성적 분석을 통합하여 종합적인 답변을 제공하세요.

**질문:** {question}

**정량적 데이터:**
{formatted_data if formatted_data else "정량적 데이터가 없습니다."}

**정성적 분석:**
{qualitative_answer if qualitative_answer else "정성적 분석이 없습니다."}

**통합 분석 요청:**
1. 정량적 데이터와 정성적 분석을 연결하여 해석
2. 데이터가 이론을 어떻게 뒷받침하는지 설명
3. 종합적인 결론과 실무적 제언 제시

**종합 전문가 답변:**"""
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            # 오류 시 각각의 결과를 단순 조합
            result = f"**정량적 분석 결과:**\n{formatted_data}\n\n"
            result += f"**정성적 분석 결과:**\n{qualitative_answer}"
            return result
    
    def _format_dataframe(self, df: pd.DataFrame, description: str) -> str:
        """DataFrame을 읽기 쉬운 텍스트로 변환"""
        if df.empty:
            return "데이터가 없습니다."
        
        formatted = f"📊 {description}\n\n"
        
        if len(df) == 1:
            # 단일 행 (집계 결과)
            row = df.iloc[0]
            for col, val in row.items():
                if pd.notna(val):
                    if isinstance(val, (int, float)):
                        val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                    formatted += f"• {col}: {val}\n"
        else:
            # 여러 행
            display_df = df.head(5)
            for idx, row in display_df.iterrows():
                formatted += f"\n[{idx + 1}]\n"
                for col, val in row.items():
                    if pd.notna(val):
                        if isinstance(val, (int, float)):
                            val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                        formatted += f"  {col}: {val}\n"
            
            if len(df) > 5:
                formatted += f"\n*(총 {len(df)}개 결과 중 상위 5개 표시)*"
        
        return formatted

class SmartRAGSystem:
    """
    통합 스마트 RAG 시스템 (Watson AI 기반)
    """
    
    def __init__(self, papers_dir: str = "../papers/"):
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
        self.classifier = QuestionClassifier(self.predefined_queries)
        self.quantitative_analyzer = QuantitativeAnalyzer(DB_CONFIG, self.predefined_queries)
        self.qualitative_analyzer = QualitativeAnalyzer()
        self.response_generator = ResponseGenerator()
        
        # 정성분석 시스템 초기화
        if not self.qualitative_analyzer.initialize(papers_dir):
            print("⚠️ 정성분석 시스템 초기화 실패 - 정량분석만 사용 가능")
    
    def answer_question(self, question: str) -> str:
        """질문에 대한 통합 분석 및 답변"""
        print(f"🔍 질문 분석 중: {question}")
        
        # 1. 질문 분류
        question_type = self.classifier.classify_question(question)
        print(f"📋 질문 유형: {question_type.value}")
        
        # 2. 질문 유형별 처리
        quantitative_data = None
        qualitative_answer = None
        sql_info = None
        
        if question_type in [QuestionType.QUANTITATIVE, QuestionType.MIXED]:
            print("📊 정량분석 수행 중...")
            quantitative_data, error, sql_info = self.quantitative_analyzer.analyze(question)
            if error:
                print(f"⚠️ 정량분석 오류: {error}")
        
        if question_type in [QuestionType.QUALITATIVE, QuestionType.MIXED]:
            print("📚 정성분석 수행 중...")
            qualitative_answer = self.qualitative_analyzer.analyze(question)
        
        # 3. 최종 답변 생성 (Watson AI 사용)
        print("🤖 최종 답변 생성 중...")
        final_answer = self.response_generator.generate_final_response(
            question, question_type, quantitative_data, qualitative_answer, sql_info
        )
        
        # 답변 텍스트 처리
        if hasattr(final_answer, 'content'):
            return final_answer.content
        return str(final_answer)

def interactive_chat(rag_system: SmartRAGSystem):
    """대화형 채팅 인터페이스"""
    print("=" * 70)
    print("🤖 Watson AI 기반 스마트 DRT 분석 어시스턴트 (질문분류 + 정량/정성 통합분석)")
    print("=" * 70)
    print("✨ 자동으로 질문을 분류하여 최적의 분석 방법을 선택합니다")
    print("📊 정량분석: PostgreSQL 데이터 기반")
    print("📚 정성분석: 논문/문서 기반 (Watson AI 모델)") 
    print("🔄 통합분석: 정량+정성 데이터 결합 (Watson AI 추론)")
    print("❌ 관련없는 질문: 정중히 안내")
    print("\n종료하려면 'quit' 또는 '종료'를 입력하세요.")
    print("=" * 70)
    
    while True:
        try:
            question = input("\n🔍 질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 이용해주셔서 감사합니다!")
                break
            
            if not question:
                continue
            
            print(f"\n{'='*50}")
            answer = rag_system.answer_question(question)
            print(f"\n🤖 답변:")
            print(answer)
            print(f"\n{'='*50}")
            
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
        
        print(f"🚀 Watson AI 기반 스마트 RAG 시스템 초기화 중...")
        print(f"📡 모델: {CHAT_MODEL}")
        print(f"🔗 임베딩: {EMBEDDING_MODEL}")
        
        # 시스템 생성
        rag_system = SmartRAGSystem()
        
        # 테스트
        test_questions = [
            "안녕하세요?",  # 관련없는 질문
            "지난달 운행 건수는?",  # 정량분석
            "DRT의 장점은 무엇인가요?",  # 정성분석
            "지난달 승객 수와 DRT 효과를 분석해주세요"  # 통합분석
        ]
        
        print("\n🧪 Watson AI 시스템 테스트:")
        for i, q in enumerate(test_questions, 1):
            print(f"\n[테스트 {i}] {q}")
            try:
                answer = rag_system.answer_question(q)
                preview = answer[:100] + "..." if len(answer) > 100 else answer
                print(f"✓ 답변: {preview}")
            except Exception as e:
                print(f"❌ 오류: {str(e)}")
        
        print("\n✅ 테스트 완료! 대화형 모드를 시작합니다.\n")
        
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