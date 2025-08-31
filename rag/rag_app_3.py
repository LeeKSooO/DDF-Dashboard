import os
import logging
import shutil
import pandas as pd
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz
from sqlalchemy import create_engine, text
from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama

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

# 로깅 레벨 설정 (PDF 관련 경고 숨기기)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# 모델 설정 (하드웨어 스펙에 맞춘 추천)
EMBEDDING_MODEL = "bge-m3"  # 한국어/영어 모두 뛰어난 다국어 임베딩
CHAT_MODEL = "qwen2.5:7b-instruct"  # RTX 3080으로 충분히 실행 가능
# CHAT_MODEL = "qwen2.5:3b-instruct"  # 더 가볍게 원한다면

# PostgreSQL 연결 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ddf_db',
    'user': 'ddf_user',
    'password': 'ddf_password'
}

# 질문-SQL 매핑 딕셔너리 (실제 테이블 구조에 맞게 수정)
PREDEFINED_QUERIES = {
    "지난달 총 운행건수는?": {
        "sql": """
            SELECT 
                COUNT(*) as total_operations,
                SUM(ride_passenger + alight_passenger) as total_passengers,
                COUNT(DISTINCT node_id) as active_stations,
                ROUND(AVG(ride_passenger + alight_passenger), 2) as avg_passengers_per_operation
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
                ROUND(AVG(ride_passenger), 2) as avg_boarding_per_hour,
                ROUND(AVG(alight_passenger), 2) as avg_alighting_per_hour,
                ROUND(AVG(ride_passenger + alight_passenger), 2) as avg_total_passengers,
                SUM(ride_passenger + alight_passenger) as total_passengers_month,
                COUNT(DISTINCT node_id) as active_stations
            FROM station_passenger_history 
            WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
              AND (ride_passenger > 0 OR alight_passenger > 0)
        """,
        "description": "지난 달 평균 승객 수 및 총 이용객 통계"
    },
    
    "가장 바쁜 정류장은?": {
        "sql": """
            SELECT 
                sph.station_name,
                sph.node_id,
                SUM(sph.ride_passenger + sph.alight_passenger) as total_passengers,
                SUM(sph.ride_passenger) as total_boarding,
                SUM(sph.alight_passenger) as total_alighting,
                ROUND(AVG(sph.ride_passenger + sph.alight_passenger), 2) as avg_passengers_per_hour,
                COUNT(*) as operational_hours
            FROM station_passenger_history sph
            WHERE sph.record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND sph.record_date < DATE_TRUNC('month', CURRENT_DATE)::date
              AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
            GROUP BY sph.node_id, sph.station_name
            ORDER BY total_passengers DESC
            LIMIT 10
        """,
        "description": "지난 달 승하차 승객이 가장 많은 상위 10개 정류장"
    },
    
    "노선별 이용률은?": {
        "sql": """
            SELECT 
                sph.route_id,
                sph.route_name,
                COUNT(DISTINCT sph.node_id) as total_stops,
                SUM(sph.ride_passenger + sph.alight_passenger) as total_passengers,
                ROUND(AVG(sph.ride_passenger + sph.alight_passenger), 2) as avg_passengers_per_hour,
                COUNT(*) as operational_hours,
                COUNT(DISTINCT sph.record_date) as operation_days
            FROM station_passenger_history sph
            WHERE sph.record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND sph.record_date < DATE_TRUNC('month', CURRENT_DATE)::date
              AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
            GROUP BY sph.route_id, sph.route_name
            HAVING SUM(sph.ride_passenger + sph.alight_passenger) > 0
            ORDER BY total_passengers DESC
            LIMIT 15
        """,
        "description": "지난 달 노선별 이용률 상위 15개 노선"
    },
    
    "시간대별 이용 패턴은?": {
        "sql": """
            SELECT 
                sph.hour,
                COUNT(*) as total_operations,
                SUM(sph.ride_passenger) as total_boarding,
                SUM(sph.alight_passenger) as total_alighting,
                SUM(sph.ride_passenger + sph.alight_passenger) as total_passengers,
                ROUND(AVG(sph.ride_passenger + sph.alight_passenger), 2) as avg_passengers,
                COUNT(DISTINCT sph.node_id) as active_stations,
                CASE 
                    WHEN sph.hour BETWEEN 7 AND 9 THEN 'Morning Peak'
                    WHEN sph.hour BETWEEN 17 AND 19 THEN 'Evening Peak'
                    WHEN sph.hour BETWEEN 10 AND 16 THEN 'Daytime Off-Peak'
                    WHEN sph.hour BETWEEN 20 AND 23 THEN 'Evening Off-Peak'
                    ELSE 'Night/Early Morning'
                END as time_category
            FROM station_passenger_history sph
            WHERE sph.record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND sph.record_date < DATE_TRUNC('month', CURRENT_DATE)::date
              AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
            GROUP BY sph.hour
            ORDER BY sph.hour
        """,
        "description": "지난 달 시간대별 버스 이용 패턴 및 피크 시간 분석"
    },
    
    "운영 효율성은?": {
        "sql": """
            SELECT 
                '전체 시스템' as metric,
                COUNT(DISTINCT node_id) as total_stations,
                COUNT(DISTINCT CASE WHEN total_passengers > 0 THEN node_id END) as active_stations,
                ROUND(
                    COUNT(DISTINCT CASE WHEN total_passengers > 0 THEN node_id END) * 100.0 / 
                    COUNT(DISTINCT node_id), 2
                ) as utilization_rate,
                SUM(total_passengers) as total_system_passengers,
                ROUND(AVG(total_passengers), 2) as avg_passengers_per_station
            FROM (
                SELECT 
                    node_id,
                    SUM(ride_passenger + alight_passenger) as total_passengers
                FROM station_passenger_history
                WHERE record_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
                  AND record_date < DATE_TRUNC('month', CURRENT_DATE)::date
                GROUP BY node_id
            ) station_stats
        """,
        "description": "지난 달 전체 시스템 운영 효율성 분석"
    }
}

