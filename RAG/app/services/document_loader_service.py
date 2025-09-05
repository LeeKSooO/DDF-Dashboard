"""
Document loader and chunking service for RAG system
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader, 
    PyMuPDFLoader, 
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from app.core.config import settings
from app.core.exceptions import DocumentLoaderException


logger = logging.getLogger(__name__)


class DocumentLoaderService:
    """Service for loading and chunking documents"""
    
    def __init__(self):
        self._initialized = False
        self._health_status = False
        self.processed_files: Dict[str, Dict[str, Any]] = {}
        self.text_splitter = None
        
    async def initialize(self) -> None:
        """Initialize document loader service"""
        
        if self._initialized:
            return
        
        logger.info("🚀 Initializing document loader service...")
        
        try:
            # Initialize text splitter with optimized settings
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,      # 각 청크의 최대 문자 수
                chunk_overlap=300,    # 인접 청크 간 겹치는 문자 수
                separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""],  # 구분자 우선순위
                length_function=len,
            )
            
            self._initialized = True
            self._health_status = True
            
            logger.info("✅ Document loader service initialized successfully")
            
        except Exception as e:
            self._health_status = False
            logger.error(f"❌ Failed to initialize document loader service: {e}")
            raise DocumentLoaderException(f"Document loader initialization failed: {str(e)}")
    
    async def load_directory(
        self, 
        directory_path: str,
        glob_pattern: str = "**/*.pdf",
        recursive: bool = True
    ) -> List[Document]:
        """Load all documents from a directory"""
        
        if not self._initialized:
            raise DocumentLoaderException("Document loader not initialized")
        
        try:
            if not os.path.exists(directory_path):
                raise DocumentLoaderException(f"Directory not found: {directory_path}")
            
            all_documents = []
            
            # Find all matching files
            path = Path(directory_path)
            if recursive:
                files = list(path.rglob(glob_pattern.replace("**/", "")))
            else:
                files = list(path.glob(glob_pattern.replace("**/", "")))
            
            logger.info(f"Found {len(files)} files matching pattern: {glob_pattern}")
            
            # Load each file
            for file_path in files:
                docs = await self.load_single_document(str(file_path))
                if docs:
                    all_documents.extend(docs)
            
            logger.info(f"Loaded {len(all_documents)} documents from {directory_path}")
            return all_documents
            
        except Exception as e:
            logger.error(f"Failed to load directory: {e}")
            raise DocumentLoaderException(f"Directory loading failed: {str(e)}")
    
    async def load_single_document(self, file_path: str) -> List[Document]:
        """Load a single document file"""
        
        if not self._initialized:
            raise DocumentLoaderException("Document loader not initialized")
        
        try:
            if not os.path.exists(file_path):
                raise DocumentLoaderException(f"File not found: {file_path}")
            
            file_extension = Path(file_path).suffix.lower()
            documents = []
            
            if file_extension == '.pdf':
                documents = await self._load_pdf(file_path)
            elif file_extension in ['.txt', '.text']:
                documents = await self._load_text(file_path)
            elif file_extension in ['.md', '.markdown']:
                documents = await self._load_markdown(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_extension}")
                return []
            
            # Add metadata to documents
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": file_extension,
                    "loaded_at": datetime.utcnow().isoformat()
                })
            
            # Update processed files tracking
            self._update_processed_file_info(file_path, len(documents))
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            raise DocumentLoaderException(f"Document loading failed: {str(e)}")
    
    async def _load_pdf(self, file_path: str) -> List[Document]:
        """Load PDF document"""
        
        filename = os.path.basename(file_path)
        
        # Try PyMuPDFLoader first (faster and more accurate)
        try:
            loader = PyMuPDFLoader(file_path)
            docs = loader.load()
            logger.info(f"✅ Loaded PDF with PyMuPDF: {filename} ({len(docs)} pages)")
            return docs
        except Exception as e:
            logger.warning(f"PyMuPDF failed for {filename}: {e}")
        
        # Fallback to PyPDFLoader
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            logger.info(f"✅ Loaded PDF with PyPDF: {filename} ({len(docs)} pages)")
            return docs
        except Exception as e:
            logger.error(f"All PDF loaders failed for {filename}: {e}")
            raise
    
    async def _load_text(self, file_path: str) -> List[Document]:
        """Load text document"""
        
        try:
            loader = TextLoader(file_path, encoding='utf-8')
            docs = loader.load()
            logger.info(f"✅ Loaded text file: {os.path.basename(file_path)}")
            return docs
        except Exception as e:
            logger.error(f"Failed to load text file: {e}")
            raise
    
    async def _load_markdown(self, file_path: str) -> List[Document]:
        """Load markdown document"""
        
        try:
            loader = UnstructuredMarkdownLoader(file_path)
            docs = loader.load()
            logger.info(f"✅ Loaded markdown file: {os.path.basename(file_path)}")
            return docs
        except Exception as e:
            logger.error(f"Failed to load markdown file: {e}")
            raise
    
    async def chunk_documents(
        self, 
        documents: List[Document],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[Document]:
        """Split documents into chunks"""
        
        if not self._initialized:
            raise DocumentLoaderException("Document loader not initialized")
        
        try:
            # Use custom settings if provided
            if chunk_size or chunk_overlap:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size or 1500,
                    chunk_overlap=chunk_overlap or 300,
                    separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""],
                    length_function=len,
                )
            else:
                text_splitter = self.text_splitter
            
            # Split documents
            chunks = text_splitter.split_documents(documents)
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                    "chunked_at": datetime.utcnow().isoformat()
                })
            
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk documents: {e}")
            raise DocumentLoaderException(f"Document chunking failed: {str(e)}")
    
    async def load_and_chunk(
        self,
        file_path: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[Document]:
        """Load and chunk a single document in one operation"""
        
        try:
            # Load document
            documents = await self.load_single_document(file_path)
            
            if not documents:
                return []
            
            # Chunk documents
            chunks = await self.chunk_documents(
                documents, 
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to load and chunk {file_path}: {e}")
            raise DocumentLoaderException(f"Load and chunk failed: {str(e)}")
    
    async def load_directory_and_chunk(
        self,
        directory_path: str,
        glob_pattern: str = "**/*.pdf",
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[Document]:
        """Load all documents from directory and chunk them"""
        
        try:
            # Load all documents
            documents = await self.load_directory(directory_path, glob_pattern)
            
            if not documents:
                return []
            
            # Chunk all documents
            chunks = await self.chunk_documents(
                documents,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to load and chunk directory: {e}")
            raise DocumentLoaderException(f"Directory load and chunk failed: {str(e)}")
    
    def _update_processed_file_info(self, file_path: str, doc_count: int) -> None:
        """Update tracking information for processed files"""
        
        file_hash = self._get_file_hash(file_path)
        self.processed_files[file_path] = {
            "hash": file_hash,
            "document_count": doc_count,
            "processed_at": datetime.utcnow().isoformat(),
            "file_size": os.path.getsize(file_path)
        }
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate file hash for change detection"""
        
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)  # Read in 64kb chunks
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    
    def _is_file_changed(self, file_path: str) -> bool:
        """Check if file has changed since last processing"""
        
        if file_path not in self.processed_files:
            return True
        
        current_hash = self._get_file_hash(file_path)
        stored_hash = self.processed_files[file_path].get("hash")
        
        return current_hash != stored_hash
    
    async def get_new_or_changed_files(self, directory_path: str) -> List[str]:
        """Get list of new or changed files in directory"""
        
        new_or_changed = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith(('.pdf', '.txt', '.md')):
                    filepath = os.path.join(root, file)
                    if self._is_file_changed(filepath):
                        new_or_changed.append(filepath)
                        logger.info(f"📄 New/changed file: {os.path.basename(filepath)}")
        
        return new_or_changed
    
    async def health_check(self) -> bool:
        """Check service health"""
        
        if not self._initialized:
            return False
        
        try:
            # Test text splitter
            test_doc = Document(page_content="Test document for health check.")
            chunks = self.text_splitter.split_documents([test_doc])
            
            self._health_status = len(chunks) > 0
            return self._health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._health_status = False
            return False
    
    async def load_documents_from_directory(self, directory_path: str) -> List[Document]:
        """Load and chunk documents from directory (alias for compatibility)"""
        return await self.load_directory_and_chunk(directory_path)

    async def get_new_documents(self, directory_path: str) -> List[Document]:
        """Get new or changed documents from directory"""
        try:
            new_files = await self.get_new_or_changed_files(directory_path)
            if not new_files:
                return []
            
            all_docs = []
            for file_path in new_files:
                docs = await self.load_and_chunk(file_path)
                all_docs.extend(docs)
            
            return all_docs
        except Exception as e:
            logger.error(f"Failed to get new documents: {e}")
            return []

    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        
        return {
            "initialized": self._initialized,
            "health_status": self._health_status,
            "processed_files_count": len(self.processed_files),
            "default_chunk_size": 1500,
            "default_chunk_overlap": 300,
            "supported_formats": [".pdf", ".txt", ".md"],
            "last_health_check": datetime.utcnow().isoformat()
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        
        logger.info("🧹 Cleaning up document loader service...")
        
        self.text_splitter = None
        self.processed_files.clear()
        self._initialized = False
        self._health_status = False
        
        logger.info("✅ Document loader service cleanup completed")