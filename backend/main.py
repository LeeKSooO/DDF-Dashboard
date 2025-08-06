from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import sys
from pathlib import Path

# Import routers
from app.api.v1.endpoints import prediction, model, analysis, drt_analytics, bus_stops
from app.core.config import settings
from app.db.session import init_db

# Configure logging
logger.remove()
logger.add(sys.stdout, format="{time} - {level} - {message}", level="INFO")
logger.add("logs/app.log", rotation="1 day", retention="7 days", level="DEBUG")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle
    """
    # Startup
    logger.info("Starting DRT Prediction API Server...")
    
    # Initialize database
    await init_db()
    
    # Create necessary directories
    Path(settings.MODEL_BASE_PATH).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    logger.info("Server started successfully!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down server...")

# Create FastAPI app
app = FastAPI(
    title="DRT Demand Prediction API",
    description="API for predicting DRT demand using ASTGCN model",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    prediction.router,
    prefix="/api/v1/predictions",
    tags=["predictions"]
)
app.include_router(
    model.router,
    prefix="/api/v1/models",
    tags=["models"]
)
app.include_router(
    analysis.router,
    prefix="/api/v1/analysis",
    tags=["analysis"]
)
app.include_router(
    bus_stops.router,
    prefix="/api/v1/bus-stops",
    tags=["bus-stops"]
)
app.include_router(
    drt_analytics.router,
    prefix="/api/v1/drt-analytics",
    tags=["drt-analytics"]
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DRT Demand Prediction API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "backend"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)