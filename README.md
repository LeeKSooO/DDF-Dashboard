# DDF-Dashbaord

서울시 버스 교통 데이터 기반 DRT(Demand Responsive Transport)도입 우선순위 및 버스교통수요 분석 시스템

## 프로젝트 개요

서울시 버스 OD(Origin-Destination) 데이터를 분석하여 DRT 도입 우선순위를 산정하고, 실시간 대시보드를 통해 교통 패턴을 시각화하는 시스템입니다. TimescaleDB를 활용한 시계열 데이터 처리와 Redis 캐싱을 통해 대용량 데이터의 실시간 분석을 지원합니다.

## 시스템 구조

```
DDF-ASTGCN/
├── frontend/         # Next.js 14 대시보드
├── backend/          # FastAPI 서버
├── ai/               # MSTGCN 모델(프로젝트 범위에서 제외, 추후 개선 예정)
├── RAG/              # RAG 기반 챗봇 서비스
├── data/             # ETL 파이프라인
├── infrastructure/   # Docker, Kubernetes 설정
├── k8s/              # Kubernetes 배포 매니페스트
```

## 주요 기능

- **OD 분석**: 61만 건의 월별 OD 데이터 분석
- **DRT 우선순위**: 4단계 우선순위 점수 산정 알고리즘
- **실시간 히트맵**: 시간대별 수요 패턴 시각화
- **시계열 분석**: 일별/월별 교통량 추이 분석
- **대화형 분석**: RAG 기반 자연어 질의 응답
