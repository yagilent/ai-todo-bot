# src/tgbot/handlers/nlp_handler.py

import logging
from typing import Optional
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты
from src.llm.gemini_client import process_user_input
from src.database.crud import get_or_create_user
from src.utils.parsers import extract_task_id_from_text

# Импортируем функции-обработчики для каждого интента
from .intent_handlers import (
    handle_add_task,
    handle_find_tasks,
    handle_update_timezone,
    handle_complete_task,
    handle_reschedule_task,
    handle_edit_task_description,
    handle_snooze_task,
    handle_clarification_request,
    handle_unknown_intent,
    handle_error_intent
)

logger = logging.getLogger(__name__)
nlp_router = Router(name="nlp_handlers")

# Контекстные интенты, требующие ID задачи
CONTEXTUAL_INTENTS = {
    "complete_task",
    "reschedule_task",
    "edit_task_description",
    "snooze_task",
}

@nlp_router.message(F.text, ~F.text.startswith('/'))
async def handle_natural_language_query(
    message: types.Message,
    state: FSMContext, # Контекст FSM (пока не используется активно для этого хендлера)
    session: AsyncSession # Инжектируется middleware
):
    """
    Основной обработчик текста: определяет намерение, извлекает контекст (task_id из реплая)
    и передает управление специализированным функциям.
    """
    user = message.from_user
    user_telegram_id = user.id
    user_text = message.text
    context_task_id: Optional[int] = None # ID задачи из контекста реплая

    logger.info(f"Processing NLP query from user {user_telegram_id}. Text: '{user_text[:100]}...'")

    try:
        # Проверка на реплай и извлечение ID
        if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            replied_text = message.reply_to_message.text or message.reply_to_message.caption
            context_task_id = extract_task_id_from_text(replied_text)
            if context_task_id:
                logger.info(f"Detected reply context with task_id: {context_task_id}")
            else:
                logger.debug("Reply detected, but no task ID found.")

        # Получаем/создаем пользователя (нужен для контекста и ID)
        db_user = await get_or_create_user(session, user_telegram_id, user.full_name, user.username)
        if not db_user:
            logger.error(f"Failed to get or create user {user_telegram_id} in NLP handler.")
            await message.reply("Не удалось обработать ваш профиль. Пожалуйста, попробуйте выполнить команду /start.")
            return

        # Вызов LLM для определения намерения (с новыми параметрами)
        is_reply = context_task_id is not None
        user_timezone = db_user.timezone if db_user.timezone else "Europe/Moscow"
        llm_result = await process_user_input(user_text, is_reply=is_reply, user_timezone=user_timezone)
        logger.debug(f"LLM intent result for user {user_telegram_id}: {llm_result}")

        status = llm_result.get("status")
        intent = llm_result.get("intent")
        params = llm_result.get("params", {})

        # Диспетчеризация по результату LLM
        if status == "success":
            # Обработка контекстных интентов
            if intent in CONTEXTUAL_INTENTS:
                if context_task_id:
                    # Вызываем соответствующий обработчик, передавая ID
                    if intent == "complete_task":
                        await handle_complete_task(message, session, db_user, context_task_id)
                    elif intent == "reschedule_task":
                        await handle_reschedule_task(message, session, db_user, params, context_task_id)
                    elif intent == "edit_task_description":
                        await handle_edit_task_description(message, session, db_user, params, context_task_id)
                    elif intent == "snooze_task":
                        await handle_snooze_task(message, session, db_user, params, context_task_id)
                    # Добавить другие контекстные интенты здесь, если появятся
                else:
                    # Интент требует контекста, но его нет
                    logger.warning(f"Contextual intent '{intent}' received without valid reply/task_id for user {user_telegram_id}")
                    await message.reply(
                        "Пожалуйста, используйте функцию 'Ответить' (Reply) на сообщении с задачей (у него должен быть ID в скобках), "
                        "чтобы я понял, к какой именно задаче применить команду."
                    )
            # Обработка неконтекстных интентов
            elif intent == "add_task":
                # Передаем state, т.к. этот хендлер может инициировать FSM для таймзоны
                await handle_add_task(message, session, db_user, params)
            elif intent == "find_tasks":
                await handle_find_tasks(message, session, db_user, params)
            elif intent == "update_timezone":
                await handle_update_timezone(message, session, db_user, params)
            else:
                # Успешный статус, но неизвестный интент
                logger.warning(f"LLM success with unknown intent: {intent}")
                await handle_unknown_intent(message) # Передаем управление обработчику неизвестных

        elif status == "clarification_needed":
             # Передаем state, т.к. этот обработчик точно работает с FSM
            await handle_clarification_request(message, llm_result)

        elif status == "unknown_intent":
            await handle_unknown_intent(message)
        elif status == "error":
            await handle_error_intent(message, llm_result)
        else:
            logger.error(f"Unexpected LLM status: {status}")
            await message.reply("Произошла неожиданная ошибка при обработке вашего запроса.")

    except Exception as e:
        logger.exception(f"General error in handle_natural_language_query for user {user_telegram_id}")
        await message.reply("💥 Ой! Что-то пошло не так при обработке вашего сообщения.")