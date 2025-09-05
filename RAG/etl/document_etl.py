#!/usr/bin/env python3
"""
Document ETL Job - Manual Trigger Script
ETL (Extract, Transform, Load) process for document embedding into ChromaDB

Usage:
    python etl/document_etl.py [--force-reload] [--chromadb-url http://localhost:8003]

This script:
1. Extracts documents from data/documents directory
2. Transforms them into embeddings using HuggingFace embeddings
3. Loads them into ChromaDB vector store

Separated from RAG service for better operational efficiency.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
import shutil

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from langchain_chroma import Chroma

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.document_loader_service import DocumentLoaderService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentETL:
    """Standalone Document ETL processor"""
    
    def __init__(self, chromadb_url: Optional[str] = None, force_reload: bool = False):
        self.chromadb_url = chromadb_url or "http://localhost:8003"
        self.force_reload = force_reload
        self.embedding_service = None
        self.document_loader_service = None
        self.vectorstore = None
        
    async def initialize(self) -> bool:
        """Initialize ETL components"""
        logger.info("🚀 Initializing Document ETL...")
        
        try:
            # Initialize services
            self.embedding_service = EmbeddingService()
            self.document_loader_service = DocumentLoaderService()
            
            await self.embedding_service.initialize()
            await self.document_loader_service.initialize()
            
            logger.info("✅ Document ETL initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Document ETL initialization failed: {e}")
            return False
    
    async def setup_vectorstore(self) -> bool:
        """Setup ChromaDB vector store"""
        logger.info("📚 Setting up vector store...")
        
        try:
            chroma_path = Path(settings.CHROMA_PERSIST_DIR)
            
            # Force reload: clear existing data
            if self.force_reload and chroma_path.exists():
                logger.info("🔄 Force reload enabled - clearing existing vector store...")
                shutil.rmtree(chroma_path)
                chroma_path.mkdir(parents=True, exist_ok=True)
            
            # Ensure directory exists
            chroma_path.mkdir(parents=True, exist_ok=True)
            
            # Create or load vector store
            if chroma_path.exists() and any(chroma_path.iterdir()) and not self.force_reload:
                logger.info("📖 Loading existing vector store...")
                self.vectorstore = Chroma(
                    persist_directory=str(chroma_path),
                    embedding_function=self.embedding_service.langchain_embeddings
                )
            else:
                logger.info("📝 Creating new vector store...")
                # Will be created when first documents are added
                self.vectorstore = None
                
            logger.info("✅ Vector store setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vector store setup failed: {e}")
            return False
    
    async def load_and_embed_documents(self) -> bool:
        """Main ETL process: Load documents and create embeddings"""
        logger.info("📄 Starting document loading and embedding process...")
        
        try:
            documents_path = Path("./data/documents")
            
            if not documents_path.exists():
                logger.error(f"❌ Documents directory not found: {documents_path}")
                return False
            
            # Load documents
            logger.info(f"🔍 Loading documents from {documents_path}...")
            documents = await self.document_loader_service.load_documents_from_directory(
                str(documents_path)
            )
            
            if not documents:
                logger.warning("⚠️ No documents found to process")
                return True
            
            logger.info(f"📚 Found {len(documents)} documents to process")
            
            # Create or update vector store
            chroma_path = Path(settings.CHROMA_PERSIST_DIR)
            
            if self.vectorstore is None:
                # Create new vector store
                logger.info("🔨 Creating vector store from documents...")
                self.vectorstore = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Chroma.from_documents(
                        documents=documents,
                        embedding=self.embedding_service.langchain_embeddings,
                        persist_directory=str(chroma_path)
                    )
                )
                logger.info(f"✅ Vector store created with {len(documents)} documents")
                
            else:
                # Add to existing vector store
                if self.force_reload:
                    # Complete reload
                    logger.info("🔄 Force reloading all documents...")
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.vectorstore.add_documents(documents)
                    )
                    logger.info(f"✅ Vector store reloaded with {len(documents)} documents")
                else:
                    # Check for new/changed documents
                    new_docs = await self.document_loader_service.get_new_documents(
                        str(documents_path)
                    )
                    
                    if new_docs:
                        logger.info(f"📝 Adding {len(new_docs)} new/changed documents...")
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.vectorstore.add_documents(new_docs)
                        )
                        logger.info(f"✅ Added {len(new_docs)} new documents to vector store")
                    else:
                        logger.info("📚 No new or changed documents found")
            
            # Get final document count
            if self.vectorstore:
                try:
                    total_docs = self.vectorstore._collection.count()
                    logger.info(f"📊 Final vector store contains {total_docs} document chunks")
                except Exception as e:
                    logger.warning(f"Could not get document count: {e}")
            
            logger.info("✅ Document loading and embedding completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Document loading and embedding failed: {e}")
            return False
    
    async def validate_vectorstore(self) -> bool:
        """Validate that vector store is working correctly"""
        logger.info("🔍 Validating vector store...")
        
        try:
            if not self.vectorstore:
                logger.error("❌ Vector store not initialized")
                return False
            
            # Test search functionality
            test_query = "DRT 시스템"
            results = self.vectorstore.similarity_search(test_query, k=3)
            
            logger.info(f"🔍 Test search for '{test_query}' returned {len(results)} results")
            
            if results:
                logger.info(f"📄 Sample result: {results[0].page_content[:100]}...")
            
            logger.info("✅ Vector store validation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vector store validation failed: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up ETL resources...")
        
        # Services don't have cleanup methods
        self.embedding_service = None
        self.document_loader_service = None
        self.vectorstore = None
        
        logger.info("✅ ETL cleanup completed")
    
    async def run_etl(self) -> bool:
        """Run complete ETL process"""
        logger.info("🚀 Starting Document ETL Process...")
        
        try:
            # Initialize components
            if not await self.initialize():
                return False
            
            # Setup vector store
            if not await self.setup_vectorstore():
                return False
            
            # Load and embed documents
            if not await self.load_and_embed_documents():
                return False
            
            # Validate results
            if not await self.validate_vectorstore():
                return False
            
            logger.info("🎉 Document ETL Process completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Document ETL Process failed: {e}")
            return False
        
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Document ETL Job - Manual Trigger")
    parser.add_argument(
        "--force-reload", 
        action="store_true", 
        help="Force reload all documents (clears existing vector store)"
    )
    parser.add_argument(
        "--chromadb-url", 
        type=str, 
        default="http://localhost:8003",
        help="ChromaDB server URL (default: http://localhost:8003)"
    )
    parser.add_argument(
        "--documents-path",
        type=str,
        default="./data/documents",
        help="Path to documents directory (default: ./data/documents)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("🚀 Document ETL Job Starting")
    logger.info("=" * 60)
    logger.info(f"📊 Configuration:")
    logger.info(f"   • ChromaDB URL: {args.chromadb_url}")
    logger.info(f"   • Documents Path: {args.documents_path}")
    logger.info(f"   • Force Reload: {args.force_reload}")
    logger.info(f"   • Chroma Persist Dir: {settings.CHROMA_PERSIST_DIR}")
    logger.info("=" * 60)
    
    # Run ETL process
    etl = DocumentETL(
        chromadb_url=args.chromadb_url,
        force_reload=args.force_reload
    )
    
    success = await etl.run_etl()
    
    if success:
        logger.info("=" * 60)
        logger.info("🎉 Document ETL Job Completed Successfully!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("❌ Document ETL Job Failed!")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())