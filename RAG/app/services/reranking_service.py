"""
Re-ranking Service for Enhanced RAG Performance
"""

import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from langchain.schema import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.services.llm_service import LLMService
from app.core.exceptions import RAGServiceException

logger = logging.getLogger(__name__)


@dataclass
class RerankingScore:
    """Re-ranking score data class"""
    document_index: int
    relevance_score: float
    semantic_score: float
    importance_score: float
    freshness_score: float
    final_score: float
    reasoning: str


class RerankingService:
    """Document re-ranking service for better retrieval quality"""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.use_llm_reranking = llm_service is not None
        
        # LLM-based re-ranking prompt
        self.reranking_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 문서 관련성 평가 전문가입니다. 주어진 질문에 대해 각 문서의 관련성을 0.0-1.0 점수로 평가하세요.

평가 기준:
1. 직접적 관련성: 질문에 직접 답할 수 있는 정보 포함 여부
2. 의미적 유사성: 질문과 문서의 의미적 연관성
3. 정보 완성도: 포괄적이고 상세한 정보 제공 여부
4. 신뢰성: 공식 문서나 권위 있는 소스인지 여부

각 문서에 대해 다음 형식으로 평가하세요:
문서 [번호]: [점수] - [간단한 이유]

예시:
문서 1: 0.9 - DRT 정의와 개념을 자세히 설명
문서 2: 0.7 - DRT 장점 일부만 언급
문서 3: 0.3 - 간접적 관련성만 있음"""),
            ("human", """질문: {question}

문서들:
{documents}

