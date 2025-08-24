# src/utils/llm_progress_tracker.py

import asyncio
import logging
from typing import Optional
from aiogram import Bot

logger = logging.getLogger(__name__)


class LLMProgressTracker:
    """
    Класс для показа прогресса обработки LLM запросов пользователю.
    
    Показывает typing indicator и статусные сообщения во время долгих операций.
    """
    
    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.status_message = None
        self.is_active = False
    
    async def start(self, initial_text: str = "🤖 Анализирую запрос..."):
        """
        Начинает показ прогресса.
        
        Args:
            initial_text: Первоначальный текст статуса
        """
        try:
            self.is_active = True
            
            # Сначала показываем typing indicator
            await self.bot.send_chat_action(self.chat_id, "typing")
            
            # Небольшая пауза, чтобы пользователь увидел typing
            await asyncio.sleep(1.5)
            
            # Отправляем статусное сообщение
            self.status_message = await self.bot.send_message(
                self.chat_id, 
                initial_text
            )
            logger.debug(f"Started LLM progress tracking for chat {self.chat_id}")
            
        except Exception as e:
            logger.error(f"Error starting LLM progress tracker: {e}")
            self.is_active = False
    
    async def update(self, text: str, step: Optional[int] = None, total: Optional[int] = None):
        """
        Обновляет статус прогресса.
        
        Args:
            text: Новый текст статуса
            step: Текущий этап (опционально)
            total: Общее количество этапов (опционально)
        """
        if not self.is_active or not self.status_message:
            return
            
        try:
            # Формируем текст с индикатором этапа
            status_text = text
            if step and total:
                status_text += f" ({step}/{total})"
            
            # Обновляем сообщение
            await self.status_message.edit_text(status_text)
            
            # Обновляем typing indicator
            await self.bot.send_chat_action(self.chat_id, "typing")
            
            logger.debug(f"Updated LLM progress: {status_text}")
            
        except Exception as e:
            logger.error(f"Error updating LLM progress tracker: {e}")
    
    async def finish(self, keep_message: bool = False):
        """
        Завершает показ прогресса.
        
        Args:
            keep_message: Если True, не удаляет статусное сообщение
        """
        if not self.is_active:
            return
            
        try:
            self.is_active = False
            
            # Удаляем статусное сообщение если не просят оставить
            if self.status_message and not keep_message:
                await self.status_message.delete()
                logger.debug(f"Finished and deleted LLM progress message for chat {self.chat_id}")
            elif keep_message:
                logger.debug(f"Finished LLM progress tracking, keeping message for chat {self.chat_id}")
                
        except Exception as e:
            logger.error(f"Error finishing LLM progress tracker: {e}")
    
    async def __aenter__(self):
        """Поддержка async context manager"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое завершение при выходе из контекста"""
        await self.finish()