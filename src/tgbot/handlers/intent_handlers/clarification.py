# src/tgbot/handlers/intent_handlers/clarification.py
import logging
from aiogram import types
# Убираем импорт FSMContext
# from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

async def handle_clarification_request(
    message: types.Message,
    # Убираем state: FSMContext,
    llm_result: dict
):
    """Обрабатывает ответ LLM, требующий уточнения. Просто задает вопрос."""
    question = llm_result.get("question", "Не могли бы вы уточнить детали?")
    intent_being_processed = llm_result.get("intent", "unknown")
    logger.info(f"Clarification needed for user {message.from_user.id}. Intent: {intent_being_processed}. Question: '{question}'")

    # --- УБИРАЕМ ЛОГИКУ FSM ---

    # Просто задаем вопрос пользователю
    await message.reply(f"🤔 {question}")
    # Следующий ответ пользователя будет обработан заново через nlp_handler