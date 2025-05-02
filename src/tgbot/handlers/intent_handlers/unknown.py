# src/tgbot/handlers/intent_handlers/unknown.py
import logging
from aiogram import types

logger = logging.getLogger(__name__)

async def handle_unknown_intent(message: types.Message):
    """
    Обрабатывает случаи, когда LLM не смогла определить намерение пользователя.
    Можно ничего не отвечать или дать общий ответ.
    """
    user_telegram_id = message.from_user.id
    user_text = message.text
    logger.info(f"Unknown intent detected for user {user_telegram_id}. Text: '{user_text[:100]}...'")

    # Вариант 1: Ничего не отвечать
    pass

    # Вариант 2: Ответить вежливо
    # await message.reply(
    #     "Хм, я не совсем понял ваш запрос. 🤔\n"
    #     "Я умею добавлять задачи (просто напишите ее) и скоро научусь их искать."
    # )

async def handle_error_intent(message: types.Message, llm_result: dict):
    """
    Обрабатывает случаи, когда LLM вернула статус 'error'.
    Информирует пользователя об ошибке.
    """
    user_telegram_id = message.from_user.id
    error_msg = llm_result.get("message", "Произошла внутренняя ошибка.")
    logger.error(f"LLM processing error intent for user {user_telegram_id}. Message: {error_msg}. Details: {llm_result}")

    # Отвечаем пользователю
    await message.reply(
        f"😕 При обработке вашего запроса ИИ-помощником произошла ошибка:\n"
        f"<i>{error_msg}</i>\n\n"
        "Пожалуйста, попробуйте переформулировать или повторите запрос позже."
    )