def load_documents_with_fallback(directory_path="../papers/"):
    """
    여러 PDF 로더를 시도해서 문서를 안전하게 로드 (UTF-8 인코딩 오류 방지)
    """
    all_docs = []
    failed_files = []
    
    # PDF 파일 경로 수집
    pdf_files = []
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    print(f"총 {len(pdf_files)}개의 PDF 파일을 찾았습니다.")
    
    for pdf_path in pdf_files:
        success = False
        
        # 1차 시도: PyMuPDFLoader (UTF-8 처리 개선)
        try:
            # 파일 경로에 UTF-8 문제가 있을 수 있으므로 안전하게 처리
            safe_path = os.path.abspath(pdf_path)
            loader = PyMuPDFLoader(safe_path)
            docs = loader.load()
            
            # 문서 내용의 인코딩 문제 해결
            for doc in docs:
                if hasattr(doc, 'page_content'):
                    try:
                        # 내용이 바이트인 경우 UTF-8로 디코딩
                        if isinstance(doc.page_content, bytes):
                            doc.page_content = doc.page_content.decode('utf-8', errors='replace')
                        # 문제가 있는 문자들을 안전한 문자로 대체
                        doc.page_content = doc.page_content.encode('utf-8', errors='replace').decode('utf-8')
                    except Exception:
                        # 인코딩 문제가 있는 경우 빈 문자열로 처리하지 않고 그대로 유지
                        pass
            
            all_docs.extend(docs)
            print(f"✓ PyMuPDF로 로드 성공: {os.path.basename(pdf_path)}")
            success = True
        except Exception as e:
            print(f"△ PyMuPDF 실패: {os.path.basename(pdf_path)} - {str(e)[:100]}")
        
        # 2차 시도: PyPDFLoader (1차가 실패한 경우)
        if not success:
            try:
                safe_path = os.path.abspath(pdf_path)
                loader = PyPDFLoader(safe_path)
                docs = loader.load()
                
                # 동일한 인코딩 처리
                for doc in docs:
                    if hasattr(doc, 'page_content'):
                        try:
                            if isinstance(doc.page_content, bytes):
                                doc.page_content = doc.page_content.decode('utf-8', errors='replace')
                            doc.page_content = doc.page_content.encode('utf-8', errors='replace').decode('utf-8')
                        except Exception:
                            pass
                
                all_docs.extend(docs)
                print(f"✓ PyPDF로 로드 성공: {os.path.basename(pdf_path)}")
                success = True
            except Exception as e:
                print(f"△ PyPDF도 실패: {os.path.basename(pdf_path)} - {str(e)[:100]}")
        
        if not success:
            failed_files.append(pdf_path)
            print(f"✗ 모든 로더 실패: {os.path.basename(pdf_path)}")
    
    print(f"\n로드 완료: {len(all_docs)}개 문서, {len(failed_files)}개 실패")
    if failed_files:
        print("실패한 파일들:")
        for failed in failed_files:
            print(f"  - {failed}")
    
    return all_docs

