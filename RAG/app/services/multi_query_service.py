"""
Multi-Query Generation Service for Enhanced RAG Performance
"""

import logging
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.services.llm_service import LLMService
from app.core.exceptions import RAGServiceException

logger = logging.getLogger(__name__)


class MultiQueryService:
    """Multi-query generation service for diverse information retrieval"""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
        # Multi-query generation prompt template - 질문 의도 중심으로 개선
        self.multi_query_prompt = ChatPromptTemplate.from_messages([
            ("system", """주어진 질문의 핵심 의도를 파악하고, 그 의도에 맞는 유사한 검색 쿼리 3개를 생성하세요.

생성 규칙:
1. 원래 질문의 핵심 의도와 목적을 정확히 유지
2. 동일한 정보를 찾기 위한 다른 표현이나 키워드 사용
3. 질문 범위를 넓히지 말고 같은 범위 내에서 다각도 접근

예시:
질문: "DRT의 정의는?"
답변:
수요응답형 교통의 정의
DRT 개념과 의미
Demand Responsive Transport 정의

질문: "DRT 시스템의 장점은?"
답변:  
수요응답형 교통의 이점
DRT 도입 효과
DRT 서비스 장점

질문: "DRT 운영 방법은?"
답변:
수요응답형 교통 운영 절차
DRT 시스템 운영 방식  
DRT 서비스 운영 프로세스

중요: 질문이 특정한 주제(정의, 장점, 방법 등)를 묻는다면 그 범위를 벗어나지 마세요."""),
            ("human", "질문: {question}\n답변:")
        ])
        
        logger.info("✅ Multi-query service initialized")
    
    async def generate_multiple_queries(self, original_query: str) -> List[str]:
        """Generate multiple search queries from a single original query"""
        
        try:
            if not self.llm_service.is_initialized():
                await self.llm_service.initialize()
            
            # Generate multi-queries using LLM
            chain = self.multi_query_prompt | self.llm_service.langchain_llm | StrOutputParser()
            
            logger.info(f"🔍 Generating multiple queries for: {original_query[:50]}...")
            
            response = await chain.ainvoke({"question": original_query})
            
            # Parse the response to extract individual queries
            queries = self._parse_generated_queries(response, original_query)
            
            logger.info(f"✅ Generated {len(queries)} diverse queries")
            for i, query in enumerate(queries, 1):
                logger.debug(f"Query {i}: {query}")
            
            return queries
            
        except Exception as e:
            logger.error(f"❌ Failed to generate multiple queries: {e}")
            # Fallback: return original query with basic variations
            return self._generate_fallback_queries(original_query)
    
    def _parse_generated_queries(self, response: str, original_query: str) -> List[str]:
        """Parse LLM response to extract individual queries"""
        
        queries = [original_query]  # Always include original query
        
        # Split by lines and extract valid queries
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Remove bullet points, dashes, numbers
            line = line.lstrip('- •·* 0123456789.)')
            line = line.strip()
            
            # Skip empty lines or too short queries
            if len(line) < 10:
                continue
            
            # Skip if too similar to original query
            if line.lower() == original_query.lower():
                continue
            
            # Add valid query
            if line not in queries:
                queries.append(line)
        
        # Limit to maximum 4 queries (원본 + 3개 변형)
        return queries[:4]
    
    def _generate_fallback_queries(self, original_query: str) -> List[str]:
        """Generate fallback queries when LLM generation fails"""
        
        logger.warning("🔄 Using fallback query generation")
        
        fallback_queries = [original_query]  # 항상 원본 질문 포함
        
        # 질문 의도에 맞는 동의어/유사 표현 생성
        if "정의" in original_query or "무엇" in original_query:
            # 정의 관련 질문의 경우
            fallback_queries.append(original_query.replace("정의", "개념").replace("무엇인가", "의미"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        elif "장점" in original_query or "효과" in original_query:
            # 장점/효과 관련 질문의 경우
            fallback_queries.append(original_query.replace("장점", "이점").replace("효과", "혜택"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        elif "방법" in original_query or "어떻게" in original_query:
            # 방법 관련 질문의 경우  
            fallback_queries.append(original_query.replace("방법", "방식").replace("어떻게", "어떤 방식으로"))
            fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
            
        else:
            # 일반적인 경우 - 키워드만 변형
            if "DRT" in original_query:
                fallback_queries.append(original_query.replace("DRT", "수요응답형교통"))
                fallback_queries.append(original_query.replace("DRT", "demand responsive transport"))
        
        return list(set(fallback_queries))[:4]  # 중복 제거하고 최대 4개
    
    async def generate_contextual_queries(
        self, 
        original_query: str, 
        context_keywords: List[str] = None
    ) -> List[str]:
        """Generate contextual queries based on domain keywords"""
        
        try:
            # Base queries from multi-query generation
            base_queries = await self.generate_multiple_queries(original_query)
            
            # Add context-specific queries if keywords provided
            if context_keywords:
                contextual_queries = []
                
                for keyword in context_keywords[:3]:  # Limit context keywords
                    contextual_query = f"{keyword}와 관련된 {original_query}"
                    contextual_queries.append(contextual_query)
                
                # Combine and deduplicate
                all_queries = base_queries + contextual_queries
                return list(set(all_queries))[:7]  # Limit total queries
            
            return base_queries
            
        except Exception as e:
            logger.error(f"❌ Failed to generate contextual queries: {e}")
            return [original_query]
    
    async def health_check(self) -> bool:
        """Check service health"""
        try:
            if not self.llm_service.is_initialized():
                return False
            
            # Test query generation
            test_queries = await self.generate_multiple_queries("테스트 질문")
            return len(test_queries) > 0
            
        except Exception as e:
            logger.error(f"Multi-query service health check failed: {e}")
            return False


class MultiQueryException(RAGServiceException):
    """Multi-query service specific exceptions"""
    pass