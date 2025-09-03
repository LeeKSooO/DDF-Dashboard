# 🚀 DDF RAG Service

Enterprise-grade RAG (Retrieval-Augmented Generation) system for converting natural language queries to SQL using IBM Watson AI and LangChain.

## 🏗️ Architecture

```
RAG_1/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI application entry point
│   ├── core/                     # Core application components
│   │   ├── config.py             # Configuration settings
│   │   ├── dependencies.py       # Dependency injection
│   │   └── exceptions.py         # Custom exceptions
│   ├── api/                      # API layer
│   │   ├── v1/                   # API version 1
│   │   │   ├── endpoints/        # API endpoints
│   │   │   │   ├── health.py     # Health check endpoints
│   │   │   │   └── query.py      # Query processing endpoints
│   │   │   └── router.py         # API router
│   │   └── middleware/           # Middleware components
│   │       ├── auth.py           # Authentication middleware
│   │       └── logging.py        # Logging middleware
│   ├── services/                 # Business logic services
│   │   ├── llm_service.py        # Watson AI LLM service
│   │   ├── embedding_service.py  # Text embedding service
│   │   ├── vector_store_service.py # Vector storage service
│   │   └── sql_generator_service.py # SQL generation service
│   ├── chains/                   # LangChain implementations
│   ├── agents/                   # LangChain agents
│   ├── models/                   # Data models
│   │   └── schemas/              # Pydantic schemas
│   │       ├── request.py        # Request models
│   │       └── response.py       # Response models
│   ├── prompts/                  # LLM prompt templates
│   └── utils/                    # Utility functions
├── tests/                        # Test suite
├── scripts/                      # Utility scripts
├── docker/                       # Docker configuration
├── k8s/                         # Kubernetes manifests
└── docs/                        # Documentation
```

## 🌟 Features

- **🎯 High Accuracy**: 99% confidence SQL generation with pattern matching
- **⚡ Fast Performance**: Optimized RAG pipeline with vector similarity search
- **🔄 RESTful API**: Complete REST API with OpenAPI documentation
- **🐳 Container Ready**: Docker and Kubernetes deployment support
- **📊 Monitoring**: Health checks, metrics, and logging
- **🔧 Extensible**: Modular architecture for easy extension
- **🛡️ Enterprise Security**: Authentication, rate limiting, and CORS support