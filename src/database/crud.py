# src/database/crud.py

import logging
import datetime
from typing import Optional, List, Dict, Any 
import pendulum

from sqlalchemy import select, update
from sqlalchemy import or_, and_, case, func, TIMESTAMP, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Импортируем обе модели
from src.database.models import User, Task

logger = logging.getLogger(__name__)

# --- User CRUD ---

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получает пользователя по Telegram ID."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()

async def get_all_active_users(session: AsyncSession) -> List[User]:
    """Получает всех активных пользователей (имеющих задачи)."""
    result = await session.execute(
        select(User).join(Task, User.telegram_id == Task.user_telegram_id).distinct()
    )
    return result.scalars().all()

async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None
    # timezone и timezone_text будут пока None или дефолтные
) -> User:
    """Создает нового пользователя."""
    # Проверка, чтобы не создать дубликат (хотя PK должен защитить)
    existing_user = await get_user_by_telegram_id(session, telegram_id)
    if existing_user:
        logger.warning(f"Attempted to create user {telegram_id} which already exists.")
        return existing_user

    new_user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        username=username
        # timezone использует server_default='UTC'
    )
    session.add(new_user)
    try:
        await session.commit()
        await session.refresh(new_user)
        logger.info(f"New user created: {new_user}")
        return new_user
    except IntegrityError: # На случай гонки потоков
        await session.rollback()
        logger.warning(f"User {telegram_id} creation failed due to IntegrityError (likely race condition).")
        return await get_user_by_telegram_id(session, telegram_id) # Возвращаем существующего
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during user creation for {telegram_id}: {e}", exc_info=True)
        raise

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None
) -> User:
    """Получает пользователя по Telegram ID или создает нового."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        # Обновляем данные, если они изменились
        update_needed = False
        if user.full_name != full_name: user.full_name = full_name; update_needed = True
        if user.username != username: user.username = username; update_needed = True

        if update_needed:
            try:
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"User {telegram_id} data updated.")
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database error during user update for {telegram_id}: {e}", exc_info=True)
                # Игнорируем ошибку обновления, возвращаем пользователя как есть
        else:
            logger.debug(f"User {telegram_id} found, no update needed.")
        return user
    else:
        logger.info(f"User {telegram_id} not found, creating new one.")
        return await create_user(session, telegram_id, full_name, username)

async def update_user_timezone(
    session: AsyncSession,
    telegram_id: int,
    timezone: str,
    timezone_text: Optional[str] = None
    ) -> Optional[User]:
    """Обновляет таймзону пользователя."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        logger.error(f"Attempted to update timezone for non-existent user {telegram_id}")
        return None

    user.timezone = timezone
    user.timezone_text = timezone_text # Обновляем и текст, если передан
    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Timezone updated for user {telegram_id} to {timezone}")
        return user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during timezone update for {telegram_id}: {e}", exc_info=True)
        raise


# --- Task CRUD ---

async def add_task(
    session: AsyncSession,
    user_telegram_id: int,
    description: str,
    title: Optional[str] = None,
    # УПРОЩЕНИЕ: Убираем поля времени события - оставляем только время напоминания
    # due_date: Optional[datetime.date] = None,
    # due_datetime: Optional[datetime.datetime] = None,
    # has_time: bool = False,
    original_due_text: Optional[str] = None,
    is_repeating: bool = False,
    recurrence_rule: Optional[str] = None,
    next_reminder_at: Optional[datetime.datetime] = None,
    raw_input: Optional[str] = None
) -> Task:
    """Добавляет новую задачу в базу данных."""
    # Проверяем, существует ли пользователь (хорошая практика перед вставкой FK)
    user = await get_user_by_telegram_id(session, user_telegram_id)
    if not user:
         # Можно либо создать пользователя здесь, либо выбросить ошибку
         logger.error(f"Attempted to add task for non-existent user {user_telegram_id}")
         # TODO: Решить, как обрабатывать - создавать юзера или нет? Пока выбрасываем ошибку.
         raise ValueError(f"User with telegram_id {user_telegram_id} not found.")

    new_task = Task(
        user_telegram_id=user_telegram_id,
        description=description,
        title=title,
        # УПРОЩЕНИЕ: Всегда устанавливаем время события в None/False
        due_date=None,
        due_datetime=None,
        has_time=False,
        original_due_text=original_due_text,
        is_repeating=is_repeating,
        recurrence_rule=recurrence_rule,
        next_reminder_at=next_reminder_at,  # Только время напоминания важно
        raw_input=raw_input
    )
    session.add(new_task)
    try:
        await session.commit()
        await session.refresh(new_task)
        logger.info(f"Task added: ID={new_task.task_id} for user TG_ID={user_telegram_id}")
        logger.debug(
            f"Saved Task Details: "
            f"task_id={getattr(new_task, 'task_id', 'N/A')}, " # ID теперь должен быть
            f"user_telegram_id={getattr(new_task, 'user_telegram_id', 'N/A')}, "
            f"title={getattr(new_task, 'title', None)!r}, " # Используем !r для кавычек
            f"description={getattr(new_task, 'description', '')[:50]!r}..., "
            f"due_date={getattr(new_task, 'due_date', None)}, "
            f"due_datetime={getattr(new_task, 'due_datetime', None)}, "
            f"has_time={getattr(new_task, 'has_time', None)}, "
            f"status={getattr(new_task, 'status', 'N/A')!r}, " # Добавим статус, если он есть
            f"next_reminder_at={getattr(new_task, 'next_reminder_at', None)}"
            # Добавьте другие поля по необходимости (created_at, recurrence_rule и т.д.)
        )
        return new_task
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during task creation for user {user_telegram_id}: {e}", exc_info=True)
        raise

