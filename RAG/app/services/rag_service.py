"""
RAG service that integrates all components with CoT functionality
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import pytz

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
from app.services.question_classifier_service import QuestionClassifierService, QuestionType, ClassificationResult
from app.services.text_to_sql_service import TextToSQLService, SQLGenerationResult

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
        self.question_classifier = None  # Initialize later after llm_service
        self.text_to_sql_service = None  # Initialize later after llm_service
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

            # Initialize question classifier
            self.question_classifier = QuestionClassifierService(self.llm_service)

            # Initialize Text-to-SQL service
            self.text_to_sql_service = TextToSQLService(self.llm_service)
            
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
                search_kwargs={"k": 10}
            )
            
            # CoT-enhanced prompt template with detailed response guidance
            cot_prompt = PromptTemplate(
                template="""당신은 DRT(수요응답형 교통) 전문 분석가입니다. 매우 상세하고 포괄적인 답변을 제공해주세요.

다음과 같이 단계별로 충분히 상세하게 분석하여 답변해주세요:

🔍 1단계: 질문 이해 및 배경 분석 (최소 2-3문단)
- 질문에서 요구하는 정보의 핵심을 명확히 파악하고 설명
- DRT 시스템의 어떤 측면과 관련되는지 구체적으로 식별
- 질문의 맥락과 중요성을 상세히 설명
- 관련된 정책적, 기술적 배경까지 포함하여 분석

📚 2단계: 문헌 및 데이터 심층 검토 (최소 3-4문단)
- 제공된 참고자료를 체계적이고 상세하게 검토
- 질문과 관련된 핵심 정보를 다각도로 추출하고 분석
- 관련 이론, 연구 결과, 실무 사례를 포함하여 설명
- 데이터나 수치가 있다면 구체적으로 제시하고 해석

🧠 3단계: 전문적 분석 및 심화 논의 (최소 4-5문단)
- DRT 이론과 실무 경험을 바탕으로 단계적 논리를 상세히 전개
- 각 추론 단계의 근거를 구체적으로 명시
- 다양한 관점에서 문제를 분석하고 비교 검토
- 장단점, 한계점, 개선 방안을 포함하여 종합적으로 분석
- 국내외 사례나 벤치마크가 있다면 비교 분석

✅ 4단계: 종합 결론 및 실무적 제안 (최소 3-4문단)
- 앞선 분석을 종합하여 구체적이고 실용적인 답변을 상세히 제공
- 핵심 포인트를 명확하게 정리하고 설명
- 실무에 적용 가능한 구체적인 제안이나 가이드라인 제시
- 향후 발전 방향이나 추가 고려사항을 상세히 언급
- 결론의 신뢰도와 한계점을 투명하게 제시

**중요: 각 단계마다 충분한 분량의 상세한 설명을 작성하되, 최종 답변은 최소 1500자 이상의 포괄적이고 유익한 내용이 되도록 해주세요.**

질문: {question}
참고자료:
{context}

