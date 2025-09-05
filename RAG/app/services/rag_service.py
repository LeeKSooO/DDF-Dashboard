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
from langchain.schema import Document

from app.core.config import settings
from app.core.exceptions import RAGServiceException
from app.services.embedding_service import EmbeddingService
from app.services.document_loader_service import DocumentLoaderService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class RAGService:
    """Comprehensive RAG service with CoT enhancement"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.document_loader_service = DocumentLoaderService()
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
            # Initialize all services
            await self.embedding_service.initialize()
            await self.document_loader_service.initialize()
            await self.llm_service.initialize()
            
            # Initialize vector store
            await self._initialize_vectorstore()
            
            # Setup RAG chain
            await self._setup_rag_chain()
            
            self._initialized = True
            logger.info("✅ RAG service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ RAG service initialization failed: {e}")
            return False
    
    async def _initialize_vectorstore(self) -> None:
        """Initialize Chroma vector store"""
        logger.info("📚 Initializing vector store...")
        
        chroma_path = Path(settings.CHROMA_PERSIST_DIR)
        
        try:
            if chroma_path.exists() and any(chroma_path.iterdir()):
                # Load existing vector store
                logger.info("Loading existing vector store...")
                self.vectorstore = Chroma(
                    persist_directory=str(chroma_path),
                    embedding_function=self.embedding_service.langchain_embeddings
                )
                
                # Check if we need to add new documents
                await self._update_vectorstore_if_needed()
                
            else:
                # Create new vector store
                logger.info("Creating new vector store...")
                await self._create_new_vectorstore()
                
            logger.info(f"✅ Vector store initialized at {chroma_path}")
            
        except Exception as e:
            logger.error(f"❌ Vector store initialization failed: {e}")
            raise RAGServiceException(f"Vector store initialization error: {e}")
    
    async def _create_new_vectorstore(self) -> None:
        """Create new vector store from documents"""
        documents_path = Path("./data/documents")
        
        if not documents_path.exists():
            logger.warning(f"Documents directory not found: {documents_path}")
            return
        
        # Load and process documents
        documents = await self.document_loader_service.load_documents_from_directory(
            str(documents_path)
        )
        
        if not documents:
            logger.warning("No documents found to create vector store")
            return
        
        logger.info(f"Creating vector store from {len(documents)} documents...")
        
        # Create vector store
        self.vectorstore = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: Chroma.from_documents(
                documents=documents,
                embedding=self.embedding_service.langchain_embeddings,
                persist_directory=settings.CHROMA_PERSIST_DIR
            )
        )
        
        logger.info("✅ Vector store created successfully")
    
    async def _update_vectorstore_if_needed(self) -> None:
        """Update vector store with new documents if any"""
        documents_path = Path("./data/documents")
        
        if not documents_path.exists():
            return
        
        # Check for new documents
        new_docs = await self.document_loader_service.get_new_documents(
            str(documents_path)
        )
        
        if new_docs:
            logger.info(f"Adding {len(new_docs)} new documents to vector store...")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.vectorstore.add_documents(new_docs)
            )
            logger.info("✅ Vector store updated with new documents")
    
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
        """Query the RAG system"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")
        
        if not self.rag_chain:
            raise RAGServiceException("RAG chain not setup")
        
        try:
            logger.info(f"🔍 Processing query: {question[:50]}...")
            
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
                "cot_enabled": self.llm_service.enable_cot
            }
            
            logger.info(f"✅ Query processed successfully (confidence: {confidence:.0%})")
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
    
    async def reload_documents(self) -> bool:
        """Reload documents and recreate vector store"""
        try:
            logger.info("🔄 Reloading documents...")
            
            # Clear existing vector store
            if self.vectorstore:
                # Remove existing store
                chroma_path = Path(settings.CHROMA_PERSIST_DIR)
                if chroma_path.exists():
                    import shutil
                    shutil.rmtree(chroma_path)
            
            # Recreate vector store
            await self._create_new_vectorstore()
            
            # Recreate RAG chain
            await self._setup_rag_chain()
            
            logger.info("✅ Documents reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Document reload failed: {e}")
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
        
        if self.document_loader_service:
            # Document loader service doesn't have cleanup method
            pass
        
        if self.llm_service:
            await self.llm_service.cleanup()
        
        self.vectorstore = None
        self.rag_chain = None
        self._initialized = False
        
        logger.info("✅ RAG service cleanup completed")