각 문서의 관련성을 평가해주세요:""")
        ])
        
        logger.info(f"✅ Re-ranking service initialized (LLM-based: {self.use_llm_reranking})")
    
    async def rerank_documents(
        self, 
        query: str, 
        documents: List[Document], 
        top_k: int = 10
    ) -> List[Document]:
        """Re-rank documents based on multiple scoring criteria"""
        
        try:
            logger.info(f"🔄 Re-ranking {len(documents)} documents for query: {query[:50]}...")
            
            # Calculate multiple scores for each document
            scores = []
            for i, doc in enumerate(documents):
                score = await self._calculate_comprehensive_score(query, doc, i)
                scores.append(score)
            
            # Sort by final score (descending)
            scores.sort(key=lambda x: x.final_score, reverse=True)
            
            # Re-order documents based on scores
            reranked_documents = []
            for score in scores[:top_k]:
                doc = documents[score.document_index]
                # Add re-ranking metadata
                doc.metadata.update({
                    'rerank_score': score.final_score,
                    'relevance_score': score.relevance_score,
                    'semantic_score': score.semantic_score,
                    'importance_score': score.importance_score,
                    'freshness_score': score.freshness_score,
                    'rerank_reasoning': score.reasoning
                })
                reranked_documents.append(doc)
            
            logger.info(f"✅ Re-ranked to top {len(reranked_documents)} documents")
            logger.debug(f"Top 3 scores: {[f'{s.final_score:.3f}' for s in scores[:3]]}")
            
            return reranked_documents
            
        except Exception as e:
            logger.error(f"❌ Re-ranking failed: {e}")
            # Fallback: return original documents
            return documents[:top_k]
    
    async def _calculate_comprehensive_score(
        self, 
        query: str, 
        document: Document, 
        doc_index: int
    ) -> RerankingScore:
        """Calculate comprehensive score combining multiple factors"""
        
        # 1. Semantic similarity score (기존 벡터 검색 점수)
        semantic_score = self._calculate_semantic_score(query, document)
        
        # 2. Enhanced chunking importance score
        importance_score = self._get_importance_score(document)
        
        # 3. Document freshness/recency score
        freshness_score = self._calculate_freshness_score(document)
        
        # 4. LLM-based relevance score (optional)
        relevance_score = semantic_score  # Default to semantic score
        if self.use_llm_reranking:
            try:
                relevance_score = await self._calculate_llm_relevance_score(query, document)
            except Exception as e:
                logger.warning(f"LLM relevance scoring failed: {e}")
        
        # 5. Calculate final weighted score
        final_score = self._calculate_weighted_final_score(
            relevance_score, semantic_score, importance_score, freshness_score
        )
        
        # Generate reasoning
        reasoning = self._generate_score_reasoning(
            relevance_score, semantic_score, importance_score, freshness_score
        )
        
        return RerankingScore(
            document_index=doc_index,
            relevance_score=relevance_score,
            semantic_score=semantic_score,
            importance_score=importance_score,
            freshness_score=freshness_score,
            final_score=final_score,
            reasoning=reasoning
        )
    
    def _calculate_semantic_score(self, query: str, document: Document) -> float:
        """Calculate semantic similarity score"""
        
        # Use simple keyword matching as fallback
        query_words = set(query.lower().split())
        doc_words = set(document.page_content.lower().split())
        
        if not query_words:
            return 0.0
        
        # Jaccard similarity
        intersection = len(query_words.intersection(doc_words))
        union = len(query_words.union(doc_words))
        
        jaccard_score = intersection / union if union > 0 else 0.0
        
        # Boost for DRT-specific terms
        drt_terms = ['drt', '수요응답', '교통', '대중교통', '모빌리티', '교통체계']
        drt_boost = 0.0
        for term in drt_terms:
            if term in document.page_content.lower():
                drt_boost += 0.1
        
        return min(1.0, jaccard_score + drt_boost)
    
    def _get_importance_score(self, document: Document) -> float:
        """Get importance score from enhanced chunking metadata"""
        
        # Use enhanced chunking importance score if available
        enhanced_importance = document.metadata.get('importance_score', 0.5)
        
        # Boost based on chunk type
        chunk_type = document.metadata.get('chunk_type', 'paragraph')
        type_boost = {
            'title': 0.2,
            'section': 0.15,
            'paragraph': 0.0,
            'list': 0.05,
            'table': 0.1,
            'figure': 0.05
        }.get(chunk_type, 0.0)
        
        # Boost for high structure level (more important sections)
        structure_level = document.metadata.get('structure_level', 4)
        structure_boost = max(0, (4 - structure_level) * 0.05)
        
        return min(1.0, enhanced_importance + type_boost + structure_boost)
    
    def _calculate_freshness_score(self, document: Document) -> float:
        """Calculate document freshness/recency score"""
        
        # Check for recent indicators in metadata
        loaded_at = document.metadata.get('loaded_at', '')
        if '2025' in loaded_at:
            return 0.9
        elif '2024' in loaded_at:
            return 0.8
        elif '2023' in loaded_at:
            return 0.6
        else:
            return 0.4
    
    async def _calculate_llm_relevance_score(self, query: str, document: Document) -> float:
        """Calculate LLM-based relevance score"""
        
        if not self.llm_service or not self.llm_service.is_initialized():
            return 0.5
        
        try:
            # Prepare document summary for LLM evaluation
            doc_summary = document.page_content[:500] + "..." if len(document.page_content) > 500 else document.page_content
            
            # Create evaluation chain
            chain = self.reranking_prompt | self.llm_service.langchain_llm | StrOutputParser()
            
            # Get LLM evaluation
            response = await chain.ainvoke({
                "question": query,
                "documents": f"문서 1: {doc_summary}"
            })
            
            # Parse score from response
            score = self._parse_llm_score(response)
            return score
            
        except Exception as e:
            logger.warning(f"LLM relevance scoring failed: {e}")
            return 0.5
    
    def _parse_llm_score(self, response: str) -> float:
        """Parse score from LLM response"""
        
        import re
        
        # Look for score pattern (0.0 - 1.0)
        score_match = re.search(r'문서 1:\s*([0-9]*\.?[0-9]+)', response)
        if score_match:
            try:
                score = float(score_match.group(1))
                return min(1.0, max(0.0, score))
            except ValueError:
                pass
        
        # Fallback: analyze positive/negative keywords
        positive_keywords = ['관련', '중요', '포함', '설명', '상세', '적합']
        negative_keywords = ['무관', '부족', '간접', '제한', '부분']
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in response)
        negative_count = sum(1 for keyword in negative_keywords if keyword in response)
        
        if positive_count > negative_count:
            return 0.7
        elif negative_count > positive_count:
            return 0.3
        else:
            return 0.5
    
    def _calculate_weighted_final_score(
        self, 
        relevance_score: float, 
        semantic_score: float, 
        importance_score: float, 
        freshness_score: float
    ) -> float:
        """Calculate weighted final score"""
        
        # Weighted combination
        weights = {
            'relevance': 0.4,      # LLM-based relevance (highest weight)
            'semantic': 0.3,       # Semantic similarity
            'importance': 0.2,     # Enhanced chunking importance
            'freshness': 0.1       # Document freshness
        }
        
        final_score = (
            relevance_score * weights['relevance'] +
            semantic_score * weights['semantic'] +
            importance_score * weights['importance'] +
            freshness_score * weights['freshness']
        )
        
        return min(1.0, final_score)
    
    def _generate_score_reasoning(
        self,
        relevance_score: float,
        semantic_score: float, 
        importance_score: float,
        freshness_score: float
    ) -> str:
        """Generate human-readable reasoning for the score"""
        
        reasons = []
        
        if relevance_score >= 0.8:
            reasons.append("높은 관련성")
        elif relevance_score >= 0.6:
            reasons.append("보통 관련성")
        else:
            reasons.append("낮은 관련성")
        
        if importance_score >= 0.7:
            reasons.append("중요 섹션")
        elif importance_score >= 0.5:
            reasons.append("일반 섹션")
        
        if semantic_score >= 0.7:
            reasons.append("높은 의미 유사성")
        
        if freshness_score >= 0.8:
            reasons.append("최신 문서")
        
        return ", ".join(reasons) if reasons else "기본 점수"
    
    async def get_reranking_explanation(self, scores: List[RerankingScore]) -> str:
        """Generate explanation of re-ranking results"""
        
        explanation = "📊 문서 재순위 매기기 결과:\n\n"
        
        for i, score in enumerate(scores[:5], 1):
            explanation += f"{i}. 최종점수: {score.final_score:.3f}\n"
            explanation += f"   - 관련성: {score.relevance_score:.2f}, 의미유사성: {score.semantic_score:.2f}\n"
            explanation += f"   - 중요도: {score.importance_score:.2f}, 신선도: {score.freshness_score:.2f}\n"
            explanation += f"   - 사유: {score.reasoning}\n\n"
        
        return explanation
    
    async def health_check(self) -> bool:
        """Check service health"""
        try:
            # Test basic functionality
            test_doc = Document(
                page_content="DRT 수요응답형 교통 테스트 문서",
                metadata={'importance_score': 0.7, 'chunk_type': 'paragraph'}
            )
            
            scores = await self._calculate_comprehensive_score("DRT 테스트", test_doc, 0)
            return scores.final_score > 0.0
            
        except Exception as e:
            logger.error(f"Re-ranking service health check failed: {e}")
            return False


class RerankingException(RAGServiceException):
    """Re-ranking service specific exceptions"""
    pass