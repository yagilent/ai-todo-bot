# src/tgbot/handlers/intent_handlers/find_tasks.py
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
import pendulum # Для форматирования
import json # Для сериализации задач в JSON

# Импорты
from src.database.models import User, Task
# Импортируем НОВЫЕ CRUD функции
from src.database.crud import get_all_user_tasks, get_tasks_by_ids
# Импортируем НОВУЮ LLM функцию
from src.llm.gemini_client import find_tasks_with_llm

# Импортируем форматирование списка
from src.utils.formatters import format_task_list
from src.tgbot.keyboards.inline import create_tasks_keyboard

from typing import Optional

logger = logging.getLogger(__name__)

async def handle_find_tasks(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict # Содержит query_text
):
    """
    Обрабатывает намерение найти задачи, используя LLM для фильтрации
    всего списка задач пользователя.
    """
    query_text = params.get("query_text", "")
    user_telegram_id = db_user.telegram_id
    user_timezone = db_user.timezone

    if not query_text:
        await message.reply("Уточните, какие задачи вы ищете.")
        return

    logger.info(f"Handling find_tasks intent via LLM context search for user {user_telegram_id}. Query: '{query_text}'")

    try:
        # 1. Получаем все (или активные) задачи пользователя из БД
        # TODO: Решить, передавать все или только pending в LLM? Начнем с pending.
        all_user_tasks = await get_all_user_tasks(session, user_telegram_id, only_pending=True)

        if not all_user_tasks:
            await message.reply("У вас пока нет активных задач для поиска.")
            return

        # 2. Форматируем задачи для LLM
        tasks_for_llm = []
        for task in all_user_tasks:

            due_date_iso_str: Optional[str] = None # Явно строка или None

            if task.has_time and task.due_datetime:
                try:
                    # Конвертируем datetime UTC в строку ISO 8601
                    due_date_iso_str = pendulum.instance(task.due_datetime).to_iso8601_string()
                except Exception as e:
                     logger.error(f"Error converting due_datetime {task.due_datetime} to ISO string: {e}")
                     # Оставляем None в случае ошибки
            elif not task.has_time and task.due_date:
                try:
                    # Конвертируем date в строку ISO 8601 (YYYY-MM-DD)
                    due_date_iso_str = task.due_date.isoformat()
                except Exception as e:
                    logger.error(f"Error converting due_date {task.due_date} to ISO string: {e}")
                    # Оставляем None


            tasks_for_llm.append({
                "id": task.task_id,
                "description": task.description,
                "title": task.title,
                "status": task.status,
                "due_date_utc_iso": due_date_iso_str
            })

        # 3. Вызываем LLM для поиска по контексту
        matching_ids = await find_tasks_with_llm(query_text, tasks_for_llm)

        if matching_ids is None: # Ошибка LLM
            await message.reply("Не удалось обработать поисковый запрос с помощью ИИ. Попробуйте позже.")
            return

        if not matching_ids: # LLM не нашла совпадений
            await message.reply("Не нашел задач, соответствующих вашему запросу.")
            return

        # 4. Получаем найденные задачи из БД по ID
        found_tasks = await get_tasks_by_ids(session, user_telegram_id, matching_ids)

        # 5. Форматируем и отправляем результат
        response_text = format_task_list(found_tasks, user_timezone, criteria_text=query_text)
        keyboard = create_tasks_keyboard(found_tasks, db_user)
        
        await message.answer(response_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error during LLM-based task search for user {user_telegram_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка во время поиска задач.")