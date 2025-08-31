#!/usr/bin/env python3
"""
Test script to check if all required imports are available
"""
print("Starting import tests...")

try:
    import langchain_community
    print("✓ langchain_community imported successfully")
except ImportError as e:
    print(f"✗ Failed to import langchain_community: {e}")

try:
    from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader, PyPDFLoader
    print("✓ document loaders imported successfully")
except ImportError as e:
    print(f"✗ Failed to import document loaders: {e}")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    print("✓ text_splitter imported successfully")
except ImportError as e:
    print(f"✗ Failed to import text_splitter: {e}")

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    print("✓ HuggingFaceEmbeddings imported successfully")
except ImportError as e:
    print(f"✗ Failed to import HuggingFaceEmbeddings: {e}")

try:
    import chromadb
    print("✓ chromadb imported successfully")
except ImportError as e:
    print(f"✗ Failed to import chromadb: {e}")

print("Import tests completed!")