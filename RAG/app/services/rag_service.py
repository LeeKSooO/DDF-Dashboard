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

logger = logging.getLogger(__name__)


class RAGService:
    """Read-only RAG service with CoT enhancement
    
    This service only queries existing vector stores and does not handle document loading.
    Document ETL should be done separately using the DocumentETL job.
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
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
    
    def _calculate_confidence(self, response: str, reasoning_steps: List[str]) -> float:
        """Calculate response confidence"""
        confidence = 0.5  # base confidence
        
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