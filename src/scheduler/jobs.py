# src/scheduler/jobs.py
import logging
import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from aiogram import Bot

from typing import List, Optional, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database.models import Task, User
from src.database.crud import get_user_by_telegram_id, add_task, get_all_active_users

# Импортируем функцию отправки напоминания из responses
from src.tgbot import responses

# Импортируем функцию расчета следующего времени
from src.utils.rrule_helper import calculate_next_reminder_time

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

    # Отправляем напоминания и создаем копии для рекуррентных задач
    recurring_tasks_to_copy = []  # Список рекуррентных задач для копирования
    
    for task in tasks_to_remind:
        user = users_cache.get(task.user_telegram_id)
        if not user:
            logger.error(f"User {task.user_telegram_id} not found in cache for task {task.task_id}")
            failed_count += 1
            continue

        # --- ВЫЗЫВАЕМ ФУНКЦИЮ ИЗ RESPONSES ---
        sent_successfully = await responses.send_reminder_notification(
            bot=bot,
            task=task,
            user=user
        )
        # ------------------------------------

        if sent_successfully:
            successfully_reminded_ids.append(task.task_id)
            sent_count += 1
            
            # НОВОЕ: Если задача повторяющаяся, подготавливаем копию
            if task.is_repeating and task.recurrence_rule:
                logger.info(f"Preparing to copy recurring task {task.task_id} with rule: {task.recurrence_rule}")
                recurring_tasks_to_copy.append(task)
        else:
            failed_count += 1

    # Создаем копии рекуррентных задач и обновляем оригинальные
    if recurring_tasks_to_copy:
        await _handle_recurring_task_copies(session_pool, recurring_tasks_to_copy)
    
    # Обновляем last_reminder_sent_at для успешно отправленных задач
    if successfully_reminded_ids:
        try:
            async with session_pool() as session:
                now_utc_for_update = datetime.datetime.now(datetime.timezone.utc)
                
                # Разделяем задачи на рекуррентные и обычные
                recurring_task_ids = [t.task_id for t in recurring_tasks_to_copy]
                regular_task_ids = [tid for tid in successfully_reminded_ids if tid not in recurring_task_ids]
                
                # Для рекуррентных задач: обновляем last_reminder_sent_at, убираем recurrence_rule, обнуляем next_reminder_at
                if recurring_task_ids:
                    stmt_recurring = update(Task).where(Task.task_id.in_(recurring_task_ids)).values(
                        last_reminder_sent_at=now_utc_for_update,
                        next_reminder_at=None,
                        recurrence_rule=None,  # Убираем правило повтора с оригинала
                        is_repeating=False     # Делаем задачу обычной
                    )
                    await session.execute(stmt_recurring)
                    logger.info(f"Updated {len(recurring_task_ids)} recurring tasks - removed recurrence rules")
                
                # Для обычных задач: только обновляем last_reminder_sent_at и обнуляем next_reminder_at
                if regular_task_ids:
                    stmt_regular = update(Task).where(Task.task_id.in_(regular_task_ids)).values(
                        last_reminder_sent_at=now_utc_for_update,
                        next_reminder_at=None
                    )
                    await session.execute(stmt_regular)
                    logger.info(f"Updated {len(regular_task_ids)} regular tasks")
                
                await session.commit()
                logger.info(f"Updated DB for {len(successfully_reminded_ids)} successfully sent reminders")
        except Exception as e:
            logger.error(f"Error updating tasks after sending reminders: {e}", exc_info=True)

    logger.debug(f"Reminder job finished. Sent: {sent_count}, Failed: {failed_count}, Copied recurring: {len(recurring_tasks_to_copy)}")


async def _handle_recurring_task_copies(
    session_pool: async_sessionmaker[AsyncSession],
    recurring_tasks: List[Task]
):
    """
    Создает копии рекуррентных задач с рассчитанным следующим временем напоминания.
    """
    if not recurring_tasks:
        return
    
    logger.info(f"Creating copies for {len(recurring_tasks)} recurring tasks")
    
    try:
        async with session_pool() as session:
            for task in recurring_tasks:
                # Вычисляем следующее время напоминания
                if not task.next_reminder_at or not task.recurrence_rule:
                    logger.warning(f"Skipping task {task.task_id} - missing reminder time or recurrence rule")
                    continue
                
                # Получаем пользователя для определения таймзоны
                user = await get_user_by_telegram_id(session, task.user_telegram_id)
                user_timezone = user.timezone if user else "UTC"
                
                next_reminder_time = calculate_next_reminder_time(
                    current_reminder=task.next_reminder_at,
                    rrule_string=task.recurrence_rule,
                    timezone=user_timezone
                )
                
                if not next_reminder_time:
                    logger.warning(f"Could not calculate next reminder time for task {task.task_id}")
                    continue
                
                # Создаем копию задачи
                new_task = await add_task(
                    session=session,
                    user_telegram_id=task.user_telegram_id,
                    description=task.description,
                    title=task.title,
                    original_due_text=task.original_due_text,
                    is_repeating=True,  # Копия остается рекуррентной
                    recurrence_rule=task.recurrence_rule,  # Сохраняем правило повтора
                    next_reminder_at=next_reminder_time,  # Устанавливаем следующее время
                    raw_input=task.raw_input
                )
                
                logger.info(f"Created recurring task copy {new_task.task_id} from {task.task_id}, next reminder: {next_reminder_time}")
            
            await session.commit()
            logger.info(f"Successfully created {len(recurring_tasks)} recurring task copies")
            
    except Exception as e:
        logger.error(f"Error creating recurring task copies: {e}", exc_info=True)