def create_db_connection():
    """
    PostgreSQL 데이터베이스 연결 생성
    """
    try:
        connection_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(connection_string)
        
        # 연결 테스트
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ PostgreSQL 연결 성공!")
            
        return engine
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {str(e)}")
        return None

def execute_sql(query):
    """
    SQL 쿼리 실행 및 결과 반환 (개선된 버전)
    """
    try:
        db_engine = create_db_connection()
        if not db_engine:
            return None, "데이터베이스 연결이 없습니다."
        
        with db_engine.connect() as conn:
            result = conn.execute(text(query))
            
            # 결과를 DataFrame으로 변환
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            
            if df.empty:
                return None, "조회 결과가 없습니다."
            
            return df, None
            
    except Exception as e:
        error_msg = f"SQL 실행 오류: {str(e)}"
        print(f"❌ {error_msg}")
        return None, error_msg

def format_sql_results(df, query_description):
    """
    SQL 결과를 읽기 쉬운 형태로 포맷팅
    """
    if df is None or df.empty:
        return "조회된 데이터가 없습니다."
    
    formatted = f"\n📊 **{query_description}**\n\n"
    
    # 결과가 1행인 경우 (집계 결과)
    if len(df) == 1:
        row = df.iloc[0]
        for col, val in row.items():
            if pd.notna(val):
                # 숫자인 경우 천 단위 구분자 추가
                if isinstance(val, (int, float)) and col != 'hour':
                    val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                formatted += f"• **{col}**: {val}\n"
    
    # 결과가 여러 행인 경우 (순위, 패턴 등)
    else:
        # 상위 5개만 표시 (너무 길어지지 않게)
        display_df = df.head(5) if len(df) > 5 else df
        
        for idx, row in display_df.iterrows():
            formatted += f"\n**{idx + 1}위:**\n"
            for col, val in row.items():
                if pd.notna(val):
                    if isinstance(val, (int, float)) and col not in ['hour', 'operational_percentage']:
                        val = f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
                    formatted += f"  • {col}: {val}\n"
        
        if len(df) > 5:
            formatted += f"\n*(전체 {len(df)}개 결과 중 상위 5개만 표시)*\n"
    
    return formatted

class QuestionMatcher:
    """
    질문과 SQL 매핑을 찾는 클래스
    """
    
    def __init__(self, question_mappings):
        self.mappings = question_mappings
    
    def find_best_match(self, user_question, threshold=70):
        """
        가장 유사한 질문을 찾아서 SQL 반환
        """
        best_match = None
        best_score = 0
        
        for mapped_question, sql_info in self.mappings.items():
            # 여러 방식으로 유사도 계산
            similarity_scores = [
                fuzz.ratio(user_question.lower(), mapped_question.lower()),
                fuzz.partial_ratio(user_question.lower(), mapped_question.lower()),
                fuzz.token_sort_ratio(user_question.lower(), mapped_question.lower()),
                self._keyword_similarity(user_question, mapped_question)
            ]
            
            # 최고 점수 선택
            score = max(similarity_scores)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = {
                    'question': mapped_question,
                    'sql': sql_info['sql'],
                    'description': sql_info['description'],
                    'confidence': score
                }
        
        return best_match
    
    def _keyword_similarity(self, user_q, mapped_q):
        """
        키워드 기반 유사도 계산
        """
        user_keywords = set(user_q.lower().split())
        mapped_keywords = set(mapped_q.lower().split())
        
        if not user_keywords or not mapped_keywords:
            return 0
            
        intersection = user_keywords.intersection(mapped_keywords)
        union = user_keywords.union(mapped_keywords)
        
        return (len(intersection) / len(union)) * 100
    
    def get_available_questions(self):
        """
        사용 가능한 질문 목록 반환
        """
        return list(self.mappings.keys())

