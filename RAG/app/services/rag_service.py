"""
RAG service that integrates all components with CoT functionality
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from langchain_chroma import Chroma
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.core.config import settings
from app.core.exceptions import RAGServiceException
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.multi_query_service import MultiQueryService
from app.services.reranking_service import RerankingService

logger = logging.getLogger(__name__)


class RAGService:
    """Read-only RAG service with CoT enhancement
    
    This service only queries existing vector stores and does not handle document loading.
    Document ETL should be done separately using the DocumentETL job.
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        self.multi_query_service = None  # Initialize later after llm_service
        self.reranking_service = None    # Initialize later after llm_service
        self.vectorstore: Optional[Chroma] = None
        self.rag_chain = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all RAG components"""
        if self._initialized:
            return True
        
        logger.info("🚀 Initializing RAG service...")
        
        try:
            # Initialize services (no document loader needed for read-only)
            await self.embedding_service.initialize()
            await self.llm_service.initialize()
            
            # Initialize multi-query service
            self.multi_query_service = MultiQueryService(self.llm_service)
            
            # Initialize re-ranking service
            self.reranking_service = RerankingService(self.llm_service)
            
            # Initialize vector store (read-only)
            await self._initialize_vectorstore_readonly()
            
            # Setup RAG chain
            await self._setup_rag_chain()
            
            self._initialized = True
            logger.info("✅ Read-only RAG service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ RAG service initialization failed: {e}")
            return False
    
    async def _initialize_vectorstore_readonly(self) -> None:
        """Initialize Chroma vector store in read-only mode"""
        logger.info("📚 Initializing read-only vector store...")
        
        chroma_path = Path(settings.CHROMA_PERSIST_DIR)
        
        try:
            if chroma_path.exists() and any(chroma_path.iterdir()):
                # Load existing vector store
                logger.info("📖 Loading existing vector store (read-only)...")
                self.vectorstore = Chroma(
                    persist_directory=str(chroma_path),
                    embedding_function=self.embedding_service.langchain_embeddings
                )
                
                # Get document count for info
                try:
                    doc_count = self.vectorstore._collection.count()
                    logger.info(f"📊 Vector store contains {doc_count} document chunks")
                except Exception as e:
                    logger.warning(f"Could not get document count: {e}")
                    
            else:
                logger.warning("⚠️ Vector store not found - no documents available for querying")
                logger.warning("💡 Run DocumentETL job to create vector store first")
                # Still initialize empty store for graceful degradation
                self.vectorstore = None
                
            logger.info(f"✅ Read-only vector store initialized at {chroma_path}")
            
        except Exception as e:
            logger.error(f"❌ Vector store initialization failed: {e}")
            raise RAGServiceException(f"Vector store initialization error: {e}")
    
    # Document loading methods removed - use DocumentETL job instead
    
    async def _setup_rag_chain(self) -> None:
        """Setup RAG chain with CoT-enhanced prompt"""
        if not self.vectorstore:
            raise RAGServiceException("Vector store not initialized")
        
        logger.info("🔗 Setting up RAG chain...")
        
        try:
            # Create retriever
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 6}
            )
            
            # CoT-enhanced prompt template
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
                logger.debug(f"📚 {len(docs)}개 문서 참조")
                return context
            
            # Create RAG chain
            self.rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | cot_prompt
                | self.llm_service.langchain_llm
                | StrOutputParser()
            )
            
            logger.info("✅ RAG chain setup completed")
            
        except Exception as e:
            logger.error(f"❌ RAG chain setup failed: {e}")
            raise RAGServiceException(f"RAG chain setup error: {e}")
    
    async def query(self, question: str) -> Dict[str, Any]:
        """Query the RAG system (read-only)"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")
        
        if not self.rag_chain:
            raise RAGServiceException("RAG chain not setup")
        
        if not self.vectorstore:
            raise RAGServiceException("No vector store available - run DocumentETL job first")
        
        try:
            logger.info(f"🔍 Processing read-only query: {question[:50]}...")
            
            # Generate response using RAG chain
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.rag_chain.invoke(question)
            )
            
            # Get reasoning steps
            reasoning_steps = self.llm_service.get_reasoning_steps()
            
            # Calculate confidence (simple heuristic)
            confidence = self._calculate_confidence(response, reasoning_steps)
            
            result = {
                "question": question,
                "answer": response,
                "reasoning_steps": reasoning_steps,
                "confidence": confidence,
                "cot_enabled": self.llm_service.enable_cot,
                "mode": "read_only"
            }
            
            logger.info(f"✅ Read-only query processed successfully (confidence: {confidence:.0%})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Query processing failed: {e}")
            raise RAGServiceException(f"Query processing error: {e}")
    
    async def multi_query(self, question: str, max_results: int = 10) -> Dict[str, Any]:
        """Enhanced query with multi-query generation for better retrieval"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")
        
        if not self.vectorstore:
            raise RAGServiceException("No vector store available - run DocumentETL job first")
        
        if not self.multi_query_service:
            raise RAGServiceException("Multi-query service not initialized")
        
        try:
            logger.info(f"🔍 Processing multi-query: {question[:50]}...")
            
            # Step 1: Generate multiple diverse queries
            queries = await self.multi_query_service.generate_multiple_queries(question)
            
            # Validate queries is a list and not empty
            if not isinstance(queries, list) or len(queries) == 0:
                logger.warning("⚠️ Invalid queries result, using fallback")
                queries = [question]  # Fallback to original query
            
            logger.info(f"📝 Generated {len(queries)} diverse queries")
            
            # Step 2: Retrieve documents for each query
            all_documents = []
            unique_docs = set()
            
            for i, query in enumerate(queries, 1):
                logger.debug(f"🔍 Retrieving for query {i}: {query[:50]}...")
                
                # Safe division with minimum value
                k_value = max(5, max_results // max(len(queries), 1))
                
                # Retrieve documents for this query
                docs = self.vectorstore.similarity_search(
                    query, 
                    k=k_value
                )
                
                # Filter duplicates by content hash
                for doc in docs:
                    doc_hash = hash(doc.page_content)
                    if doc_hash not in unique_docs:
                        unique_docs.add(doc_hash)
                        all_documents.append(doc)
            
            logger.info(f"📊 Retrieved {len(all_documents)} unique documents from {len(queries)} queries")
            
            # Step 3: Re-rank documents using multiple criteria
            if self.reranking_service:
                logger.info("🎯 Re-ranking documents with multiple criteria...")
                reranked_documents = await self.reranking_service.rerank_documents(
                    question, all_documents, top_k=max_results
                )
                top_documents = reranked_documents
            else:
                logger.warning("⚠️ Re-ranking service not available, using similarity order")
                top_documents = all_documents[:max_results]
            
            # Step 4: Generate context from selected documents
            context = self._format_context_from_documents(top_documents)
            
            # Step 5: Generate enhanced answer using combined context
            enhanced_response = await self._generate_enhanced_response(question, context, queries)
            
            # Get reasoning steps
            reasoning_steps = self.llm_service.get_reasoning_steps()
            
            # Calculate enhanced confidence
            confidence = self._calculate_enhanced_confidence(enhanced_response, reasoning_steps, len(all_documents))
            
            result = {
                "question": question,
                "answer": enhanced_response,
                "reasoning_steps": reasoning_steps,
                "confidence": confidence,
                "cot_enabled": self.llm_service.enable_cot,
                "mode": "multi_query_with_reranking",
                "generated_queries": queries,
                "documents_retrieved": len(all_documents),
                "documents_reranked": len(top_documents),
                "unique_sources": len(set(doc.metadata.get('source', '') for doc in top_documents)),
                "reranking_enabled": self.reranking_service is not None,
                "top_rerank_scores": [doc.metadata.get('rerank_score', 0.0) for doc in top_documents[:5]]
            }
            
            logger.info(f"✅ Multi-query processed successfully (confidence: {confidence:.0%})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Multi-query processing failed: {e}")
            raise RAGServiceException(f"Multi-query processing error: {e}")
    
    def _calculate_confidence(self, response: str, reasoning_steps: List[str]) -> float:
        """Calculate response confidence"""
        confidence = 0.5  # base confidence
        
        # Ensure response is a string
        if not isinstance(response, str):
            logger.warning(f"⚠️ Response is not a string: {type(response)}")
            response = str(response) if response is not None else ""
        
        # Boost confidence based on response length and structure
        if len(response.strip()) > 100:
            confidence += 0.2
        
        # Boost confidence if CoT steps are present
        if reasoning_steps:
            confidence += 0.2
        
        # Boost confidence if response contains structured elements
        if any(marker in response for marker in ["1단계", "2단계", "3단계", "4단계"]):
            confidence += 0.1
        
        return min(0.95, confidence)
    
    def _format_context_from_documents(self, documents: List) -> str:
        """Format context from retrieved documents"""
        context_parts = []
        
        for i, doc in enumerate(documents, 1):
            # Get metadata
            section = doc.metadata.get('section_title', '')
            importance = doc.metadata.get('importance_score', 0.0)
            rerank_score = doc.metadata.get('rerank_score', 0.0)
            
            # Clean and format document content
            content = doc.page_content.strip()
            
            # Create clean header
            header = f"[문서 {i}]"
            if section:
                header += f" {section}"
            if rerank_score > 0:
                header += f" (관련도: {rerank_score:.2f})"
            
            context_parts.append(f"{header}\n{content}")
        
        return "\n\n---\n\n".join(context_parts)
    
    async def _generate_enhanced_response(self, question: str, context: str, queries: List[str]) -> str:
        """Generate enhanced response using multi-query context"""
        
        # 질문 유형 분석
        answer_type = self._analyze_question_type(question)
        
        # 질문 유형에 맞는 프롬프트 생성
        enhanced_prompt = self._create_adaptive_prompt(question, context, answer_type)

        try:
            # Generate response using LLM
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.llm_service.langchain_llm.invoke(enhanced_prompt)
            )
            return response
            
        except Exception as e:
            logger.error(f"Enhanced response generation failed: {e}")
            # Fallback to basic prompt
            return f"질문: {question}\n\n관련 정보를 바탕으로 답변이 생성되지 않았습니다. 오류: {str(e)}"
    
    def _analyze_question_type(self, question: str) -> str:
        """Analyze question type and determine appropriate response strategy"""
        question_lower = question.lower()
        
        # 장점/효과 질문을 먼저 체크 (더 구체적인 키워드이므로)
        if any(keyword in question_lower for keyword in ["장점", "효과", "이점", "혜택", "좋은점", "도움"]):
            return "benefits"
        
        # 정의/개념 질문
        elif any(keyword in question_lower for keyword in ["정의는", "무엇인가", "개념", "의미", "뜻", "란 무엇"]):
            return "definition"
        
        # 방법/절차 질문
        elif any(keyword in question_lower for keyword in ["방법", "절차", "과정", "단계", "어떻게", "방식"]):
            return "procedure"
        
        # 사례/예시 질문
        elif any(keyword in question_lower for keyword in ["사례", "예시", "예", "실제", "도입", "적용"]):
            return "examples"
        
        # 비교/차이점 질문
        elif any(keyword in question_lower for keyword in ["차이", "비교", "다른점", "구별", "vs"]):
            return "comparison"
        
        # 포괄적 설명 요청
        elif any(keyword in question_lower for keyword in ["포괄적", "전체적", "종합적", "자세히", "상세히", "전반적"]):
            return "comprehensive"
        
        # 문제/해결 질문
        elif any(keyword in question_lower for keyword in ["문제", "해결", "개선", "최적화", "향상"]):
            return "problem_solution"
        
        # 특징/구성요소 질문
        elif any(keyword in question_lower for keyword in ["특징", "구성", "요소", "구조", "특성"]):
            return "characteristics"
        
        # 기본 질문 (단순 답변)
        else:
            return "general"
    
    def _create_adaptive_prompt(self, question: str, context: str, answer_type: str) -> str:
        """Create adaptive prompt based on question type"""
        
        base_context = f"질문: {question}\n참고자료:\n{context}\n\n"
        
        if answer_type == "definition":
            return base_context + """DRT 전문가로서 다음과 같이 간결하게 정의해주세요:

🔍 핵심 정의
- 질문에서 요구하는 개념의 핵심 정의를 명확하고 간결하게 제시

📝 핵심 특징 (2-3가지)
- 가장 중요한 특징이나 구성요소만 간략히 언급

답변:"""
        
        elif answer_type == "benefits":
            return base_context + """DRT 전문가로서 다음과 같이 장점을 설명해주세요:

✅ 주요 장점들
- 핵심적인 장점 3-5가지를 구체적으로 제시
- 각 장점에 대한 간략한 설명 포함

💡 실무적 효과
- 실제 도입 시 기대되는 효과나 개선점

답변:"""
        
        elif answer_type == "procedure":
            return base_context + """DRT 전문가로서 다음과 같이 절차를 설명해주세요:

📋 주요 단계
1. 첫 번째 단계와 주요 내용
2. 두 번째 단계와 주요 내용
3. 세 번째 단계와 주요 내용
(필요에 따라 추가)

⚡ 핵심 고려사항
- 실행 시 주의해야 할 중요한 포인트들

답변:"""
        
        elif answer_type == "examples":
            return base_context + """DRT 전문가로서 다음과 같이 사례를 제시해주세요:

🏢 대표적인 사례들
- 국내외 주요 도입 사례 2-3가지
- 각 사례의 핵심 특징과 성과

