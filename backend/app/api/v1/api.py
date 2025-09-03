"""
API v1 라우터 통합
모든 v1 엔드포인트를 하나로 통합하는 메인 라우터
"""

from fastapi import APIRouter
from app.api.v1.endpoints import traffic, heatmap, anomaly_pattern, drt_score

api_router = APIRouter()

# Traffic API 라우트 등록
api_router.include_router(
    traffic.router,
    prefix="/traffic",
    tags=["traffic"]
)

# Heatmap API 라우트 등록
api_router.include_router(
    heatmap.router,
    prefix="/heatmap",
    tags=["heatmap"]
)

# Anomaly Pattern API 라우트 등록
api_router.include_router(
    anomaly_pattern.router,
    prefix="/anomaly-pattern",
    tags=["anomaly-pattern"]
)

# DRT Score API 라우트 등록
api_router.include_router(
    drt_score.router,
    prefix="/drt-score",
    tags=["drt-score"]
)