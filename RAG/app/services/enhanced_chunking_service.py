"""
Enhanced chunking service with PDF structure awareness for RAG system
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import TextSplitter

from app.core.config import settings
from app.core.exceptions import RAGServiceException


logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """청크 유형 정의"""
    TITLE = "title"           # 제목
    SECTION = "section"       # 섹션
    PARAGRAPH = "paragraph"   # 문단
    LIST = "list"            # 목록
    TABLE = "table"          # 표
    FIGURE = "figure"        # 그림 설명
    REFERENCE = "reference"   # 참고문헌
    MIXED = "mixed"          # 혼합 내용


@dataclass
class ChunkMetadata:
    """청크 메타데이터 강화"""
    chunk_type: ChunkType
    importance_score: float  # 중요도 점수 (0.0 ~ 1.0)
    structure_level: int     # 구조 깊이 (0: 제목, 1: 소제목, 2: 내용...)
    has_korean: bool         # 한국어 포함 여부
    word_count: int          # 단어 수
    char_count: int          # 문자 수
    section_title: Optional[str] = None  # 속한 섹션 제목


class EnhancedChunkingService:
    """PDF 구조를 인식하는 스마트 청킹 서비스"""
    
    def __init__(self):
        self.base_chunk_size = getattr(settings, 'ENHANCED_CHUNK_SIZE', 1200)
        self.base_overlap = getattr(settings, 'ENHANCED_CHUNK_OVERLAP', 200)
        self.max_chunk_size = getattr(settings, 'MAX_CHUNK_SIZE', 2000)
        self.min_chunk_size = getattr(settings, 'MIN_CHUNK_SIZE', 300)
        
        # PDF 구조 패턴 정의
        self._title_patterns = [
            r'^[0-9]+\.\s+.+$',                    # 1. 제목
            r'^[가-힣]+\s*[0-9]+\.\s+.+$',         # 제 1장. 제목
            r'^[IVX]+\.\s+.+$',                    # I. 제목 (로마숫자)
            r'^[가-힣]\.\s+.+$',                   # 가. 제목
            r'^제\s*[0-9]+\s*[장절]\s+.+$',        # 제 1장, 제 1절
        ]
        
        self._subsection_patterns = [
            r'^[0-9]+\.[0-9]+\s+.+$',             # 1.1 소제목
            r'^[0-9]+\.[0-9]+\.[0-9]+\s+.+$',     # 1.1.1 소제목
            r'^\([0-9]+\)\s+.+$',                  # (1) 소제목
            r'^[가-힣]\)\s+.+$',                   # 가) 소제목
        ]
        
        self._list_patterns = [
            r'^[-•·▪▫]\s+.+$',                     # 불릿 포인트
            r'^[0-9]+\)\s+.+$',                    # 1) 목록
            r'^[①-⑳]\s+.+$',                      # 숫자 원형
        ]
        
        logger.info("✅ Enhanced chunking service initialized")
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """문서들을 스마트하게 청크 분할"""
        try:
            all_chunks = []
            
            for doc in documents:
                chunks = self._smart_chunk_document(doc)
                all_chunks.extend(chunks)
            
            logger.info(f"📊 Enhanced chunking: {len(documents)} docs → {len(all_chunks)} chunks")
            return all_chunks
            
        except Exception as e:
            logger.error(f"❌ Enhanced chunking failed: {e}")
            # 폴백: 기본 청킹 사용
            return self._fallback_chunking(documents)
    
    def _smart_chunk_document(self, document: Document) -> List[Document]:
        """단일 문서를 스마트하게 청크 분할"""
        try:
            content = document.page_content
            
            # 안전 장치: 빈 문서 확인
            if not content or not content.strip():
                return []
            
            # 1. 문서 구조 분석
            structure = self._analyze_document_structure(content)
            
            # 안전 장치: 구조 분석 실패시
            if not structure:
                return self._fallback_chunking([document])
            
            # 2. 구조 기반 청킹
            chunks = self._structure_based_chunking(content, structure, document.metadata)
            
            # 안전 장치: 청킹 실패시
            if not chunks:
                return self._fallback_chunking([document])
            
            # 3. 청크 최적화 (크기 조정)
            optimized_chunks = self._optimize_chunks(chunks)
            
            return optimized_chunks
            
        except Exception as e:
            logger.error(f"❌ Smart chunking failed for document: {e}")
            # 폴백: 기본 청킹 사용
            return self._fallback_chunking([document])
    
    def _analyze_document_structure(self, content: str) -> List[Dict[str, Any]]:
        """문서 구조 분석"""
        lines = content.split('\n')
        structure = []
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 구조 요소 분류
            element = {
                'line_num': i,
                'content': line,
                'type': self._classify_line(line),
                'importance': self._calculate_importance(line),
                'level': self._get_structure_level(line),
            }
            
            # 섹션 추적
            if element['type'] in [ChunkType.TITLE, ChunkType.SECTION]:
                current_section = line
            element['section'] = current_section
            
            structure.append(element)
        
        return structure
    
    def _classify_line(self, line: str) -> ChunkType:
        """라인 유형 분류"""
        # 제목 패턴 확인
        for pattern in self._title_patterns:
            if re.match(pattern, line):
                return ChunkType.TITLE
        
        # 소제목 패턴 확인
        for pattern in self._subsection_patterns:
            if re.match(pattern, line):
                return ChunkType.SECTION
        
        # 목록 패턴 확인
        for pattern in self._list_patterns:
            if re.match(pattern, line):
                return ChunkType.LIST
        
        # 표/그림 확인
        if re.match(r'^\[표\s*[0-9-]+\]|^\[그림\s*[0-9-]+\]|^<표\s*[0-9-]+>|^<그림\s*[0-9-]+>', line):
            return ChunkType.FIGURE
        
        # 참고문헌 확인
        if re.match(r'^\[[0-9]+\]|^\([0-9]{4}\)', line):
            return ChunkType.REFERENCE
        
        return ChunkType.PARAGRAPH
    
    def _calculate_importance(self, line: str) -> float:
        """라인 중요도 계산 (0.0 ~ 1.0)"""
        importance = 0.3  # 기본값
        
        # 제목이면 높은 중요도
        if any(re.match(p, line) for p in self._title_patterns):
            importance = 1.0
        elif any(re.match(p, line) for p in self._subsection_patterns):
            importance = 0.8
        
        # DRT 관련 키워드 보너스
        drt_keywords = ['DRT', '수요응답', '교통', '대중교통', '모빌리티', '교통체계']
        if any(keyword in line for keyword in drt_keywords):
            importance += 0.2
        
        # 한국어 포함시 보너스 (DRT 문서는 대부분 한국어)
        if re.search(r'[가-힣]', line):
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _get_structure_level(self, line: str) -> int:
        """구조 레벨 계산 (0: 최상위, 1: 섹션, 2: 서브섹션...)"""
        # 제목 패턴들을 레벨별로 확인
        if re.match(r'^제\s*[0-9]+\s*장', line):
            return 0
        elif re.match(r'^[0-9]+\.\s+', line):
            return 1
        elif re.match(r'^[0-9]+\.[0-9]+\s+', line):
            return 2
        elif re.match(r'^[0-9]+\.[0-9]+\.[0-9]+\s+', line):
            return 3
        elif re.match(r'^\([0-9]+\)', line):
            return 2
        
        return 4  # 일반 내용
    
    def _structure_based_chunking(
        self, 
        content: str, 
        structure: List[Dict[str, Any]], 
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """구조 기반 청킹"""
        chunks = []
        current_chunk = []
        current_size = 0
        current_section = None
        
        for element in structure:
            line = element['content']
            line_size = len(line)
            
            # 새로운 섹션 시작시 또는 크기 초과시 청크 완료
            should_break = (
                (element['type'] in [ChunkType.TITLE, ChunkType.SECTION] and current_chunk) or
                (current_size + line_size > self.base_chunk_size and current_chunk)
            )
            
            if should_break:
                # 현재 청크 완료
                chunk_content = '\n'.join(current_chunk)
                if chunk_content.strip():
                    chunk_doc = self._create_chunk_document(
                        chunk_content, base_metadata, current_section
                    )
                    chunks.append(chunk_doc)
                
                # 새 청크 시작
                current_chunk = [line] if line else []
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size + 1  # +1 for newline
            
            # 섹션 추적
            if element['type'] in [ChunkType.TITLE, ChunkType.SECTION]:
                current_section = line
        
        # 마지막 청크 처리
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if chunk_content.strip():
                chunk_doc = self._create_chunk_document(
                    chunk_content, base_metadata, current_section
                )
                chunks.append(chunk_doc)
        
        return chunks
    
    def _create_chunk_document(
        self, 
        content: str, 
        base_metadata: Dict[str, Any], 
        section_title: Optional[str]
    ) -> Document:
        """청크 문서 생성"""
        # 청크 메타데이터 생성
        chunk_metadata = ChunkMetadata(
            chunk_type=self._determine_chunk_type(content),
            importance_score=self._calculate_chunk_importance(content),
            structure_level=self._get_chunk_level(content),
            has_korean=bool(re.search(r'[가-힣]', content)),
            word_count=len(content.split()),
            char_count=len(content),
            section_title=section_title
        )
        
        # 메타데이터 결합 (None 값 필터링)
        metadata = base_metadata.copy()
        enhanced_metadata = {
            'chunk_type': chunk_metadata.chunk_type.value,
            'importance_score': chunk_metadata.importance_score,
            'structure_level': chunk_metadata.structure_level,
            'has_korean': chunk_metadata.has_korean,
            'word_count': chunk_metadata.word_count,
            'char_count': chunk_metadata.char_count,
            'enhanced_chunking': True
        }
        
        # section_title이 None이 아닐 때만 추가
        if chunk_metadata.section_title:
            enhanced_metadata['section_title'] = chunk_metadata.section_title
            
        metadata.update(enhanced_metadata)
        
        return Document(page_content=content, metadata=metadata)
    
    def _determine_chunk_type(self, content: str) -> ChunkType:
        """청크 타입 결정"""
        lines = content.strip().split('\n')
        
        # 첫 줄로 타입 판단
        first_line = lines[0].strip() if lines else ""
        
        if any(re.match(p, first_line) for p in self._title_patterns):
            return ChunkType.TITLE
        elif any(re.match(p, first_line) for p in self._subsection_patterns):
            return ChunkType.SECTION
        elif len([l for l in lines if any(re.match(p, l.strip()) for p in self._list_patterns)]) > 1:
            return ChunkType.LIST
        else:
            return ChunkType.PARAGRAPH
    
    def _calculate_chunk_importance(self, content: str) -> float:
        """청크 전체 중요도 계산"""
        lines = content.split('\n')
        total_importance = 0.0
        
        for line in lines:
            total_importance += self._calculate_importance(line.strip())
        
        # 평균 중요도 반환
        return total_importance / len(lines) if lines else 0.0
    
    def _get_chunk_level(self, content: str) -> int:
        """청크의 구조 레벨 결정"""
        lines = content.split('\n')
        min_level = 10  # 큰 값으로 초기화
        
        for line in lines:
            level = self._get_structure_level(line.strip())
            min_level = min(min_level, level)
        
        return min_level if min_level < 10 else 4
    
    def _optimize_chunks(self, chunks: List[Document]) -> List[Document]:
        """청크 크기 최적화"""
        optimized = []
        
        for chunk in chunks:
            content = chunk.page_content
            
            # 너무 작은 청크는 다음 청크와 병합 고려
            if len(content) < self.min_chunk_size:
                # 이전 청크와 병합 시도
                if optimized and len(optimized[-1].page_content) + len(content) <= self.max_chunk_size:
                    prev_chunk = optimized[-1]
                    merged_content = prev_chunk.page_content + '\n\n' + content
                    
                    # 메타데이터 업데이트
                    merged_metadata = prev_chunk.metadata.copy()
                    merged_metadata['char_count'] = len(merged_content)
                    merged_metadata['word_count'] = len(merged_content.split())
                    
                    optimized[-1] = Document(
                        page_content=merged_content,
                        metadata=merged_metadata
                    )
                    continue
            
            # 너무 큰 청크는 분할
            if len(content) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk)
                optimized.extend(sub_chunks)
            else:
                optimized.append(chunk)
        
        return optimized
    
    def _split_large_chunk(self, chunk: Document) -> List[Document]:
        """큰 청크를 분할"""
        content = chunk.page_content
        metadata = chunk.metadata.copy()
        
        # RecursiveCharacterTextSplitter로 분할
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.base_chunk_size,
            chunk_overlap=self.base_overlap,
            separators=["\n\n", "\n", ". ", "。", " "]
        )
        
        text_chunks = splitter.split_text(content)
        
        sub_chunks = []
        for i, text_chunk in enumerate(text_chunks):
            sub_metadata = metadata.copy()
            sub_metadata['sub_chunk_index'] = i
            sub_metadata['char_count'] = len(text_chunk)
            sub_metadata['word_count'] = len(text_chunk.split())
            
            sub_chunks.append(Document(
                page_content=text_chunk,
                metadata=sub_metadata
            ))
        
        return sub_chunks
    
    def _fallback_chunking(self, documents: List[Document]) -> List[Document]:
        """폴백: 기본 청킹 방식"""
        logger.warning("🔄 Using fallback chunking strategy")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.base_chunk_size,
            chunk_overlap=self.base_overlap,
            separators=["\n\n", "\n", ". ", "。", "!", "?", " ", ""]
        )
        
        all_chunks = []
        for doc in documents:
            chunks = splitter.split_documents([doc])
            
            # 기본 메타데이터 추가
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    'chunk_type': 'fallback',
                    'chunk_index': i,
                    'enhanced_chunking': False
                })
            
            all_chunks.extend(chunks)
        
        return all_chunks


class EnhancedChunkingException(RAGServiceException):
    """Enhanced chunking service specific exceptions"""
    pass