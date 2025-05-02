# src/tgbot/handlers/intent_handlers/edit_description.py
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import update_task_description, get_task_by_id # Нужны эти функции
from src.database.models import User

from src.tgbot import responses

logger = logging.getLogger(__name__)

async def handle_edit_task_description(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict, # Содержит new_description
    task_id: int
):
    """Обрабатывает намерение изменить описание задачи."""
    new_description = params.get("new_description")
    user_telegram_id = db_user.telegram_id

    if not new_description:
        logger.warning(f"Edit description intent for task {task_id} without new description. User: {user_telegram_id}")
        await message.reply("Не понял, на какой текст изменить описание.")
        return

    logger.info(f"Handling edit_description intent for user {user_telegram_id}, task_id: {task_id}.")

    try:
        # Проверяем задачу
        task = await get_task_by_id(session, task_id)
        if not task:
            await message.reply("Не нашел задачу с таким ID для изменения.")
            return
        if task.user_telegram_id != user_telegram_id:
            await message.reply("Похоже, эта задача не ваша.")
            return

        # TODO: Решить, заменяем текст или добавляем? Пока заменяем.
        # Можно спросить у LLM в промпте intent recognition, что делать (replace/append).
        updated_task = await update_task_description(
            session=session,
            task_id=task_id,
            new_description=new_description
        )

        if updated_task:
             await responses.send_task_operation_confirmation(
                 message=message,
                 action_title="Описание задачи изменено",
                 task=updated_task,
                 user=db_user
             )
        else:
             await message.reply("Не удалось изменить описание задачи.")

    except Exception as e:
        logger.error(f"Error handling edit_description for user {user_telegram_id}, task {task_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при изменении описания.")