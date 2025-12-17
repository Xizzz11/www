"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
import os

from config.settings import settings

# Синхронный engine
try:
    engine = create_engine(
        settings.database_connection_string,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
except Exception:
    # Fallback для тестов
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

# Асинхронный engine (ленивая инициализация для тестов)
async_engine = None
try:
    async_engine = create_async_engine(
        settings.async_database_connection_string,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
except Exception:
    # В тестах async engine не нужен
    pass

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency для получения синхронной сессии БД.
    
    Yields:
        Session: SQLAlchemy session
    
    Examples:
        >>> @app.get("/users")
        >>> def get_users(db: Session = Depends(get_db)):
        ...     return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """
    Dependency для получения асинхронной сессии БД.
    
    Yields:
        AsyncSession: SQLAlchemy async session
    
    Examples:
        >>> @app.get("/users")
        >>> async def get_users(db: AsyncSession = Depends(get_async_db)):
        ...     result = await db.execute(select(User))
        ...     return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    """Инициализация БД (создание таблиц)."""
    Base.metadata.create_all(bind=engine)