class HybridRAG:
    """
    SQL 데이터 + 문서 데이터 통합 RAG 시스템
    """
    
    def __init__(self, db_engine, document_rag_chain, question_mappings):
        self.db_engine = db_engine
        self.doc_rag = document_rag_chain
        self.question_matcher = QuestionMatcher(question_mappings)
        self.llm = ChatOllama(model=CHAT_MODEL, temperature=0.2)
    
    def answer_question(self, user_question):
        """
        질문에 대해 SQL + 문서 데이터로 통합 답변
        """
        
        # 1. SQL 매핑 검사
        sql_match = self.question_matcher.find_best_match(user_question)
        
        # 2. 문서 기반 정보 검색
        doc_context = self.doc_rag.invoke(user_question)
        
        # 3. SQL 데이터가 있는 경우
        if sql_match:
            print(f"📊 질문 매칭: '{sql_match['question']}' (신뢰도: {sql_match['confidence']:.1f}%)")
            sql_data = self._execute_sql(sql_match['sql'])
            return self._generate_hybrid_answer(
                user_question, sql_match, sql_data, doc_context
            )
        
        # 4. SQL 데이터가 없으면 문서만으로 답변
        else:
            print("📚 SQL 매칭 없음 - 문서 기반 답변")
            return self._generate_document_only_answer(user_question, doc_context)
    
    def _execute_sql(self, sql_query):
        """
        SQL 쿼리 실행하여 데이터 반환
        """
        df, error = execute_sql(sql_query)
        if error:
            print(f"SQL 실행 오류: {error}")
            return None
        return df
    
    def _generate_hybrid_answer(self, question, sql_match, sql_data, doc_context):
        """
        SQL 결과 + 문서 정보로 통합 답변 생성
        """
        # SQL 결과를 읽기 쉬운 형태로 포맷팅
        formatted_data = format_sql_results(sql_data, sql_match['description'])
        
        prompt = f"""
당신은 DRT(수요응답형 교통) 및 교통 시스템 전문가입니다.
사용자 질문에 대해 정량적 데이터와 문서 정보를 모두 활용해 포괄적이고 실용적으로 답변하세요.

**사용자 질문:** {question}

**실제 운영 데이터:**
{formatted_data}

**관련 이론 및 연구자료:**
{doc_context}

**답변 가이드라인:**
1. 현재 운영 상황을 데이터로 명확히 제시하세요
2. 수치의 의미와 운영상의 시사점을 구체적으로 해석하세요
3. 문서의 이론적 배경과 연결하여 분석의 깊이를 더하세요
4. 개선 방안이나 정책적 제언을 구체적으로 제시하세요
5. 답변은 체계적이고 실무진이 이해하기 쉽게 구성하세요
6. DRT 분야의 전문성을 바탕으로 인사이트를 제공하세요

**전문가 분석:**
""",
        
        return self.llm.invoke(prompt)
    
    def _generate_document_only_answer(self, question, doc_context):
        """
        문서 기반만으로 답변 생성
        """
        
        prompt = f"""
당신은 DRT(수요응답형 교통) 및 교통 시스템 전문가입니다.
제공된 문서를 바탕으로 질문에 전문적이고 포괄적으로 답변하세요.

**질문:** {question}

**참고 문서:**
{doc_context}

**답변 지침:**
1. 문서의 내용을 바탕으로 하되, DRT 분야의 전문 지식을 활용하여 보다 완전한 답변을 제공하세요
2. 이론적 배경과 실무적 적용 방안을 모두 다뤄주세요  
3. 구체적인 사례나 데이터가 문서에 있다면 반드시 인용하세요
4. 관련 정책이나 해외 사례 등도 언급하여 맥락을 풍부하게 하세요
5. 답변을 체계적으로 구성하여 이해하기 쉽게 작성하세요

**전문가 답변:**
"""
        
        return self.llm.invoke(prompt)

    def get_sql_questions_list(self):
        """
        사용 가능한 정량적 질문 목록
        """
        return self.question_matcher.get_available_questions()

