# src/tgbot/handlers/find_tasks_commands.py
import logging
from aiogram import Router, types
# Импортируем фильтры команд
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
import pendulum
from typing import Optional

# Импорты для поиска и форматирования

from src.database.crud import find_tasks_by_criteria, get_or_create_user
from src.database.models import User
from src.utils.formatters import format_task_list
from src.tgbot.keyboards.inline import create_tasks_keyboard # Клавиатура с кнопками

logger = logging.getLogger(__name__)
find_commands_router = Router(name="find_tasks_commands")

async def find_and_reply(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    status: str,
    start_date: Optional[pendulum.DateTime],
    end_date: Optional[pendulum.DateTime],
    title_prefix: str # Для заголовка ответа
):
    """Вспомогательная функция для поиска и ответа."""
    try:
        # Собираем критерии для find_tasks
        tasks = await find_tasks_by_criteria(
            session=session,
            db_user=db_user,
            search_text=None, # Для команд поиск по тексту не нужен
            start_date=start_date, # Передаем start_date (pendulum или None)
            end_date=end_date,     # Передаем end_date (pendulum или None)
            status=status          # Передаем status
        )

        keyboard = create_tasks_keyboard(tasks, db_user)
        
        if tasks:
            response_text = f"{title_prefix}: {len(tasks)}"
            await message.answer(response_text, reply_markup=keyboard)
        else:
            await message.answer(f"{title_prefix}: не найдено.")

    except Exception as e:
        logger.error(f"Error processing command '{message.text}' for user {db_user.telegram_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при поиске задач.")


@find_commands_router.message(Command("today"))
async def handle_today_command(message: types.Message, session: AsyncSession):
    """Обрабатывает команду /today."""
    user_id = message.from_user.id
    user = await get_or_create_user(session, user_id, message.from_user.full_name, message.from_user.username)
    if not user: await message.answer("Ошибка профиля."); return

    now_local = pendulum.now(user.timezone)
    start_date_utc = now_local.start_of('day').in_timezone('UTC')
    end_date_utc = now_local.end_of('day').in_timezone('UTC')

    await find_and_reply(message, session, user, None, start_date_utc, end_date_utc, "Задачи на сегодня")


@find_commands_router.message(Command("tomorrow"))
async def handle_tomorrow_command(message: types.Message, session: AsyncSession):
    """Обрабатывает команду /tomorrow."""
    user_id = message.from_user.id
    user = await get_or_create_user(session, user_id, message.from_user.full_name, message.from_user.username)
    if not user: await message.answer("Ошибка профиля."); return

    now_local = pendulum.now(user.timezone)
    start_date_utc = now_local.add(days=1).start_of('day').in_timezone('UTC')
    end_date_utc = now_local.add(days=1).end_of('day').in_timezone('UTC')

    await find_and_reply(message, session, user, None, start_date_utc, end_date_utc, "Задачи на завтра")


@find_commands_router.message(Command("overdue"))
async def handle_overdue_command(message: types.Message, session: AsyncSession):
    """Обрабатывает команду /overdue."""
    user_id = message.from_user.id
    user = await get_or_create_user(session, user_id, message.from_user.full_name, message.from_user.username)
    if not user: await message.answer("Ошибка профиля."); return

    # find_tasks сама обрабатывает статус 'overdue'
    await find_and_reply(message, session, user, 'overdue', None, None, "Просроченные задачи")


@find_commands_router.message(Command("all_pending"))
async def handle_all_pending_command(message: types.Message, session: AsyncSession):
    """Обрабатывает команду /all_pending."""
    user_id = message.from_user.id
    user = await get_or_create_user(session, user_id, message.from_user.full_name, message.from_user.username)
    if not user: await message.answer("Ошибка профиля."); return

    # Ищем все задачи со статусом pending без фильтра по дате
    await find_and_reply(message, session, user, 'pending', None, None, "Все активные задачи")