📊 사례별 성과
- 구체적인 수치나 개선 효과가 있다면 포함

답변:"""
        
        elif answer_type == "comparison":
            return base_context + """DRT 전문가로서 다음과 같이 비교 분석해주세요:

⚖️ 주요 차이점
- 핵심적인 차이점들을 명확히 구분하여 제시

📈 각각의 특징
- 비교 대상별 주요 특징과 장단점

🎯 적용 상황
- 어떤 상황에서 어떤 것이 더 적합한지

답변:"""
        
        elif answer_type == "comprehensive":
            return base_context + """DRT 전문가로서 다음과 같이 포괄적으로 설명해주세요:

🔍 1단계: 기본 개념
- 핵심 정의와 개념 설명

📊 2단계: 구성 요소
- 주요 구성요소나 특징들

💡 3단계: 실무 적용
- 실제 운영 방식이나 절차

✅ 4단계: 효과와 전망
- 기대 효과와 향후 발전 방향

답변:"""
        
        elif answer_type == "problem_solution":
            return base_context + """DRT 전문가로서 다음과 같이 문제 해결 방안을 제시해주세요:

🚨 문제 분석
- 현재 상황의 핵심 문제점들

💡 해결 방안
- 구체적이고 실행 가능한 해결책들

⚡ 실행 전략
- 단계별 실행 방법과 고려사항