async def restore_daily_reminders_job(
    session_pool: async_sessionmaker[AsyncSession]
):
    """
    Джоб, который запускается каждый час и восстанавливает напоминания 
    для пользователей, у которых наступила полночь
    """
    import pendulum
    
    current_utc = pendulum.now('UTC')
    logger.info(f"Running daily reminder restoration job at {current_utc}")
    
    restored_count = 0
    processed_users = 0
    
    try:
        async with session_pool() as session:
            # Получаем всех активных пользователей
            users = await get_all_active_users(session)
            
            for user in users:
                processed_users += 1
                
                try:
                    user_local = current_utc.in_timezone(user.timezone)
                    
                    # Если у пользователя полночь (00:xx)
                    if user_local.hour == 0:
                        logger.info(f"Processing midnight restoration for user {user.telegram_id} in {user.timezone}")
                        count = await restore_user_daily_reminders(session, user, user_local.date())
                        restored_count += count
                        
                except Exception as e:
                    logger.error(f"Error processing user {user.telegram_id}: {e}", exc_info=True)
                    continue
            
            await session.commit()
            logger.info(f"Daily restoration job completed. Users processed: {processed_users}, Reminders restored: {restored_count}")
            
    except Exception as e:
        logger.error(f"Error in daily reminder restoration job: {e}", exc_info=True)


async def restore_user_daily_reminders(
    session: AsyncSession, 
    user: User, 
    date
) -> int:
    """
    Восстанавливает next_reminder_at для задач пользователя на указанную дату.
    Возвращает количество восстановленных задач.
    """
    import pendulum
    
    # Находим задачи без next_reminder_at, но с недавним last_reminder_sent_at
    yesterday = pendulum.instance(date).subtract(days=1)
    today_start = pendulum.instance(date).start_of('day')
    
    stmt = select(Task).where(
        Task.user_telegram_id == user.telegram_id,
        Task.status == 'pending',
        Task.next_reminder_at == None,
        Task.last_reminder_sent_at != None,
        Task.last_reminder_sent_at >= yesterday.start_of('day').in_timezone('UTC'),
        Task.last_reminder_sent_at < today_start.in_timezone('UTC')
    )
    
    result = await session.execute(stmt)
    tasks = result.scalars().all()
    
    restored_count = 0
    
    for task in tasks:
        try:
            # Извлекаем время из last_reminder_sent_at
            original_reminder = pendulum.instance(task.last_reminder_sent_at).in_timezone(user.timezone)
            
            # Устанавливаем на сегодня в то же время
            new_reminder = today_start.add(
                hours=original_reminder.hour,
                minutes=original_reminder.minute
            ).in_timezone('UTC')
            
            task.next_reminder_at = new_reminder
            restored_count += 1
            
            logger.info(f"Restored reminder for task {task.task_id}: {new_reminder} (was {task.last_reminder_sent_at})")
            
        except Exception as e:
            logger.error(f"Error restoring reminder for task {task.task_id}: {e}")
            continue
    
    return restored_count


def register_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession]
    ):
    """Регистрирует периодические задачи в планировщике."""
    try:
        # Джоб проверки и отправки напоминаний
        scheduler.add_job(
            check_and_send_reminders,
            trigger='interval',
            minutes=1, # Запускать каждую минуту (можно настроить)
            id='reminder_check_job', # Уникальный ID джобы
            replace_existing=True, # Заменять джобу, если она уже есть
            kwargs={'bot': bot, 'session_pool': session_pool} # Передаем зависимости
        )
        logger.info("Job 'check_and_send_reminders' scheduled to run every 1 minute.")
        
        # Джоб восстановления ежедневных напоминаний
        scheduler.add_job(
            restore_daily_reminders_job,
            trigger='interval',
            hours=1, # Запускать каждый час
            id='daily_reminder_restore_job',
            replace_existing=True,
            kwargs={'session_pool': session_pool}
        )
        logger.info("Job 'restore_daily_reminders' scheduled to run every hour.")
        
    except Exception as e:
        logger.error(f"Error scheduling jobs: {e}", exc_info=True)