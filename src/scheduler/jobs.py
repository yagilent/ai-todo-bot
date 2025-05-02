# src/scheduler/jobs.py
import logging
import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from aiogram import Bot

from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database.models import Task, User
from src.database.crud import get_user_by_telegram_id # Нужна функция для получения User

# Импортируем функцию отправки напоминания из responses
from src.tgbot import responses

logger = logging.getLogger(__name__)

async def check_and_send_reminders(
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession]
):
    """
    Проверяет задачи и отправляет напоминания через responses.send_reminder_notification.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    logger.debug(f"Running reminder check job at {now_utc}")

    tasks_to_remind: list[Task] = []
    users_cache: Dict[int, User] = {} # Кеш для объектов User

    # Получаем задачи
    try:
        async with session_pool() as session:
            stmt = select(Task).where(
                Task.status == 'pending',
                Task.next_reminder_at != None, # Убедимся, что время установлено
                Task.next_reminder_at <= now_utc,
                (Task.last_reminder_sent_at == None) | (Task.last_reminder_sent_at < Task.next_reminder_at) # noqa E711
            ).order_by(Task.next_reminder_at)

            result = await session.execute(stmt)
            tasks_to_remind = result.scalars().all()

            # Предзагружаем пользователей, чтобы не делать запрос в цикле
            user_ids_to_fetch = {t.user_telegram_id for t in tasks_to_remind}
            if user_ids_to_fetch:
                 user_stmt = select(User).where(User.telegram_id.in_(user_ids_to_fetch))
                 user_result = await session.execute(user_stmt)
                 for user in user_result.scalars().all():
                     users_cache[user.telegram_id] = user

    except Exception as e:
         logger.error(f"Error fetching tasks/users for reminders: {e}", exc_info=True)
         return

    if not tasks_to_remind:
        logger.debug("No tasks found for reminders.")
        return # Выходим из функции, если задач нет


    logger.info(f"Found {len(tasks_to_remind)} tasks to remind.")
    sent_count = 0
    failed_count = 0
    successfully_reminded_ids = [] # ID задач, для которых УСПЕШНО отправили напоминание

    # Отправляем напоминания
    for task in tasks_to_remind:
        user = users_cache.get(task.user_telegram_id)
        if not user:
            logger.error(f"User {task.user_telegram_id} not found in cache for task {task.task_id}")
            failed_count += 1
            continue # Пропускаем задачу, если не нашли пользователя

        # --- ВЫЗЫВАЕМ ФУНКЦИЮ ИЗ RESPONSES ---
        sent_successfully = await responses.send_reminder_notification(
            bot=bot,
            task=task,
            user=user # Передаем объект User
        )
        # ------------------------------------

        if sent_successfully:
            successfully_reminded_ids.append(task.task_id)
            sent_count += 1
        else:
            failed_count += 1
            # TODO: Что делать при ошибке отправки? Повторить? Пометить?

    # Обновляем last_reminder_sent_at и next_reminder_at ТОЛЬКО для успешно отправленных
    if successfully_reminded_ids:
        try:
             async with session_pool() as session:
                 now_utc_for_update = datetime.datetime.now(datetime.timezone.utc) # Обновляем время
                 # --- Пока обнуляем next_reminder_at ---
                 # TODO: Реализовать логику пересчета next_reminder_at для повторов/цепочек
                 stmt_update = update(Task).where(Task.task_id.in_(successfully_reminded_ids)).values(
                     last_reminder_sent_at=now_utc_for_update,
                     next_reminder_at=None
                 )
                 await session.execute(stmt_update)
                 await session.commit()
                 logger.info(f"Updated DB for {len(successfully_reminded_ids)} successfully sent reminders.")
        except Exception as e:
             logger.error(f"Error updating tasks after sending reminders: {e}", exc_info=True)

    logger.debug(f"Reminder job finished. Sent: {sent_count}, Failed: {failed_count}")

def register_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession]
    ):
    """Регистрирует периодические задачи в планировщике."""
    try:
        scheduler.add_job(
            check_and_send_reminders,
            trigger='interval',
            minutes=1, # Запускать каждую минуту (можно настроить)
            id='reminder_check_job', # Уникальный ID джобы
            replace_existing=True, # Заменять джобу, если она уже есть
            kwargs={'bot': bot, 'session_pool': session_pool} # Передаем зависимости
        )
        logger.info("Job 'check_and_send_reminders' scheduled to run every 1 minute.")
    except Exception as e:
        logger.error(f"Error scheduling reminder job: {e}", exc_info=True)