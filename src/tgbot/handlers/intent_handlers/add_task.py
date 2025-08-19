# src/tgbot/handlers/intent_handlers/add_task.py
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
import pendulum
import datetime
from typing import Optional, List, Dict, Any

from src.tgbot import responses

from src.database.crud import add_task
from src.database.models import User
from src.utils.date_parser import text_to_datetime_obj
from src.utils.reminders import calculate_next_reminder # Импортируем обновленную функцию

from src.utils.tasks import get_due_and_notification_datetime

from src.llm.gemini_client import generate_title_with_llm

logger = logging.getLogger(__name__)

async def handle_add_task(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict
):
    """Обрабатывает намерение добавить задачу."""
    logger.debug(f"Handling add_task intent for user {db_user.telegram_id}")
    description = params.get("description")
    due_text = params.get("due_date_time_text")
    reminder_text = params.get("reminder_text")
    
    # НОВОЕ: Получаем готовое время напоминания из коротких промптов
    parsed_reminder_utc = params.get("parsed_reminder_utc")

    if not description:
        await message.reply("Не удалось извлечь описание задачи.")
        return

    task_title = await generate_title_with_llm(description)
    logger.debug(f"Task title generated: {task_title}")

    # УПРОЩЁННАЯ ЛОГИКА: Используем только готовое время напоминания
    reminder_datetime = None
    if parsed_reminder_utc:
        try:
            reminder_datetime = pendulum.parse(parsed_reminder_utc)
            logger.info(f"Using reminder time from new prompts: {reminder_datetime}")
        except Exception as e:
            logger.error(f"Failed to parse reminder time from prompts: {parsed_reminder_utc}, error: {e}")

    # Больше НЕ парсим время события - только время напоминания!

    # --- Добавление в БД ---
    try:
        new_task = await add_task(
            session=session,
            user_telegram_id=db_user.telegram_id,
            description=description,
            title=task_title,
            # УБИРАЕМ время события - оставляем только время напоминания
            due_date=None,
            due_datetime=None,
            has_time=False,
            original_due_text=due_text,
            is_repeating=False,  # Пока не поддерживается
            recurrence_rule=None,  # Пока не поддерживается
            next_reminder_at=reminder_datetime,  # Готовое время напоминания из промптов
            raw_input=message.text
       )
        # --- Ответ пользователю ---
        await responses.send_task_operation_confirmation(
            message=message,
            action_title="Задача добавлена",
            task=new_task,
            user=db_user
        )
    except Exception as e:
        logger.error(f"Failed to add task in intent handler for user {db_user.telegram_id}: {e}", exc_info=True)
        await message.reply("Не удалось сохранить задачу...")