# src/database/db_session.py

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.config import settings

logger = logging.getLogger(__name__)

class DatabaseSessionManager:
    def __init__(self, url: str):
        self._engine = create_async_engine(url, echo=False)
       
        self.session_factory = async_sessionmaker( 
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=AsyncSession
        )
        logger.info("Async engine and session factory created.")

    async def close(self):
        if self._engine is None:
            logger.warning("Engine is already closed or was not initialized.")
            return
        logger.info("Disposing SQLAlchemy engine...")
        await self._engine.dispose()
        self._engine = None
        self.session_factory = None # Обнуляем фабрику тоже
        logger.info("SQLAlchemy engine disposed.")

    # Метод get_session больше не нужен для DI через middleware,
    # но может быть полезен в других частях кода. Оставим его.
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if self.session_factory is None:
            raise IOError("DatabaseSessionManager is not initialized")
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                logger.exception("Session rollback due to exception")
                raise

# Создаем экземпляр менеджера
sessionmanager = DatabaseSessionManager(settings.database_url_asyncpg)

# Функции для старта/остановки остаются теми же
async def lifespan_startup():
    logger.info("Database session manager is ready.")
    pass

async def lifespan_shutdown():
    await sessionmanager.close()