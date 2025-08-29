from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator
from loguru import logger

from app.core.config import settings

# Create async engine with increased timeout for PostGIS queries
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "server_settings": {"jit": "off"},  # PostGIS 성능 개선
        "timeout": 60,  # 연결 타임아웃 60초로 증가
        "command_timeout": 60  # 명령 타임아웃 60초로 증가
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session for DRT analysis
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error in app: {e}")
            raise
        finally:
            await session.close()

async def close_db():
    """Close database engine"""
    await engine.dispose()
    logger.info("App database engine closed")