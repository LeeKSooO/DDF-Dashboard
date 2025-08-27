from pydantic_settings import BaseSettings
from typing import List
import os

class DRTDashboardSettings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "DRT Dashboard API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://ddf_user:ddf_password@localhost:5432/ddf_db"
    )
    
    # Cache Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")  # Redis cache for dashboard
    
    # Cache TTL Settings (seconds)
    #CACHE_TTL_KPI: int = 300        # 5 minutes - real-time metrics
    #CACHE_TTL_MAP: int = 600        # 10 minutes - map data  
    #CACHE_TTL_ANALYSIS: int = 1800  # 30 minutes - analysis results
    #CACHE_TTL_TRENDS: int = 3600    # 1 hour - trend data
    #CACHE_TTL_PREDICTION: int = 1800 # 30 minutes - prediction results
    #CACHE_TTL_SIMULATION: int = 0   # No cache for simulation results
    
    # Performance Settings
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500
    MAX_MAP_STATIONS: int = 1000    # Maximum stations to show on map
    
    # CORS
    ALLOWED_HOSTS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000", 
        "http://frontend:3000",
    ]
    
    # Database Performance
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # DRT Analysis Parameters
    DRT_SCORE_WEIGHTS: dict = {
        "demand_variability": 0.3,
        "efficiency_ratio": 0.3, 
        "connectivity_gap": 0.2,
        "service_distance_deviation": 0.2
    }
    
    # Efficiency Thresholds
    EFFICIENCY_THRESHOLDS: dict = {
        "very_low": 5,      # < 5 passengers per dispatch
        "low": 10,          # 5-10 passengers per dispatch
        "normal": 20,       # 10-20 passengers per dispatch
        "high": float('inf') # > 20 passengers per dispatch
    }
    
    # Variability Thresholds (Coefficient of Variation)
    VARIABILITY_THRESHOLDS: dict = {
        "low": 0.4,
        "medium": 0.7,
        "high": 1.0,
        "very_high": float('inf')
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = DRTDashboardSettings()