def create_korean_text_splitter():
    """
    한국어 텍스트에 최적화된 분할기 생성
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=1500,  # 한국어는 영어보다 정보 밀도가 높으므로 크게 설정
        chunk_overlap=300,  # 충분한 오버랩으로 문맥 유지
        separators=[
            "\n\n",  # 문단 분리
            "\n",    # 줄 분리
            ". ",    # 영어 문장 분리
            "。",    # 일본어/중국어 문장 분리
            "!",     # 느낌표
            "?",     # 물음표
            " ",     # 공백
            ""       # 글자별 (최후 수단)
        ],
        length_function=len,
        is_separator_regex=False,
    )

def create_rag_system():
    """
    한국어 최적화 RAG 시스템 생성
    """
    # 1. 문서 로드
    print("1. PDF 문서 로드 중...")
    docs = load_documents_with_fallback()
    
    if not docs:
        print("로드된 문서가 없습니다. papers/ 폴더에 PDF 파일이 있는지 확인하세요.")
        return None
    
    # 2. 한국어 최적화 텍스트 분할
    print("2. 한국어 최적화 텍스트 분할 중...")
    text_splitter = create_korean_text_splitter()
    splits = text_splitter.split_documents(docs)
    print(f"총 {len(splits)}개의 청크로 분할됨")
    
    # 3. 한국어/영어 최적화 임베딩 및 벡터스토어
    print(f"3. 임베딩 모델 ({EMBEDDING_MODEL})로 벡터스토어 생성 중...")
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    
    # 임베딩 모델에 따른 벡터스토어 경로 설정
    vectorstore_path = f"./chroma_db_{EMBEDDING_MODEL.replace(':', '_').replace('.', '_').replace('-', '_')}"
    
    # 항상 새로 생성 (차원 충돌 방지)
    if os.path.exists(vectorstore_path):
        shutil.rmtree(vectorstore_path)
        print("기존 벡터스토어를 삭제하고 새로 생성합니다...")
    
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory=vectorstore_path
    )
    print(f"벡터스토어가 {vectorstore_path}에 저장되었습니다.")
    
    # 4. 검색기 설정 (더 많은 문서 검색으로 정확도 향상)
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 6}  # 더 많은 관련 문서 검색
    )
    
    # 5. 한국어 최적화 프롬프트 및 LLM
    prompt = PromptTemplate(
        template="""당신은 한국어 DRT(수요응답형 교통) 및 교통 시스템 전문가입니다.
제공된 문서들을 바탕으로 질문에 정확하고 상세하게 답변해주세요.

**답변 규칙:**
- 제공된 문서에서 찾을 수 있는 정보를 우선적으로 사용하세요
- 문서에 직접적인 답변이 없어도, 관련 정보를 바탕으로 논리적인 추론을 제공하세요  
- DRT 및 교통 분야의 전문 지식을 활용하여 포괄적으로 답변하세요
- 구체적인 데이터, 수치, 사례가 있다면 반드시 포함하세요
- 답변은 명확하고 체계적으로 구성하세요 (예: 1. 정의, 2. 특징, 3. 효과 등)
- 실무적인 시사점이나 활용 방안도 함께 제시하세요

**참고 문서:**
{context}

**질문:** {question}

