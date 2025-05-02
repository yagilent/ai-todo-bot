# src/tgbot/handlers/intent_handlers/complete_task.py
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import update_task_status, get_task_by_id # Нужны обе функции
from src.database.models import User

logger = logging.getLogger(__name__)

async def handle_complete_task(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    task_id: int # ID задачи из контекста реплая
):
    """Обрабатывает намерение пометить задачу как выполненную."""
    logger.info(f"Handling complete_task intent for user {db_user.telegram_id}, task_id: {task_id}")

    try:
        # Получаем задачу, чтобы убедиться, что она принадлежит пользователю
        task = await get_task_by_id(session, task_id)

        if not task:
            await message.reply("Не нашел задачу с таким ID.")
            return
        if task.user_telegram_id != db_user.telegram_id:
             logger.warning(f"User {db_user.telegram_id} tried to complete task {task_id} belonging to user {task.user_telegram_id}")
             await message.reply("Похоже, эта задача не ваша.")
             return
        if task.status == 'done':
             await message.reply("Эта задача уже отмечена как выполненная.")
             return

        # Обновляем статус
        updated_task = await update_task_status(session, task_id, new_status='done')

        if updated_task:
            await message.reply(f"✅ Отлично! Задача '{updated_task.description[:50]}...' отмечена как выполненная.")
        else:
            # update_task_status сама логирует ошибку
            await message.reply("Не удалось обновить статус задачи.")

    except Exception as e:
        logger.error(f"Error handling complete_task for user {db_user.telegram_id}, task {task_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при отметке задачи.")