# DDF-MSTGCN Project
DRT(Demand Responsive Transport) 수요 예측 및 운영 분석 시스템

## 🏗️ 프로젝트 구조

```
DDF-MSTGCN/
├── 🖥️ frontend/          # React 대시보드
├── ⚙️ backend/           # FastAPI 서버
├── 🤖 ai/               # AI/ML 모델 및 추론
├── 📊 data/             # 데이터 처리 및 ETL
├── 🚀 infrastructure/   # Docker, DB, 배포 설정
└── 📚 docs/             # 문서
```

## 🚀 빠른 시작

### 전체 시스템 실행
```bash
# Docker Compose로 전체 시스템 실행
docker-compose up -d
```

### 개발 환경 실행
```bash
# Frontend 개발 서버
cd frontend && npm start

# Backend 개발 서버  
cd backend && uvicorn main:app --reload

# Database
docker-compose up database -d
```

## 📁 각 디렉토리 설명

### Frontend
- **기술스택**: React, TypeScript, Ant Design, Leaflet
- **포트**: 3000
- **역할**: DRT 운영 대시보드, 지도 시각화, 분석 차트

### Backend
- **기술스택**: FastAPI, SQLAlchemy, PostgreSQL
- **포트**: 8000
- **역할**: API 서버, 데이터 분석, 예측 서비스

### AI
- **기술스택**: PyTorch, TorchServe, MSTGCN
- **역할**: 모델 훈련, 추론 서비스, 예측 알고리즘

### Data
- **기술스택**: Pandas, NumPy, PostgreSQL
- **역할**: ETL 파이프라인, 데이터 전처리, 피처 생성

### Infrastructure
- **기술스택**: Docker, PostgreSQL, PostGIS
- **역할**: 컨테이너 오케스트레이션, DB 관리, 배포 설정

## 🔧 개발 가이드

### 브랜치 전략
```
main                   # 배포용 안정 버전
├── develop            # 통합 개발 브랜치  
├── feature/frontend-* # Frontend 기능
├── feature/backend-*  # Backend 기능
├── feature/ai-*       # AI/ML 기능
└── feature/data-*     # Data 처리 기능
```

### 코드 컨벤션
- **Python**: Black, isort, flake8
- **TypeScript**: ESLint, Prettier
- **Git**: Conventional Commits

## 📊 시스템 아키텍처

```
Frontend (React) → Backend (FastAPI) → Database (PostgreSQL)
                ↘     ↓
                  AI Models (PyTorch)
                     ↓
                Data Pipeline (ETL)
```

## 🤝 협업 가이드

1. **이슈 생성**: 작업 시작 전 GitHub Issues 생성
2. **브랜치 생성**: `feature/[팀]-[기능명]` 형식
3. **PR 생성**: 개발 완료 후 Pull Request
4. **코드 리뷰**: 최소 1명 이상 리뷰 후 머지
5. **배포**: `main` 브랜치 머지 시 자동 배포

## 📚 추가 문서

- [설치 가이드](docs/DOCKER_SETUP.md)
- [개발 가이드](docs/CLAUDE.md)
- [API 문서](http://localhost:8000/docs)

## 🏷️ 버전

- **현재 버전**: v2.0.0
- **Node.js**: v18+
- **Python**: 3.9+
- **PostgreSQL**: 15+