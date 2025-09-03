"""
Embedding service for text vectorization
"""

import logging
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime

from sentence_transformers import SentenceTransformer
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.core.exceptions import EmbeddingServiceException


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for text embeddings"""
    
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.langchain_embeddings: Optional[HuggingFaceEmbeddings] = None
        self._initialized = False
        self._health_status = False
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
    
    async def initialize(self) -> None:
        """Initialize embedding models"""
        
        if self._initialized:
            return
        
        logger.info(f"🚀 Initializing embedding service with model: {self.model_name}")
        
        try:
            # Load sentence transformer model
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: SentenceTransformer(self.model_name)
            )
            
            # Initialize LangChain embeddings wrapper
            self.langchain_embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},  # Use CPU for compatibility
                encode_kwargs={'normalize_embeddings': True}
            )
            
            # Test embeddings
            await self._test_embeddings()
            
            # Update dimension if needed
            loop = asyncio.get_event_loop()
            test_embedding = await loop.run_in_executor(
                None,
                lambda: self.model.encode(["test"], convert_to_tensor=False)[0]
            )
            self.dimension = len(test_embedding)
            
            self._initialized = True
            self._health_status = True
            
            logger.info(f"✅ Embedding service initialized successfully (dimension: {self.dimension})")
            
        except Exception as e:
            self._health_status = False
            logger.error(f"❌ Failed to initialize embedding service: {e}")
            raise EmbeddingServiceException(f"Embedding service initialization failed: {str(e)}")
    
    async def _test_embeddings(self) -> None:
        """Test embedding generation"""
        
        try:
            test_text = "This is a test sentence for embedding generation."
            
            # Test with sentence transformer
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self.model.encode([test_text], convert_to_tensor=False)[0]
            )
            
            if len(embedding) == 0:
                raise Exception("Empty embedding generated")
            
            logger.info("✅ Embedding test successful")
            
        except Exception as e:
            logger.error(f"❌ Embedding test failed: {e}")
            raise
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text"""
        
        if not self._initialized:
            raise EmbeddingServiceException("Embedding service not initialized")
        
        try:
            # Generate embedding in thread pool
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self.model.encode([text], convert_to_tensor=False)[0]
            )
            
            # Convert numpy array to list
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            raise EmbeddingServiceException(f"Text embedding failed: {str(e)}")
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        
        if not self._initialized:
            raise EmbeddingServiceException("Embedding service not initialized")
        
        try:
            # Generate embeddings in thread pool
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.model.encode(texts, convert_to_tensor=False)
            )
            
            # Convert numpy arrays to lists
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch text embedding failed: {e}")
            raise EmbeddingServiceException(f"Batch text embedding failed: {str(e)}")
    
    async def embed_with_langchain(self, text: str) -> List[float]:
        """Generate embedding using LangChain wrapper"""
        
        if not self._initialized or not self.langchain_embeddings:
            raise EmbeddingServiceException("LangChain embeddings not initialized")
        
        try:
            # Generate embedding in thread pool
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self.langchain_embeddings.embed_query(text)
            )
            
            return embedding
            
        except Exception as e:
            logger.error(f"LangChain embedding failed: {e}")
            raise EmbeddingServiceException(f"LangChain embedding failed: {str(e)}")
    
    async def embed_documents_with_langchain(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for documents using LangChain wrapper"""
        
        if not self._initialized or not self.langchain_embeddings:
            raise EmbeddingServiceException("LangChain embeddings not initialized")
        
        try:
            # Generate embeddings in thread pool
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.langchain_embeddings.embed_documents(texts)
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"LangChain document embedding failed: {e}")
            raise EmbeddingServiceException(f"LangChain document embedding failed: {str(e)}")
    
    async def calculate_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between embeddings"""
        
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            raise EmbeddingServiceException(f"Similarity calculation failed: {str(e)}")
    
    async def find_similar_texts(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]],
        threshold: float = 0.7,
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar texts based on embeddings"""
        
        try:
            similarities = []
            
            for i, candidate_embedding in enumerate(candidate_embeddings):
                similarity = await self.calculate_similarity(query_embedding, candidate_embedding)
                if similarity >= threshold:
                    similarities.append((i, similarity))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Return top k results
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Similar text search failed: {e}")
            raise EmbeddingServiceException(f"Similar text search failed: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check service health"""
        
        if not self._initialized:
            return False
        
        try:
            # Quick health check with simple text
            test_embedding = await self.embed_text("Health check test")
            self._health_status = len(test_embedding) == self.dimension
            return self._health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._health_status = False
            return False
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get embedding model information"""
        
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "initialized": self._initialized,
            "health_status": self._health_status,
            "langchain_available": self.langchain_embeddings is not None,
            "last_health_check": datetime.utcnow().isoformat()
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        
        logger.info("🧹 Cleaning up embedding service...")
        
        self.model = None
        self.langchain_embeddings = None
        self._initialized = False
        self._health_status = False
        
        logger.info("✅ Embedding service cleanup completed")