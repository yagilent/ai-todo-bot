# src/tgbot/handlers/task_manage.py
import logging
from aiogram import Router, types, F, Bot
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты
from src.database.crud import get_task_by_id, get_user_by_telegram_id
# Импортируем функцию ответа
from src.tgbot import responses
# Импортируем префикс из клавиатур
from src.tgbot.keyboards.inline import TASK_VIEW_PREFIX

logger = logging.getLogger(__name__)
# Создаем новый роутер для управления задачами (колбэки, команды управления)
task_manage_router = Router(name="task_manage_handlers")

@task_manage_router.callback_query(F.data.startswith(TASK_VIEW_PREFIX))
async def handle_view_task_callback(
    callback_query: types.CallbackQuery,
    session: AsyncSession,
    # bot: Bot # Bot объект не нужен, если используем message.answer
):
    """Обрабатывает нажатие на кнопку задачи для показа деталей."""
    user_telegram_id = callback_query.from_user.id
    message = callback_query.message # Сообщение, К КОТОРОМУ прикреплена клавиатура

    try:
        # Извлекаем ID задачи
        task_id_str = callback_query.data[len(TASK_VIEW_PREFIX):]
        task_id = int(task_id_str)
    except (IndexError, ValueError):
         logger.error(f"Invalid callback_data for view task: {callback_query.data}")
         await callback_query.answer("Ошибка: Неверный ID задачи.", show_alert=True)
         return

    logger.info(f"Handling view task callback for task {task_id} by user {user_telegram_id}")

    try:
        # Получаем задачу и пользователя
        task = await get_task_by_id(session, task_id)
        db_user = await get_user_by_telegram_id(session, user_telegram_id)

        if not task:
             logger.warning(f"Task {task_id} not found in DB for view.")
             await callback_query.answer("Задача не найдена.", show_alert=True)
             # Можно попробовать убрать клавиатуру у старого сообщения
             try: await message.edit_reply_markup(reply_markup=None)
             except Exception: pass
             return
        if not db_user: # Маловероятно
             logger.error(f"User {user_telegram_id} not found for view task.")
             await callback_query.answer("Ошибка профиля пользователя.", show_alert=True)
             return
        if task.user_telegram_id != user_telegram_id:
             logger.warning(f"User {user_telegram_id} tried to view task {task_id} of another user.")
             await callback_query.answer("Это не ваша задача.", show_alert=True)
             return

        # Используем функцию из responses для отправки деталей
        # Отправляем как НОВОЕ сообщение, а не редактируем список
        await responses.send_task_operation_confirmation(
            message=message, # Используем message для отправки в тот же чат
            action_title="", # Заголовок для сообщения
            task=task,
            user=db_user,
            include_action_buttons=True  # Добавляем кнопки действий к просмотру задач
        )

        # Просто отвечаем на колбэк, чтобы убрать "часики"
        await callback_query.answer()

    except Exception as e:
         logger.error(f"Error handling view_task callback for task {task_id}: {e}", exc_info=True)
         await callback_query.answer("Произошла ошибка при показе задачи.", show_alert=True)