async def get_tasks_by_user(session: AsyncSession, user_telegram_id: int, status: Optional[str] = 'pending') -> List[Task]:
    """Получает список задач пользователя, опционально фильтруя по статусу."""
    stmt = select(Task).where(Task.user_telegram_id == user_telegram_id)
    if status and status != 'all': # Добавляем фильтр по статусу, если он указан и не 'all'
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.created_at.desc()) # Сортируем по убыванию даты создания

    result = await session.execute(stmt)
    tasks = result.scalars().all()
    logger.debug(f"Found {len(tasks)} tasks for user {user_telegram_id} with status '{status}'")
    return tasks

async def get_task_by_id(session: AsyncSession, task_id: int) -> Optional[Task]:
    """Получает задачу по её ID."""
    result = await session.execute(select(Task).where(Task.task_id == task_id))
    return result.scalar_one_or_none()

async def update_task_status(session: AsyncSession, task_id: int, new_status: str) -> Optional[Task]:
    """Обновляет статус задачи (pending/done) и completed_at."""
    if new_status not in ['pending', 'done']:
        logger.error(f"Invalid status provided for task {task_id}: {new_status}")
        raise ValueError("Invalid status value")

    task = await get_task_by_id(session, task_id)
    if not task:
        logger.warning(f"Task with ID {task_id} not found for status update.")
        return None

    task.status = new_status
    if new_status == 'done':
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        # TODO: Возможно, нужно обнулить next_reminder_at?
        # task.next_reminder_at = None
    else: # Если вернули в pending
        task.completed_at = None
        # TODO: Возможно, нужно пересчитать next_reminder_at?

    try:
        session.add(task)
        await session.commit()
        await session.refresh(task)
        logger.info(f"Status updated for task {task_id} to '{new_status}'")
        return task
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during status update for task {task_id}: {e}", exc_info=True)
        raise



async def get_all_user_tasks(
    session: AsyncSession,
    user_telegram_id: int,
    only_pending: bool = True # По умолчанию берем только активные для поиска
    ) -> List[Task]:
    """Получает все (или только активные) задачи пользователя."""
    stmt = select(Task).where(Task.user_telegram_id == user_telegram_id)
    if only_pending:
        stmt = stmt.where(Task.status == 'pending')
    stmt = stmt.order_by(Task.created_at.desc()) # Сортируем

    result = await session.execute(stmt)
    tasks = result.scalars().all()
    logger.debug(f"Fetched {len(tasks)} tasks (pending={only_pending}) for user {user_telegram_id} for LLM context.")
    return tasks

async def get_tasks_by_ids(
    session: AsyncSession,
    user_telegram_id: int,
    task_ids: List[int]
) -> List[Task]:
    """Получает задачи по списку их ID, проверяя принадлежность пользователю."""
    if not task_ids:
        return [] # Если список ID пуст, ничего не ищем

    stmt = select(Task).where(
        Task.user_telegram_id == user_telegram_id,
        Task.task_id.in_(task_ids)
    ).order_by(Task.created_at.desc()) # Сортируем так же? Или по ID?

    result = await session.execute(stmt)
    tasks = result.scalars().all()
    # Проверка, что все запрошенные ID найдены и принадлежат пользователю (на всякий случай)
    if len(tasks) != len(task_ids):
        logger.warning(f"Requested {len(task_ids)} task IDs, but found {len(tasks)} for user {user_telegram_id}")
    return tasks

async def update_task_due_date(
    session: AsyncSession,
    task_id: int,
    # УПРОЩЕНИЕ: Убираем параметры времени события
    # new_due_date: Optional[datetime.date],
    # new_due_datetime: Optional[datetime.datetime], # UTC
    # new_has_time: bool,
    new_original_due_text: Optional[str],
    new_next_reminder_at: Optional[datetime.datetime] # UTC - только время напоминания
) -> Optional[Task]:
    """Обновляет время напоминания задачи (время события больше не используется)."""
    try:
        values_to_update = {
            # УПРОЩЕНИЕ: Всегда сбрасываем время события
            "due_date": None,
            "due_datetime": None,
            "has_time": False,
            "original_due_text": new_original_due_text,
            "next_reminder_at": new_next_reminder_at,  # Только время напоминания важно
        }
        stmt = update(Task).where(Task.task_id == task_id).values(
            **values_to_update
        ).returning(Task)

        result = await session.execute(stmt)
        await session.commit()
        updated_task = result.scalar_one_or_none()

        if updated_task:
            logger.info(f"Rescheduled task {task_id}. New due_date: None, next_reminder: {new_next_reminder_at}")
        else:
            logger.warning(f"Task {task_id} not found for rescheduling.")
        return updated_task
    except Exception as e:
        await session.rollback()
        logger.error(f"Error rescheduling task {task_id}: {e}", exc_info=True)
        raise


