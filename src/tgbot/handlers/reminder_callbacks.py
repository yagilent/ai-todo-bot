# src/tgbot/handlers/reminder_callbacks.py

import logging
import pendulum
from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_or_create_user, update_task_status, update_task_reminder_time
from src.tgbot.keyboards.inline import (
    REMINDER_COMPLETE_PREFIX,
    REMINDER_SNOOZE_HOUR_PREFIX, 
    REMINDER_SNOOZE_TOMORROW_PREFIX
)

logger = logging.getLogger(__name__)
reminder_callbacks_router = Router(name="reminder_callbacks")


@reminder_callbacks_router.callback_query(F.data.startswith(REMINDER_COMPLETE_PREFIX))
async def handle_reminder_complete(callback: types.CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Сделано' в уведомлении."""
    try:
        # Извлекаем ID задачи из callback_data
        task_id = int(callback.data.replace(REMINDER_COMPLETE_PREFIX, ""))
        
        user = await get_or_create_user(
            session, 
            callback.from_user.id, 
            callback.from_user.full_name, 
            callback.from_user.username
        )
        
        if not user:
            await callback.answer("Ошибка получения профиля пользователя", show_alert=True)
            return

        # Отмечаем задачу как выполненную
        updated_task = await update_task_status(session, task_id, 'done')
        success = updated_task is not None
        
        if success:
            # Редактируем сообщение, убираем кнопки
            # Добавляем статус в начало, ID остается в конце
            new_text = "✅ <b>ЗАДАЧА ВЫПОЛНЕНА</b>\n\n" + callback.message.text
            await callback.message.edit_text(
                text=new_text,
                reply_markup=None,  # Убираем кнопки
                parse_mode="HTML"
            )
            await callback.answer("Задача отмечена как выполненная! 🎉")
            logger.info(f"Task {task_id} marked as complete by user {user.telegram_id}")
        else:
            await callback.answer("Не удалось отметить задачу как выполненную", show_alert=True)
            
    except ValueError:
        await callback.answer("Ошибка обработки ID задачи", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling reminder complete callback: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@reminder_callbacks_router.callback_query(F.data.startswith(REMINDER_SNOOZE_HOUR_PREFIX))
async def handle_reminder_snooze_hour(callback: types.CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Напомни через час'."""
    try:
        task_id = int(callback.data.replace(REMINDER_SNOOZE_HOUR_PREFIX, ""))
        
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name,
            callback.from_user.username
        )
        
        if not user:
            await callback.answer("Ошибка получения профиля пользователя", show_alert=True)
            return

        # Вычисляем время через час в пользовательской зоне
        now_local = pendulum.now(user.timezone)
        reminder_time = now_local.add(hours=1).in_timezone('UTC')
        
        # Обновляем время напоминания
        updated_task = await update_task_reminder_time(session, task_id, reminder_time)
        success = updated_task is not None
        
        if success:
            # Редактируем сообщение, добавляем статус в начало
            status_text = f"⏰ <b>Напомню через час</b> ({now_local.add(hours=1).format('HH:mm')})"
            new_text = status_text + "\n\n" + callback.message.text
            await callback.message.edit_text(
                text=new_text,
                reply_markup=None,
                parse_mode="HTML"
            )
            await callback.answer("Напомню через час! ⏰")
            logger.info(f"Task {task_id} rescheduled for 1 hour by user {user.telegram_id}")
        else:
            await callback.answer("Не удалось перенести напоминание", show_alert=True)
            
    except ValueError:
        await callback.answer("Ошибка обработки ID задачи", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling reminder snooze hour callback: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@reminder_callbacks_router.callback_query(F.data.startswith(REMINDER_SNOOZE_TOMORROW_PREFIX))
async def handle_reminder_snooze_tomorrow(callback: types.CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Напомни завтра'."""
    try:
        task_id = int(callback.data.replace(REMINDER_SNOOZE_TOMORROW_PREFIX, ""))
        
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name,
            callback.from_user.username
        )
        
        if not user:
            await callback.answer("Ошибка получения профиля пользователя", show_alert=True)
            return

        # Вычисляем время завтра в то же время в пользовательской зоне
        now_local = pendulum.now(user.timezone)
        reminder_time = now_local.add(days=1).in_timezone('UTC')
        
        # Обновляем время напоминания
        updated_task = await update_task_reminder_time(session, task_id, reminder_time)
        success = updated_task is not None
        
        if success:
            # Редактируем сообщение, добавляем статус в начало
            tomorrow_time = now_local.add(days=1).format('DD.MM в HH:mm')
            status_text = f"📅 <b>Напомню завтра</b> ({tomorrow_time})"
            new_text = status_text + "\n\n" + callback.message.text
            await callback.message.edit_text(
                text=new_text,
                reply_markup=None,
                parse_mode="HTML"
            )
            await callback.answer("Напомню завтра! 📅")
            logger.info(f"Task {task_id} rescheduled for tomorrow by user {user.telegram_id}")
        else:
            await callback.answer("Не удалось перенести напоминание", show_alert=True)
            
    except ValueError:
        await callback.answer("Ошибка обработки ID задачи", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling reminder snooze tomorrow callback: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)