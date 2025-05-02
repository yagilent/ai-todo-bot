# src/tgbot/handlers/intent_handlers/reschedule_task.py
import logging
import datetime
from typing import Optional
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

import pendulum

from src.database.crud import update_task_due_date, get_task_by_id # Нужны эти функции
from src.database.models import User
from src.utils.date_parser import text_to_datetime_obj # Парсер для новой даты
from src.utils.reminders import calculate_next_reminder # Для пересчета напоминания

from src.tgbot import responses

from src.utils.tasks import get_due_and_notification_datetime

logger = logging.getLogger(__name__)

async def handle_reschedule_task(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict, # Содержит new_due_date_text
    task_id: int
):
    """Обрабатывает намерение изменить срок выполнения задачи."""
    new_due_text = params.get("new_due_date_text")
    user_telegram_id = db_user.telegram_id
    user_timezone = db_user.timezone

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

        # Парсим новую дату/время
        parsed_due_info = await text_to_datetime_obj(new_due_text, user_timezone)

        current_due_obj = {
            'date': current_task.due_date,
            'datetime': current_task.due_datetime,
            'has_time': current_task.has_time
        }

        new_due_obj={
            'date': parsed_due_info.get('date'),
            'datetime': parsed_due_info.get('datetime'),
            'has_time': parsed_due_info.get('has_time', False)
        }

        final_dates = get_due_and_notification_datetime(
            current_due_obj=current_due_obj,
            current_notification_dt=current_task.next_reminder_at, # Передаем текущее
            new_due_obj=new_due_obj, # Передаем новое
            new_notification_obj=None # Нового явного уведомления нет в этом интенте
        )

        final_due_date = final_dates['due_date']
        final_due_datetime = final_dates['due_datetime']
        final_due_has_time = final_dates['due_has_time']
        final_notification_datetime = final_dates['notification_datetime'] # Будет вычислено по умолчанию или None

        if not final_due_date and not final_due_datetime and not parsed_due_info.get('rrule'):
            logger.warning(f"Failed to parse new due date '{new_due_text}' for task {task_id}")
            await message.reply(f"Не смог разобрать новую дату/время '{new_due_text}'. Попробуйте указать иначе.")
            return

        # 4. Обновляем задачу в БД
        # TODO: Добавить обновление is_repeating и recurrence_rule, если они изменятся
        updated_task = await update_task_due_date(
            session=session,
            task_id=task_id,
            new_due_date=final_due_date,
            new_due_datetime=final_due_datetime,
            new_has_time=final_due_has_time,
            new_original_due_text=new_due_text, # Сохраняем новый текст
            new_next_reminder_at=final_notification_datetime # Сохраняем новое время напоминания
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