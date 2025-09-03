# RAG Data Directory

This directory contains data files for the RAG (Retrieval-Augmented Generation) system.

## Directory Structure

```
data/
├── documents/      # PDF and document files for knowledge base
│   └── *.pdf      # Place your PDF files here
├── chroma/        # Vector database storage (auto-generated)
│   └── ...        # Chroma DB files (do not modify)
└── README.md      # This file
```

## Usage

### Adding Documents

1. Place your PDF files in the `documents/` directory
2. Supported formats:
   - PDF files (`.pdf`)
   - Text files (`.txt`)
   - Markdown files (`.md`)

3. When the RAG application starts, it will automatically:
   - Load all documents from the `documents/` directory
   - Extract text and create chunks
   - Generate embeddings
   - Store in the Chroma vector database

### Notes

- The `chroma/` directory is automatically managed by the application
- Do not manually modify files in the `chroma/` directory
- New documents are automatically detected and processed on application restart
- Duplicate documents are skipped based on file hash comparison

## Configuration

Document loading settings can be modified in `app/core/config.py`:

```python
DOCUMENT_PATHS = [
    {
        "type": "directory",
        "path": "./data/documents",
        "pattern": "**/*.pdf",
        "chunk_size": 1500,
        "chunk_overlap": 300
    }
]
```