답변:"""
        
        elif answer_type == "characteristics":
            return base_context + """DRT 전문가로서 다음과 같이 특징을 설명해주세요:

🔧 핵심 특징들
- 주요 특징이나 구성요소들을 체계적으로 제시

📋 구조적 특성
- 시스템의 구조나 작동 원리

🎯 차별화 요소
- 다른 시스템과 구별되는 고유한 특성

답변:"""
        
        else:  # general
            return base_context + """DRT 전문가로서 질문에 적절한 수준으로 답변해주세요:

💬 핵심 답변
- 질문에서 요구하는 정보를 명확하고 간결하게 제시
- 필요한 경우 추가 설명이나 배경 정보 포함

답변:"""
    
    def _calculate_enhanced_confidence(self, response: str, reasoning_steps: List[str], doc_count: int) -> float:
        """Calculate enhanced confidence for multi-query responses"""
        confidence = 0.6  # Higher base confidence for multi-query
        
        # Ensure response is a string
        if not isinstance(response, str):
            logger.warning(f"⚠️ Enhanced confidence: Response is not a string: {type(response)}")
            response = str(response) if response is not None else ""
        
        # Ensure doc_count is an integer
        if not isinstance(doc_count, int):
            logger.warning(f"⚠️ Enhanced confidence: doc_count is not an int: {type(doc_count)}")
            doc_count = 0
        
        # Boost based on document diversity
        if doc_count >= 10:
            confidence += 0.2
        elif doc_count >= 5:
            confidence += 0.1
        
        # Boost based on response length and structure
        if len(response.strip()) > 500:
            confidence += 0.1
        
        # Boost confidence if CoT steps are present
        if reasoning_steps:
            confidence += 0.1
        
        # Boost confidence if response contains structured elements
        if any(marker in response for marker in ["1단계", "2단계", "3단계", "4단계"]):
            confidence += 0.1
        
        # Boost if response mentions multiple aspects
        aspect_keywords = ["개념", "정의", "장점", "효과", "운영", "방식", "정책", "사례"]
        mentioned_aspects = sum(1 for keyword in aspect_keywords if keyword in response)
        if mentioned_aspects >= 4:
            confidence += 0.1
        elif mentioned_aspects >= 2:
            confidence += 0.05
        
        return min(0.95, confidence)
    
    async def reload_vectorstore(self) -> bool:
        """Reload vector store (read-only - requires external ETL)"""
        try:
            logger.info("🔄 Reloading vector store (read-only)...")
            
            # Reinitialize vector store
            await self._initialize_vectorstore_readonly()
            
            # Recreate RAG chain
            await self._setup_rag_chain()
            
            logger.info("✅ Vector store reloaded successfully (read-only)")
            logger.info("💡 To add/update documents, use DocumentETL job separately")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vector store reload failed: {e}")
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components"""
        try:
            embedding_health = await self.embedding_service.health_check()
            llm_health = await self.llm_service.health_check()
            
            vectorstore_health = bool(self.vectorstore)
            rag_chain_health = bool(self.rag_chain)
            
            overall_health = all([
                self._initialized,
                embedding_health,
                llm_health,
                vectorstore_health,
                rag_chain_health
            ])
            
            return {
                "status": "healthy" if overall_health else "unhealthy",
                "initialized": self._initialized,
                "components": {
                    "embedding_service": embedding_health,
                    "llm_service": llm_health,
                    "vectorstore": vectorstore_health,
                    "rag_chain": rag_chain_health
                },
                "cot_enabled": self.llm_service.enable_cot if self.llm_service else False
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def set_cot_mode(self, enable: bool) -> None:
        """Set CoT mode for the system"""
        if self.llm_service:
            self.llm_service.set_cot_mode(enable)
            
            # Recreate RAG chain with updated settings
            if self._initialized:
                await self._setup_rag_chain()
            
            logger.info(f"CoT mode updated to: {enable}")
    
    async def cleanup(self) -> None:
        """Cleanup all resources"""
        logger.info("🧹 Cleaning up RAG service...")
        
        if self.embedding_service:
            # Embedding service doesn't have cleanup method
            pass
        
        # No document loader service in read-only mode
        
        if self.llm_service:
            await self.llm_service.cleanup()
        
        self.vectorstore = None
        self.rag_chain = None
        self._initialized = False
        
        logger.info("✅ RAG service cleanup completed")