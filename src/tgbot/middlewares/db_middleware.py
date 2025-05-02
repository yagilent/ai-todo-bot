# src/tgbot/middlewares/db_middleware.py

import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject # Базовый класс для event
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_pool = session_pool
        logger.info("DbSessionMiddleware initialized.")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any] # Словарь контекста, который мы будем обновлять
    ) -> Any:
        # logger.debug("DbSessionMiddleware started processing event.")
        # Получаем сессию из пула (фабрики)
        async with self.session_pool() as session:
            # Добавляем объект сессии в словарь контекста data
            # Ключ 'session' должен совпадать с именем аргумента в хендлерах!
            data['session'] = session
            # logger.debug(f"DB session {id(session)} added to context data.")

            # Вызываем следующий обработчик в цепочке (или сам хендлер)
            result = await handler(event, data)

        # logger.debug(f"DB session {id(session)} closed after handler.")
        return result