async def update_task_description(
    session: AsyncSession,
    task_id: int,
    new_description: str
) -> Optional[Task]:
    """Обновляет описание задачи."""
    try:
        stmt = update(Task).where(Task.task_id == task_id).values(
            description=new_description
        ).returning(Task)

        result = await session.execute(stmt)
        await session.commit()
        updated_task = result.scalar_one_or_none()

        if updated_task:
            logger.info(f"Updated description for task {task_id}.")
        else:
            logger.warning(f"Task {task_id} not found for description update.")
        return updated_task
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating description for task {task_id}: {e}", exc_info=True)
        raise

# Функция update_task_reminder_time может быть здесь или в snooze_task.py
# Если она здесь, то ее нужно импортировать в snooze_task.py
async def update_task_reminder_time(session: AsyncSession, task_id: int, new_reminder_time_utc: datetime.datetime) -> Optional[Task]:
    """Обновляет только next_reminder_at для задачи."""
    try:
        stmt = update(Task).where(Task.task_id == task_id).values(
            next_reminder_at=new_reminder_time_utc
        ).returning(Task) # Возвращаем задачу для консистентности
        result = await session.execute(stmt)
        await session.commit()
        updated_task = result.scalar_one_or_none()

        if updated_task:
            logger.info(f"Updated next_reminder_at for task {task_id} to {new_reminder_time_utc}")
        else:
            logger.warning(f"Task {task_id} not found for reminder time update.")
        return updated_task
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating reminder time for task {task_id}: {e}", exc_info=True)
        raise


async def find_tasks_by_criteria(
    session: AsyncSession,
    db_user: User,
    search_text: Optional[str] = None, # Поиск по тексту в описании и заголовке
    start_date: Optional[datetime.datetime] = None, # UTC datetime - для фильтрации по времени напоминания
    end_date: Optional[datetime.datetime] = None, # UTC datetime - для фильтрации по времени напоминания
    status: Optional[str] = 'pending',
    include_null_reminders: bool = False  # Включать ли задачи с next_reminder_at=NULL (только для /today)
) -> List[Task]:
    """
    УПРОЩЁННАЯ ВЕРСИЯ: Ищет задачи пользователя по критериям.
    Теперь используется только время напоминания (next_reminder_at), время события не используется.
    """
    user_telegram_id = db_user.telegram_id
    logger.debug(f"Finding tasks by criteria for user {user_telegram_id}. "
                 f"Search: '{search_text}', Reminder start: {start_date}, Reminder end: {end_date}, Status: {status}")

    stmt = select(Task).where(Task.user_telegram_id == user_telegram_id)

    # Фильтр по статусу  
    if status and status != 'all':
        stmt = stmt.where(Task.status == status)

    # Фильтр по текстовому запросу
    if search_text:
        search_pattern = f"%{search_text.lower()}%"
        stmt = stmt.where(
            (Task.description.ilike(search_pattern)) |
            (Task.title.ilike(search_pattern))
        )

    # УПРОЩЕНИЕ: Фильтрация по времени напоминания
    if start_date and end_date:
        if include_null_reminders:
            # Для /today включаем задачи с next_reminder_at=NULL
            stmt = stmt.where(
                or_(
                    # Стандартный случай - задачи с назначенным временем в диапазоне
                    and_(
                        Task.next_reminder_at >= start_date,
                        Task.next_reminder_at <= end_date
                    ),
                    # Задачи без назначенного времени (только для /today)
                    Task.next_reminder_at == None
                )
            )
        else:
            # Для /tomorrow и других команд - только задачи с назначенным временем
            stmt = stmt.where(
                and_(
                    Task.next_reminder_at >= start_date,
                    Task.next_reminder_at <= end_date
                )
            )
    elif start_date:
        stmt = stmt.where(Task.next_reminder_at >= start_date)
    elif end_date:
        stmt = stmt.where(Task.next_reminder_at <= end_date)

    # УПРОЩЁННАЯ сортировка: по времени напоминания, потом по дате создания
    stmt = stmt.order_by(
        Task.next_reminder_at.asc().nulls_last(),
        Task.created_at.asc()
    )

    result = await session.execute(stmt)
    tasks = result.scalars().all()
    logger.info(f"Found {len(tasks)} tasks matching criteria for user {user_telegram_id}.")
    return tasks