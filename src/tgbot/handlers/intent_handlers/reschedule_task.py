# src/tgbot/handlers/intent_handlers/reschedule_task.py
import logging
import datetime
from typing import Optional
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

import pendulum

from src.database.crud import update_task_due_date, get_task_by_id
from src.database.models import User
# Больше НЕ используем старые утилиты:
# from src.utils.date_parser import text_to_datetime_obj
# from src.utils.reminders import calculate_next_reminder
# from src.utils.tasks import get_due_and_notification_datetime

from src.tgbot import responses

logger = logging.getLogger(__name__)

async def handle_reschedule_task(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict, # Содержит new_due_date_text и parsed_reminder_utc
    task_id: int
):
    """Обрабатывает намерение изменить срок выполнения задачи."""
    new_due_text = params.get("new_due_date_text")
    parsed_reminder_utc = params.get("parsed_reminder_utc")  # НОВОЕ: готовое время из коротких промптов
    user_telegram_id = db_user.telegram_id

    if not new_due_text:
        logger.warning(f"Reschedule intent for task {task_id} without new date text. User: {user_telegram_id}")
        await message.reply("Не понял, на какую дату или время перенести задачу.")
        return

    logger.info(f"Handling reschedule_task intent for user {user_telegram_id}, task_id: {task_id}. New date text: '{new_due_text}'")

    try:
        # Проверяем, что задача существует и принадлежит пользователю
        current_task = await get_task_by_id(session, task_id)
        if not current_task:
            await message.reply("Не нашел задачу с таким ID для переноса.")
            return
        if current_task.user_telegram_id != user_telegram_id:
            await message.reply("Похоже, эта задача не ваша.")
            return

        # УПРОЩЁННАЯ ЛОГИКА: Используем готовое время напоминания из коротких промптов
        new_reminder_datetime = None
        if parsed_reminder_utc:
            try:
                new_reminder_datetime = pendulum.parse(parsed_reminder_utc)
                logger.info(f"Using new reminder time from prompts: {new_reminder_datetime}")
            except Exception as e:
                logger.error(f"Failed to parse reminder time from prompts: {parsed_reminder_utc}, error: {e}")

        if not new_reminder_datetime:
            logger.warning(f"No valid new reminder time for reschedule task {task_id}")
            await message.reply(f"Не смог разобрать новое время '{new_due_text}'. Попробуйте указать иначе.")
            return

        # 4. Обновляем задачу в БД (теперь только время напоминания)
        updated_task = await update_task_due_date(
            session=session,
            task_id=task_id,
            new_original_due_text=new_due_text,
            new_next_reminder_at=new_reminder_datetime  # Только время напоминания из коротких промптов
        )

        if updated_task:
             await responses.send_task_operation_confirmation(
                 message=message,
                 action_title="Срок задачи изменен",
                 task=updated_task,
                 user=db_user
             )
        else:
             await message.reply("Не удалось обновить срок задачи.")

    except Exception as e:
        logger.error(f"Error handling reschedule_task for user {user_telegram_id}, task {task_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при переносе задачи.")