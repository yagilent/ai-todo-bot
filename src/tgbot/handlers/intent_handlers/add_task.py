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

    if not description:
        await message.reply("Не удалось извлечь описание задачи.")
        return

    task_title = await generate_title_with_llm(description)
    logger.debug(f"Task title generated: {task_title}")

    user_timezone = db_user.timezone # Таймзона нужна для парсинга

    # Парсинг основной даты/времени/повторения
    parsed_due_info = await text_to_datetime_obj(due_text, user_timezone) if due_text else {}
    parsed_reminder_info = await text_to_datetime_obj(reminder_text, user_timezone) if reminder_text else {}

    final_dates = get_due_and_notification_datetime(
        current_due_obj=None,
        current_notification_dt=None,
        new_due_obj={ # Данные из парсинга due_text
            'date': parsed_due_info.get('date'),
            'datetime': parsed_due_info.get('datetime'),
            'has_time': parsed_due_info.get('has_time', False)
        },
        new_notification_obj={ # Данные из парсинга reminder_text
             'datetime': parsed_reminder_info.get('datetime')
        }
    )

    # --- Добавление в БД ---
    try:
        new_task = await add_task(
            session=session,
            user_telegram_id=db_user.telegram_id,
            description=description,
            title=task_title,
            due_date=final_dates['due_date'],
            due_datetime=final_dates['due_datetime'],
            has_time=final_dates['due_has_time'],
            original_due_text=due_text,
            is_repeating=parsed_due_info.get('is_repeating', False),
            recurrence_rule=parsed_due_info.get('rrule'),
            next_reminder_at=final_dates['notification_datetime'], # Берем итоговое
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