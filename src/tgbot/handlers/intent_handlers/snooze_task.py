# src/tgbot/handlers/intent_handlers/snooze_task.py
import logging
import datetime
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update # Импортируем update

from src.database.models import User, Task
from src.utils.date_parser import text_to_datetime_obj
from src.database.crud import get_task_by_id # Нужна для проверки
import pendulum

from src.database.crud import update_task_reminder_time

from src.tgbot import responses

logger = logging.getLogger(__name__)

async def handle_snooze_task(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict, # Содержит snooze_details
    task_id: int  # ID из контекста реплая
):
    """Обрабатывает намерение отложить напоминание для КОНКРЕТНОЙ задачи."""
    snooze_details = params.get("snooze_details")
    user_telegram_id = db_user.telegram_id
    user_timezone = db_user.timezone

    if not snooze_details:
        await message.reply("Не понял, на какое время отложить напоминание.")
        return

    logger.info(f"Handling snooze_task intent for user {user_telegram_id}, task_id: {task_id}. Details: '{snooze_details}'")

    try:
        # Проверяем задачу
        task = await get_task_by_id(session, task_id)
        if not task:
            await message.reply(f"Не нашел задачу (ID: {task_id}), для которой нужно отложить напоминание.")
            return
        if task.user_telegram_id != user_telegram_id:
            await message.reply("Похоже, эта задача не ваша.")
            return

        # Парсим время откладывания
        parsed_time_info = await text_to_datetime_obj(snooze_details, user_timezone)
        logger.debug(f"Snooze handle time info: {parsed_time_info}")
        new_reminder_time_utc = parsed_time_info.get('datetime')

        if not new_reminder_time_utc:
            await message.reply(f"Не смог разобрать время '{snooze_details}'. Попробуйте: 'через 15 минут', 'в 17:00', 'завтра утром'.")
            return

        # Проверка, что новое время в будущем
        if new_reminder_time_utc <= pendulum.now('UTC'):
             await message.reply("Указанное время уже прошло. Пожалуйста, укажите время в будущем.")
             return

        # Обновляем время напоминания в БД
        success = await update_task_reminder_time(session, task_id, new_reminder_time_utc)

        # Ответ пользователю
        if success:
            await responses.send_task_operation_confirmation(
                 message=message,
                 action_title="Напоминание отложено",
                 task=task,
                 user=db_user
             )
        else:
            await message.reply("Не удалось обновить время напоминания для этой задачи (возможно, она была удалена?).")

    except Exception as e:
        logger.error(f"Error handling snooze_task for user {user_telegram_id}, task {task_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при откладывании напоминания.")