**답변 (구체적이고 실용적으로):**
""",
        input_variables=["question", "context"],
    )
    
    print(f"4. 채팅 모델 ({CHAT_MODEL}) 로드 중...")
    llm = ChatOllama(
        model=CHAT_MODEL,
        temperature=0.1,  # 약간의 창의성 허용하지만 정확성 우선
        num_ctx=8192,     # 긴 문맥 처리를 위한 컨텍스트 크기 증가
    )
    
    # 6. RAG 체인 구성
    def format_docs(docs):
        return "\n\n---\n\n".join([
            f"[문서 {i+1}]\n{doc.page_content}" 
            for i, doc in enumerate(docs)
        ])
    
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    print("✅ 한국어 최적화 RAG 시스템 생성 완료!\n")
    return rag_chain

def interactive_chat(rag_chain):
    """
    대화형 채팅 인터페이스 (개선된 출력 처리)
    """
    print("=" * 60)
    print("🤖 한국어 논문 분석 어시스턴트")
    print("=" * 60)
    print("DRT(수요응답형 교통) 관련 논문들을 분석해드립니다.")
    print("질문을 입력하세요. 종료하려면 'quit' 또는 '종료'를 입력하세요.")
    print("=" * 60)
    
    while True:
        try:
            question = input("\n🔍 질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 이용해주셔서 감사합니다!")
                break
            
            if not question:
                continue
            
            print("\n💭 답변을 생성 중입니다...")
            answer = rag_chain.invoke(question)
            
            # 답변 출력 처리 개선
            if hasattr(answer, 'content'):
                answer_text = answer.content
            else:
                answer_text = str(answer)
            
            # 줄바꿈 처리 및 출력 포맷팅
            answer_text = answer_text.replace('\\n', '\n')
            print(f"\n🤖 답변:")
            print(answer_text)
            print("\n" + "-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def create_hybrid_rag_system():
    """
    하이브리드 RAG 시스템 생성
    """
    print("🚀 하이브리드 RAG 시스템 초기화...")
    
    # 1. 기존 문서 RAG 생성
    document_rag_chain = create_rag_system()  # 기존 함수
    
    if document_rag_chain is None:
        print("문서 RAG 생성 실패")
        return None
    
    # 2. PostgreSQL 연결
    print("2. PostgreSQL 데이터베이스 연결 중...")
    db_engine = create_db_connection()
    
    if db_engine is None:
        print("데이터베이스 연결 실패 - 문서 기반 RAG만 사용")
        db_engine = None
    
    # 3. 하이브리드 RAG 생성
    hybrid_rag = HybridRAG(
        db_engine=db_engine,
        document_rag_chain=document_rag_chain,
        question_mappings=PREDEFINED_QUERIES
    )
    
    print("✅ 하이브리드 RAG 시스템 준비 완료!")
    return hybrid_rag

def interactive_hybrid_chat(hybrid_rag):
    """
    하이브리드 채팅 인터페이스 (개선된 출력 처리)
    """
    print("=" * 60)
    print("🤖 DRT 통합 분석 어시스턴트 (정량 + 정성 분석)")
    print("=" * 60)
    print("📊 정량적 질문 예시:")
    
    # 사용 가능한 SQL 질문 목록 표시
    sql_questions = hybrid_rag.get_sql_questions_list()
    for i, q in enumerate(sql_questions[:5], 1):
        print(f"  {i}. {q}")
    print("\n📚 정성적 질문도 문서 기반으로 답변 가능합니다.")
    print("=" * 60)
    
    while True:
        try:
            question = input("\n🔍 질문: ").strip()
            
            if question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 이용해주셔서 감사합니다!")
                break
            
            if not question:
                continue
            
            print("\n💭 분석 중입니다...")
            answer = hybrid_rag.answer_question(question)
            
            # 답변 출력 처리 개선
            if hasattr(answer, 'content'):
                answer_text = answer.content
            else:
                answer_text = str(answer)
            
            # 줄바꿈 처리 및 출력 포맷팅
            answer_text = answer_text.replace('\\n', '\n')
            print(f"\n🤖 통합 분석 결과:")
            print(answer_text)
            print("\n" + "-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def main():
    try:
        print("🚀 DRT 통합 분석 시스템 초기화 중...")
        
        # 하이브리드 RAG 시스템 생성
        hybrid_rag = create_hybrid_rag_system()
        
        if hybrid_rag is None:
            print("❌ 시스템 초기화 실패")
            return
        
        # 기본 테스트 질문들
        test_questions = [
            "지난달 운행 건수는 몇 개인가요?",  # SQL 매칭 테스트
            "DRT의 주요 장점은 무엇인가요?",     # 문서 기반 테스트
        ]
        
        print("🧪 시스템 테스트 중...")
        print("=" * 50)
        
        for i, question in enumerate(test_questions, 1):
            try:
                print(f"\n[테스트 {i}] {question}")
                answer = hybrid_rag.answer_question(question)
                
                # 답변 처리 개선
                if hasattr(answer, 'content'):
                    answer_str = answer.content
                else:
                    answer_str = str(answer)
                
                answer_str = answer_str.replace('\\n', '\n')
                display_text = answer_str[:200] + "..." if len(answer_str) > 200 else answer_str
                print(f"✓ 답변: {display_text}")
                print("-" * 30)
                
            except Exception as e:
                print(f"❌ 테스트 {i} 실패: {str(e)}")
                print("시스템이 불완전할 수 있습니다. 계속 진행합니다.")
        
        print("\n✅ 시스템 테스트 완료!")
        
        # 하이브리드 채팅 시작
        interactive_hybrid_chat(hybrid_rag)
        
    except KeyboardInterrupt:
        print("\n\n👋 사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 치명적 오류 발생: {str(e)}")
        print("시스템을 재시작해보세요. 문제가 지속되면 환경 설정을 확인하세요.")
        print("\n주요 확인 사항:")
        print("1. Ollama 서비스가 실행 중인지 확인")
        print("2. 필요한 모델들이 설치되어 있는지 확인")
        print("3. papers/ 폴더에 PDF 파일이 있는지 확인")
        print("4. PostgreSQL 연결 설정이 올바른지 확인")

if __name__ == "__main__":
    main()