from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "DRT Demand Prediction API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://ddf_user:ddf_password@localhost:5432/ddf_db"
    )
    
    # TorchServe
    TORCHSERVE_URL: str = os.getenv("TORCHSERVE_URL", "http://localhost:8080")
    TORCHSERVE_MODEL_NAME: str = "mstgcn"
    TORCHSERVE_TIMEOUT: int = 60  # seconds
    
    # Model Configuration
    MODEL_BASE_PATH: str = os.getenv("MODEL_BASE_PATH", "/app/ddf_model")
    ACTIVE_MODEL_VERSION: str = "ddf_v1"
    
    # Model Architecture Parameters (hardcoded for now)
    NUM_OF_VERTICES: int = 957  # Actual number of bus stops (confirmed by adjacency matrix)
    IN_CHANNELS: int = 4  # 4 input features: normalized_log_boarding_count, service_availability, is_rest_day, normalized_interval
    LEN_INPUT_HOUR: int = 6   # Recent 6 hours
    LEN_INPUT_DAY: int = 24   # Recent 24 hours
    LEN_INPUT_WEEK: int = 24  # Same 24 hours from 1 week ago
    NUM_FOR_PREDICT: int = 24  # 24 hours prediction
    K_ORDER: int = 3
    
    # Data Normalization (hardcoded temporarily)
    DATA_MEAN: float = 0.1110
    DATA_STD: float = 1.1544
    
    # Redis Cache
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL: int = 300  # 5 minutes
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://frontend:3000",
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Performance
    MAX_BATCH_SIZE: int = 100  # Maximum stops per prediction request
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()