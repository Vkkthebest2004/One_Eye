import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

# Base Model
Base = declarative_base()

# Determine connection URL with SQLite fallback
db_url = settings.get_database_url()

engine = create_async_engine(
    db_url,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db():
    """Initialize database tables"""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database initialized successfully with URL: {engine.url.render_as_string(hide_password=True)}")
    except Exception as e:
        logger.warning(f"Failed to connect to primary DB ({e}). Falling back to local SQLite...")
        fallback_url = "sqlite+aiosqlite:///./oneeye.db"
        engine = create_async_engine(fallback_url, echo=False, future=True)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Initialized local fallback SQLite database successfully.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for API routes"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
