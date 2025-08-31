import os
import logging
import shutil
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
from typing import Optional, List, Any

# 로깅 레벨 설정 (PDF 관련 경고 숨기기)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# Watson AI 설정
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    api_key=os.getenv("WATSONX_APIKEY"),
)
project_id = os.getenv("WATSONX_PROJECT_ID")

# 모델 설정 (Watson AI 모델 사용)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"  # HuggingFace 임베딩 사용
CHAT_MODEL = "ibm/granite-3-8b-instruct"  # Watson AI 모델

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

def load_documents_with_fallback(directory_path="../papers/"):
    """
    여러 PDF 로더를 시도해서 문서를 안전하게 로드
    """
    all_docs = []
    failed_files = []
    
    # PDF 파일 경로 수집
    pdf_files = []
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    print(f"총 {len(pdf_files)}개의 PDF 파일을 찾았습니다.")
    
    for pdf_path in pdf_files:
        success = False
        
        # 1차 시도: PyMuPDFLoader
        try:
            loader = PyMuPDFLoader(pdf_path)
            docs = loader.load()
            all_docs.extend(docs)
            print(f"✓ PyMuPDF로 로드 성공: {os.path.basename(pdf_path)}")
            success = True
        except Exception as e:
            print(f"△ PyMuPDF 실패: {os.path.basename(pdf_path)}")
        
        # 2차 시도: PyPDFLoader (1차가 실패한 경우)
        if not success:
            try:
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()
                all_docs.extend(docs)
                print(f"✓ PyPDF로 로드 성공: {os.path.basename(pdf_path)}")
                success = True
            except Exception as e:
                print(f"△ PyPDF도 실패: {os.path.basename(pdf_path)}")
        
        if not success:
            failed_files.append(pdf_path)
            print(f"✗ 모든 로더 실패: {os.path.basename(pdf_path)}")
    
    print(f"\n로드 완료: {len(all_docs)}개 문서, {len(failed_files)}개 실패")
    if failed_files:
        print("실패한 파일들:")
        for failed in failed_files:
            print(f"  - {failed}")
    
    return all_docs

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
    Watson AI 기반 RAG 시스템 생성
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
    
    # 3. HuggingFace 임베딩 사용 (Watson AI 임베딩 대신)
    print(f"3. 임베딩 모델 ({EMBEDDING_MODEL})로 벡터스토어 생성 중...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    # 임베딩 모델에 따른 벡터스토어 경로 설정
    vectorstore_path = f"./chroma_db_watson_{EMBEDDING_MODEL.replace('/', '_').replace('-', '_')}"
    
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
    
    # 5. 한국어 최적화 프롬프트 및 Watson AI LLM
    prompt = PromptTemplate(
        template="""당신은 한국어 학술 논문 전문 분석 어시스턴트입니다.
제공된 문서들을 바탕으로 질문에 정확하고 상세하게 답변해주세요.

**답변 규칙:**
- 문서에서 직접 찾을 수 있는 정보만 사용하세요
- 추측이나 일반적인 지식 대신 문서 내용에 근거하여 답변하세요
- 확실하지 않은 정보는 "문서에서 명확하게 확인되지 않습니다"라고 명시하세요
- 가능한 한 구체적인 데이터, 수치, 인용구를 포함하세요
- 답변은 한국어로 자연스럽게 작성하세요

**참고 문서:**
{context}

**질문:** {question}

**답변:**""",
        input_variables=["question", "context"],
    )
    
    print(f"4. Watson AI 채팅 모델 ({CHAT_MODEL}) 로드 중...")
    llm = WatsonXLLM()
    
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
    
    print("✅ Watson AI 기반 RAG 시스템 생성 완료!\n")
    return rag_chain

def interactive_chat(rag_chain):
    """
    대화형 채팅 인터페이스
    """
    print("=" * 60)
    print("🤖 Watson AI 논문 분석 어시스턴트")
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
            
            print("\n💭 Watson AI가 답변을 생성 중입니다...")
            answer = rag_chain.invoke(question)
            print(f"\n🤖 답변:\n{answer}")
            print("\n" + "-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            print("다른 질문을 시도해보세요.")

def main():
    # Watson AI 연결 확인
    if not credentials.api_key or not project_id:
        print("❌ Watson AI 자격증명이 설정되지 않았습니다.")
        print("환경변수 WATSONX_APIKEY와 WATSONX_PROJECT_ID를 설정해주세요.")
        return
    
    print(f"🚀 Watson AI 모델 ({CHAT_MODEL}) 연결 확인 중...")
    
    # RAG 시스템 생성
    rag_chain = create_rag_system()
    
    if rag_chain is None:
        return
    
    # 기본 테스트 질문들
    test_questions = [
        "DRT의 주요 특징과 장점은 무엇인가요?",
        "수요응답형 교통의 운영 방식을 설명해주세요.",
        "DRT 도입 시 고려해야 할 주요 요소들은 무엇인가요?",
    ]
    
    print("🧪 Watson AI 시스템 테스트 중...")
    print("=" * 50)
    
    for i, question in enumerate(test_questions, 1):
        try:
            print(f"\n[테스트 {i}] {question}")
            answer = rag_chain.invoke(question)
            print(f"답변: {answer[:200]}..." if len(answer) > 200 else f"답변: {answer}")
            print("-" * 30)
        except Exception as e:
            print(f"테스트 {i} 실패: {str(e)}")
    
    print("\n✅ 시스템 테스트 완료!")
    
    # 대화형 모드 시작
    interactive_chat(rag_chain)

if __name__ == "__main__":
    main()