단계별 상세 분석:""",
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
        """Query the RAG system with question classification (read-only)"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")

        if not self.rag_chain:
            raise RAGServiceException("RAG chain not setup")

        if not self.vectorstore:
            raise RAGServiceException("No vector store available - run DocumentETL job first")

        try:
            logger.info(f"🔍 Processing read-only query: {question[:50]}...")

            # Step 0: Add current time context to question
            question_with_time = self._add_time_context(question)

            # Step 1: Classify question
            classification_result = await self.question_classifier.classify_question(question_with_time)

            # Step 2: Handle different question types
            if classification_result.question_type == QuestionType.QUANTITATIVE:
                logger.info("🔢 Processing QUANTITATIVE question with Text-to-SQL")
                try:
                    # Use Text-to-SQL for quantitative questions
                    sql_result = await self.text_to_sql_service.generate_sql(question)
                    logger.info(f"📝 Generated SQL: {sql_result.generated_sql}")

                    sql_data = await self.text_to_sql_service.execute_sql(sql_result.generated_sql)
                    logger.info(f"🎯 SQL execution result: success={sql_data.get('success', False)}, rows={sql_data.get('row_count', 0)}")

                    # Generate natural language response from SQL results
                    response = await self._generate_sql_response(question, sql_result, sql_data)

                    # Store SQL information for response
                    sql_info = {
                        "sql_query": sql_result.generated_sql,
                        "sql_confidence": sql_result.confidence,
                        "sql_reasoning": sql_result.reasoning,
                        "execution_success": sql_data.get("success", False),
                        "row_count": sql_data.get("row_count", 0)
                    }
                except Exception as e:
                    logger.error(f"❌ Text-to-SQL processing failed: {e}")
                    # Fallback to RAG for failed SQL queries
                    logger.info("🔄 Falling back to RAG response")
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.rag_chain.invoke(question)
                    )
                    sql_info = {
                        "error": str(e),
                        "fallback_to_rag": True
                    }

            elif classification_result.question_type == QuestionType.MIXED:
                # Use both SQL and RAG for mixed questions
                sql_result = await self.text_to_sql_service.generate_sql(question)
                sql_data = await self.text_to_sql_service.execute_sql(sql_result.generated_sql)

                # Also get RAG response
                rag_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.rag_chain.invoke(question)
                )

                # Combine both responses
                response = await self._generate_hybrid_response(question, sql_result, sql_data, rag_response)

                sql_info = {
                    "sql_query": sql_result.generated_sql,
                    "sql_confidence": sql_result.confidence,
                    "sql_reasoning": sql_result.reasoning,
                    "execution_success": sql_data.get("success", False),
                    "row_count": sql_data.get("row_count", 0),
                    "hybrid_mode": True
                }

            elif classification_result.question_type == QuestionType.QUALITATIVE:
                logger.info("📚 Processing QUALITATIVE question with RAG")
                # Use RAG for qualitative questions
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.rag_chain.invoke(question)
                )
                sql_info = None

            elif classification_result.question_type == QuestionType.IRRELEVANT:
                logger.info("❌ Processing IRRELEVANT question")
                response = "죄송합니다. 해당 질문은 DRT(수요응답형 교통) 시스템과 관련이 없어 답변을 제공할 수 없습니다. DRT 운영, 정책, 기술적 내용에 관한 질문을 해주시기 바랍니다."
                sql_info = None

            else:
                logger.warning(f"⚠️ Unknown question type: {classification_result.question_type}")
                # Fallback to RAG
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.rag_chain.invoke(question)
                )
                sql_info = None

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
                "mode": "read_only",
                "question_classification": {
                    "type": classification_result.question_type.value,
                    "confidence": classification_result.confidence,
                    "reasoning": classification_result.reasoning,
                    "keywords": classification_result.keywords,
                    "needs_sql": classification_result.needs_sql,
                    "needs_rag": classification_result.needs_rag
                },
                "sql_info": sql_info
            }

            logger.info(f"✅ Read-only query processed successfully (confidence: {confidence:.0%}, type: {classification_result.question_type.value})")
            return result

        except Exception as e:
            logger.error(f"❌ Query processing failed: {e}")
            raise RAGServiceException(f"Query processing error: {e}")

    async def _generate_sql_response(self, question: str, sql_result, sql_data: Dict[str, Any]) -> str:
        """SQL 결과를 자연어 응답으로 변환"""
        try:
            if not sql_data.get("success", False):
                return f"죄송합니다. 데이터 조회 중 오류가 발생했습니다: {sql_data.get('error', '알 수 없는 오류')}"

            data = sql_data.get("data", [])
            row_count = sql_data.get("row_count", 0)

            if row_count == 0:
                return "조회 조건에 맞는 데이터가 없습니다."

            # 데이터 요약 생성
            data_summary = self._format_sql_results(data, row_count)

            # 자연어 응답 생성을 위한 상세한 프롬프트
            response_prompt = f"""다음 SQL 쿼리 결과를 바탕으로 사용자 질문에 대한 매우 상세하고 포괄적인 답변을 생성해주세요.

사용자 질문: {question}

실행된 SQL: {sql_result.generated_sql}

쿼리 결과:
{data_summary}

상세 답변 가이드라인:
1. **데이터 요약 및 핵심 수치 제시** (2-3문단)
   - 쿼리 결과의 주요 숫자와 데이터를 명확하고 구체적으로 제시
   - 데이터의 의미와 중요성을 설명

2. **심층 분석 및 인사이트** (3-4문단)
   - 데이터에서 도출되는 주요 패턴, 트렌드, 특징을 상세히 분석
   - 시간적, 공간적, 구조적 관점에서 데이터를 해석
   - 예상 가능한 원인이나 배경 요인을 논의

3. **비교 분석 및 맥락 설명** (2-3문단)
   - 가능한 경우 이전 데이터나 다른 지역/시간대와의 비교
   - 업계 표준이나 벤치마크와의 비교 분석
   - DRT 시스템 관점에서의 해석

4. **실무적 함의 및 제안** (2-3문단)
   - 데이터가 시사하는 실무적 의미와 영향
   - 개선 방안이나 추가 조치 사항 제안
   - 향후 모니터링이나 추가 분석이 필요한 영역 제시

**중요: 최소 1200자 이상의 상세하고 유익한 답변을 작성해주세요. 친근하면서도 전문적인 어조를 유지하되, 충분한 정보를 제공해주세요.**

상세 답변:"""

            response = await self.llm_service.generate_text(response_prompt)
            return response

        except Exception as e:
            logger.error(f"Failed to generate SQL response: {e}")
            return f"데이터 처리 중 오류가 발생했습니다: {str(e)}"

    async def _generate_hybrid_response(
        self,
        question: str,
        sql_result,
        sql_data: Dict[str, Any],
        rag_response: str
    ) -> str:
        """SQL과 RAG 결과를 결합한 하이브리드 응답 생성"""
        try:
            # SQL 결과 요약
            if sql_data.get("success", False) and sql_data.get("row_count", 0) > 0:
                sql_summary = self._format_sql_results(sql_data.get("data", []), sql_data.get("row_count", 0))
            else:
                sql_summary = "데이터 조회에 실패했거나 결과가 없습니다."

            # 하이브리드 응답 생성을 위한 상세한 프롬프트
            hybrid_prompt = f"""다음 질문에 대해 정량적 데이터와 정성적 설명을 결합한 매우 포괄적이고 상세한 종합 답변을 생성해주세요.

사용자 질문: {question}

=== 정량적 데이터 (SQL 쿼리 결과) ===
실행된 SQL: {sql_result.generated_sql}
결과 데이터:
{sql_summary}

=== 정성적 설명 (문서 기반 RAG) ===
{rag_response}

=== 상세 종합 답변 지침 ===

1. **데이터 기반 현황 분석** (3-4문단)
   - 구체적인 숫자와 데이터를 명확하게 제시하고 해석
   - 데이터가 보여주는 현재 상황을 상세히 분석
   - 수치의 의미와 중요성을 맥락과 함께 설명

2. **이론적 배경 및 맥락 설명** (3-4문단)
   - 문서 기반 정성적 정보를 체계적으로 정리
   - 관련 이론, 원칙, 정책적 배경을 상세히 설명
   - 데이터와 이론적 배경 간의 연관성을 명확히 제시

3. **통합 분석 및 심화 논의** (4-5문단)
   - 정량적 데이터와 정성적 정보를 종합하여 심층 분석
   - 데이터에서 나타나는 패턴과 이론적 설명 간의 일치/불일치 분석
   - 다각도 관점에서 현상을 해석하고 원인 분석
   - 국내외 사례나 벤치마크와의 비교 검토

4. **실무적 함의 및 종합 제안** (3-4문단)
   - 분석 결과가 시사하는 실무적 의미와 영향을 종합적으로 제시
   - 데이터와 이론을 바탕으로 한 구체적 개선 방안 제안
   - 단기/중기/장기적 관점에서의 발전 방향 제시
   - 향후 모니터링이나 추가 연구가 필요한 영역 제안

**중요: 정량적 데이터와 정성적 설명이 유기적으로 연결된 최소 1800자 이상의 종합적이고 균형잡힌 답변을 작성해주세요.**

종합 상세 답변:"""

            response = await self.llm_service.generate_text(hybrid_prompt)
            return response

        except Exception as e:
            logger.error(f"Failed to generate hybrid response: {e}")
            return f"응답 생성 중 오류가 발생했습니다: {str(e)}"

    def _format_sql_results(self, data: list, row_count: int, max_rows: int = 10) -> str:
        """SQL 결과를 읽기 쉬운 형태로 포맷"""
        if not data or row_count == 0:
            return "결과가 없습니다."

        try:
            # 컬럼명 추출
            if isinstance(data[0], dict):
                columns = list(data[0].keys())
            else:
                columns = [f"column_{i}" for i in range(len(data[0]))]

            # 표시할 행 수 제한
            display_data = data[:max_rows]

            # 테이블 형태로 포맷
            formatted_lines = []
            formatted_lines.append(f"총 {row_count}건의 결과 (상위 {len(display_data)}건 표시)")
            formatted_lines.append("")

            # 헤더
            header = " | ".join(columns)
            formatted_lines.append(header)
            formatted_lines.append("-" * len(header))

            # 데이터 행들
            for row in display_data:
                if isinstance(row, dict):
                    values = [str(row.get(col, "")) for col in columns]
                else:
                    values = [str(val) for val in row]

                formatted_lines.append(" | ".join(values))

            if row_count > max_rows:
                formatted_lines.append(f"... 및 {row_count - max_rows}건 추가")

            return "\n".join(formatted_lines)

        except Exception as e:
            logger.error(f"Failed to format SQL results: {e}")
            return f"결과 포맷팅 오류: {str(e)}"
    
    async def multi_query(self, question: str, max_results: int = 10) -> Dict[str, Any]:
        """Enhanced query with multi-query generation and question classification"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")

        if not self.vectorstore:
            raise RAGServiceException("No vector store available - run DocumentETL job first")

        if not self.multi_query_service:
            raise RAGServiceException("Multi-query service not initialized")

        try:
            logger.info(f"🔍 Processing multi-query: {question[:50]}...")

            # Step 1: Classify question
            classification_result = await self.question_classifier.classify_question(question)

            # Step 2: Generate multiple diverse queries
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
                "top_rerank_scores": [doc.metadata.get('rerank_score', 0.0) for doc in top_documents[:5]],
                "question_classification": {
                    "type": classification_result.question_type.value,
                    "confidence": classification_result.confidence,
                    "reasoning": classification_result.reasoning,
                    "keywords": classification_result.keywords,
                    "needs_sql": classification_result.needs_sql,
                    "needs_rag": classification_result.needs_rag
                }
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
    
    def set_llm(self, new_llm):
        """평가를 위한 LLM 동적 교체"""
        from langchain_core.language_models import BaseLanguageModel
        
        if not isinstance(new_llm, BaseLanguageModel):
            raise ValueError("new_llm must be a LangChain BaseLanguageModel instance")
        
        # LLM 교체
        self.llm_service.langchain_llm = new_llm
        
        # RAG 체인 재구성
        if self._initialized and self.vectorstore:
            self._setup_rag_chain()
            logger.info(f"✅ LLM updated and RAG chain reconfigured")

    async def get_source_documents_for_evaluation(self, question: str) -> List:
        """평가용 source documents 반환 (답변 생성 없이)"""
        if not self._initialized:
            raise RAGServiceException("RAG service not initialized")
        
        if not self.vectorstore:
            raise RAGServiceException("No vector store available")
        
        try:
            # 기본 retrieval 사용
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": settings.MAX_RESULTS}
            )
            
            # 문서 검색만 수행
            docs = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: retriever.get_relevant_documents(question)
            )
            
            return docs
            
        except Exception as e:
            logger.error(f"❌ Document retrieval failed: {e}")
            return []

    def _add_time_context(self, question: str) -> str:
        """질문에 현재 시간 컨텍스트를 추가"""
        try:
            # 한국 시간 기준으로 현재 시간 정보 추가
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            today = now.date()

            # 상대적 시간 표현 변환
            time_replacements = {
                r'오늘': f'{today.strftime("%Y년 %m월 %d일")} ({today})',
                r'어제': f'{(today - timedelta(days=1)).strftime("%Y년 %m월 %d일")} ({today - timedelta(days=1)})',
                r'그저께': f'{(today - timedelta(days=2)).strftime("%Y년 %m월 %d일")} ({today - timedelta(days=2)})',
                r'내일': f'{(today + timedelta(days=1)).strftime("%Y년 %m월 %d일")} ({today + timedelta(days=1)})',
                r'모레': f'{(today + timedelta(days=2)).strftime("%Y년 %m월 %d일")} ({today + timedelta(days=2)})',
                r'이번 주': f'2025년 7월 3째주 ({today})',
                r'이번 달': f'2025년 7월 ({today})',
                r'올해': f'2025년 ({today})'
            }

            # 질문에서 상대적 시간 표현을 절대적 표현으로 변환
            processed_question = question
            for pattern, replacement in time_replacements.items():
                import re
                processed_question = re.sub(pattern, replacement, processed_question)

            # 현재 시간 정보가 필요한 질문인지 확인
            time_keywords = ['오늘', '현재', '지금', '최근', '이번', '요즘']
            if any(keyword in question for keyword in time_keywords):
                # 시간 컨텍스트 정보 추가
                time_context = f"""

[현재 시간 정보]
- 현재 날짜: {today} ({today.strftime('%Y년 %m월 %d일, %A')})
- 현재 시간: {now.strftime('%H:%M:%S')} (한국 시간)
- 데이터 수집 기간: 2025년 7월 19일 ~ 2025년 7월 31일
"""
                processed_question += time_context

            return processed_question

        except Exception as e:
            logger.warning(f"Time context addition failed: {e}")
            return question

    def is_evaluation_ready(self) -> bool:
        """평가 준비 상태 확인"""
        checks = {
            "initialized": self._initialized,
            "vectorstore": self.vectorstore is not None,
            "llm_service": self.llm_service is not None,
            "embedding_service": self.embedding_service is not None
        }

        all_ready = all(checks.values())

        if not all_ready:
            logger.warning(f"❌ RAG service not ready for evaluation: {checks}")

        return all_ready