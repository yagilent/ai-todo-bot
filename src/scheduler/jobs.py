# src/scheduler/jobs.py
import logging
import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from aiogram import Bot

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database.models import Task # Импортируем модель Task

logger = logging.getLogger(__name__)

async def check_and_send_reminders(
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession] # Получаем фабрику сессий
):
    """
    Проверяет задачи, для которых подошло время напоминания, и отправляет их.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    logger.debug(f"Running reminder check job at {now_utc}")

    tasks_to_remind: list[Task] = []

    # Получаем задачи, готовые к напоминанию
    try:
        async with session_pool() as session: # Создаем новую сессию
            stmt = select(Task).where(
                Task.status == 'pending',
                Task.next_reminder_at <= now_utc,
                # Проверяем, что напоминание не было отправлено после назначенного времени
                (Task.last_reminder_sent_at == None) | (Task.last_reminder_sent_at < Task.next_reminder_at) # noqa E711
            ).order_by(Task.next_reminder_at) # Сортируем, чтобы обработать самые старые первыми

            result = await session.execute(stmt)
            tasks_to_remind = result.scalars().all()
    except Exception as e:
         logger.error(f"Error fetching tasks for reminders: {e}", exc_info=True)
         return # Выходим, если не смогли получить задачи

    if not tasks_to_remind:
        logger.debug("No tasks found for reminders.")
        return

    logger.info(f"Found {len(tasks_to_remind)} tasks to remind.")

    sent_count = 0
    failed_count = 0
    updated_ids = []

    # Отправляем напоминания и обновляем БД
    for task in tasks_to_remind:
        reminder_text = f"🔔 **Напоминание!**\n\nЗадача: <i>{task.description or 'Без описания'}</i>"
        if task.due_date:
             # TODO: Форматировать дату/время для пользователя с учетом его таймзоны
             due_date_str = task.due_date.strftime('%Y-%m-%d %H:%M') + " UTC" # Пока просто UTC
             reminder_text += f"\nСрок: {due_date_str}"
        reminder_text += f"\n\n(ID: {task.task_id})"
        

        try:
            # TODO: Добавить обработку ошибок отправки (BotBlocked, etc.)
            await bot.send_message(chat_id=task.user_telegram_id, text=reminder_text)
            logger.info(f"Sent reminder for task {task.task_id} to user {task.user_telegram_id}")
            updated_ids.append(task.task_id) # Добавляем ID для обновления в БД
            sent_count += 1
        except Exception as e:
             logger.error(f"Failed to send reminder for task {task.task_id} to user {task.user_telegram_id}: {e}")
             failed_count += 1
             # TODO: Решить, что делать с задачами, для которых не удалось отправить напоминание
             # (повторить позже, пометить как ошибку и т.д.)

    # Обновляем записи в БД после отправки
    if updated_ids:
        try:
             async with session_pool() as session:
                 # --- ИЗМЕНЕНИЕ: Пока просто обнуляем next_reminder_at ---
                 stmt_update = update(Task).where(Task.task_id.in_(updated_ids)).values(
                     last_reminder_sent_at=now_utc,
                     next_reminder_at=None # Обнуляем, чтобы не напоминать снова (пока нет логики повторов)
                 )
                 await session.execute(stmt_update)
                 await session.commit()
                 logger.info(f"Updated last_reminder_sent_at for {len(updated_ids)} tasks.")
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