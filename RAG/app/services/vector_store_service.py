"""
Vector store service for similarity search
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.vectorstores import Chroma

from app.core.config import settings
from app.core.exceptions import VectorStoreException
from app.services.embedding_service import EmbeddingService


logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for vector storage and similarity search"""
    
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.chroma_client: Optional[chromadb.Client] = None
        self.collection = None
        self.langchain_vectorstore: Optional[Chroma] = None
        self._initialized = False
        self._health_status = False
    
    async def initialize(self, document_loader_service=None) -> None:
        """Initialize vector store and load documents if configured"""
        
        if self._initialized:
            return
        
        logger.info("🚀 Initializing vector store service...")
        
        try:
            # Initialize Chroma client
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(
                    allow_reset=True,
                    anonymized_telemetry=False
                )
            )
            
            # Get or create collection
            collection_name = "rag_knowledge_base"
            self.collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "RAG knowledge base for SQL generation"}
            )
            
            # Initialize LangChain vector store wrapper
            self.langchain_vectorstore = Chroma(
                client=self.chroma_client,
                collection_name=collection_name,
                embedding_function=self.embedding_service.langchain_embeddings
            )
            
            # Mark as initialized before loading documents
            self._initialized = True
            self._health_status = True
            
            # Load documents if configured and document loader is available
            await self._load_initial_documents(document_loader_service)
            
            logger.info("✅ Vector store service initialized successfully")
            
        except Exception as e:
            self._health_status = False
            logger.error(f"❌ Failed to initialize vector store service: {e}")
            raise VectorStoreException(f"Vector store initialization failed: {str(e)}")
    
    async def add_documents(
        self, 
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to vector store"""
        
        if not self._initialized:
            raise VectorStoreException("Vector store not initialized")
        
        try:
            # Generate embeddings
            embeddings = await self.embedding_service.embed_texts(documents)
            
            # Generate IDs if not provided
            if not ids:
                ids = [f"doc_{i}_{datetime.utcnow().timestamp()}" for i in range(len(documents))]
            
            # Prepare metadata
            if not metadata:
                metadata = [{"source": "unknown"} for _ in documents]
            
            # Add to collection
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadata,
                ids=ids
            )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            return ids
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise VectorStoreException(f"Document addition failed: {str(e)}")
    
    async def search_similar(
        self, 
        query: str,
        k: int = 5,
        similarity_threshold: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar documents"""
        
        if not self._initialized:
            raise VectorStoreException("Vector store not initialized")
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Search in collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=metadata_filter
            )
            
            # Filter by similarity threshold and format results
            similar_docs = []
            if results['documents'] and results['distances'] and results['metadatas']:
                for doc, distance, metadata in zip(
                    results['documents'][0],
                    results['distances'][0], 
                    results['metadatas'][0]
                ):
                    # Convert distance to similarity (assuming cosine distance)
                    similarity = 1 - distance
                    if similarity >= similarity_threshold:
                        similar_docs.append((doc, similarity, metadata))
            
            logger.info(f"Found {len(similar_docs)} similar documents for query")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Similar search failed: {e}")
            raise VectorStoreException(f"Similar search failed: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check service health"""
        
        if not self._initialized:
            return False
        
        try:
            # Simple health check - get collection info
            count = self.collection.count()
            self._health_status = True
            logger.debug(f"Vector store health check: {count} documents in collection")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._health_status = False
            return False
    
    async def _load_initial_documents(self, document_loader_service) -> None:
        """Load initial documents from configured directories"""
        
        if not document_loader_service:
            logger.info("No document loader service provided, skipping document loading")
            return
        
        # Check if collection already has documents
        existing_count = self.collection.count()
        if existing_count > 0:
            logger.info(f"Vector store already contains {existing_count} documents, skipping initial load")
            return
        
        # Get document paths from settings
        document_paths = getattr(settings, 'DOCUMENT_PATHS', [])
        if not document_paths:
            logger.info("No document paths configured in settings")
            return
        
        logger.info(f"Loading initial documents from {len(document_paths)} configured paths...")
        
        total_chunks = 0
        for doc_path in document_paths:
            try:
                if doc_path.get("type") == "directory":
                    chunks = await document_loader_service.load_directory_and_chunk(
                        directory_path=doc_path["path"],
                        glob_pattern=doc_path.get("pattern", "**/*.pdf"),
                        chunk_size=doc_path.get("chunk_size", 1500),
                        chunk_overlap=doc_path.get("chunk_overlap", 300)
                    )
                elif doc_path.get("type") == "file":
                    chunks = await document_loader_service.load_and_chunk(
                        file_path=doc_path["path"],
                        chunk_size=doc_path.get("chunk_size", 1500),
                        chunk_overlap=doc_path.get("chunk_overlap", 300)
                    )
                else:
                    logger.warning(f"Unknown document path type: {doc_path.get('type')}")
                    continue
                
                if chunks:
                    # Add chunks to vector store
                    documents = [chunk.page_content for chunk in chunks]
                    metadata = [chunk.metadata for chunk in chunks]
                    
                    await self.add_documents(documents=documents, metadata=metadata)
                    total_chunks += len(chunks)
                    
                    logger.info(f"Loaded {len(chunks)} chunks from {doc_path['path']}")
                
            except Exception as e:
                logger.error(f"Failed to load documents from {doc_path['path']}: {e}")
        
        logger.info(f"✅ Initial document loading completed: {total_chunks} total chunks loaded")

    async def cleanup(self) -> None:
        """Cleanup resources"""
        
        logger.info("🧹 Cleaning up vector store service...")
        
        self.collection = None
        self.chroma_client = None
        self.langchain_vectorstore = None
        self._initialized = False
        self._health_status = False
        
        logger.info("✅ Vector store service cleanup completed")