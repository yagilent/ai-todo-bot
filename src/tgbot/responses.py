# src/tgbot/responses.py

import logging
from typing import Optional
from aiogram import types, Bot
import pendulum # Для форматирования дат

# Импортируем модели для тайп-хинтов
from src.database.models import Task, User

from src.utils.formatters import format_reminder_time_human
from src.tgbot.keyboards.inline import create_reminder_keyboard, create_task_actions_keyboard

logger = logging.getLogger(__name__)

# --- НОВАЯ Функция Подтверждения Действий с Задачей ---
async def send_task_operation_confirmation(
    message: types.Message,
    action_title: str, # Что было сделано: "Задача добавлена", "Срок изменен" и т.д.
    task: Task, # Объект задачи (уже обновленный или новый)
    user: User, # Объект пользователя (нужен для таймзоны)
    include_action_buttons: bool = False  # Добавить кнопки действий (Сделано, Перенести)
):
    """
    Отправляет унифицированное сообщение о результате операции с задачей.
    """
    user_timezone = user.timezone # Берем таймзону из объекта User

    response_lines = []
    if action_title and action_title != "":
        status_icon = "✅" # Используем галочку для всех успешных операций
        # Собираем сообщение
        response_lines = [
            f"{status_icon} {action_title}"
        ]

    title_to_show = task.title
    desc_to_show =  task.description
    response_lines.append(f"\n<b>{title_to_show}.</b> {desc_to_show}")



    # НОВОЕ: Показываем только время напоминания (время события больше не используется)
    date_time_text = ""
    if task.next_reminder_at:
        formatted_reminder = format_reminder_time_human(
            reminder_datetime=task.next_reminder_at,
            timezone=user_timezone
        )
        if formatted_reminder:
            # Проверяем, не прошло ли время напоминания
            is_overdue = False
            try:
                now_local = pendulum.now(user_timezone)
                reminder_local = pendulum.instance(task.next_reminder_at).in_timezone(user_timezone)
                if reminder_local < now_local:
                    is_overdue = True
            except Exception as e:
                logger.error(f"Error checking reminder overdue status for task {task.task_id}: {e}")
            
            # Добавляем строку с форматированием
            reminder_prefix = "❗️<b>Пропущено:</b>" if is_overdue else "🔔 "
            formatted_string = f'<b>{formatted_reminder}</b>' if is_overdue else formatted_reminder
            date_time_text = f"\n{reminder_prefix}Напоминание: {formatted_string}"

    
    response_lines.append(date_time_text)
    
    # Показываем RRULE если есть
    if task.recurrence_rule:
        response_lines.append(f"({task.recurrence_rule})")
    
    # Всегда добавляем ID
    response_lines.append(f"(ID: {task.task_id})")

    response_text = "\n".join(response_lines)
    
    # Создаем клавиатуру с кнопками если запрошено
    keyboard = None
    if include_action_buttons and task.status == 'pending':  # Кнопки только для активных задач
        keyboard = create_task_actions_keyboard(task.task_id, "view")

    # Отправляем ответ на исходное сообщение пользователя
    try:
        await message.answer(response_text, reply_markup=keyboard)
    except Exception as e:
        # Ловим возможные ошибки отправки (например, сообщение удалено)
        logger.error(f"Failed to send task confirmation reply to user {message.from_user.id}: {e}")
        # Пытаемся отправить обычное сообщение
        try:
            await message.answer(response_text, reply_markup=keyboard)
        except Exception as e2:
             logger.error(f"Failed to send task confirmation answer to user {message.from_user.id}: {e2}")

async def send_reminder_notification(
    bot: Bot, # Принимает объект Bot
    task: Task,
    user: User # Принимает пользователя для таймзоны
    ):
    """
    Формирует и отправляет сообщение-напоминание пользователю.
    """
    user_timezone = user.timezone
    logger.info(f"Sending reminder for task {task.task_id} to user {user.telegram_id}")

    # Формируем текст напоминания
    reminder_lines = ["🔔 **Напоминание!**\n"]
    title_safe = f"<b>{task.title}</b>: " if task.title else ""
    description_safe = task.description or 'Без описания'
    reminder_lines.append(f"\n{title_safe}<i>{description_safe}</i>")

    # НОВОЕ: Показываем только время напоминания (время события больше не используется)
    if task.next_reminder_at:
        formatted_reminder = format_reminder_time_human(
            reminder_datetime=task.next_reminder_at,
            timezone=user_timezone
        )
        if formatted_reminder:
            reminder_lines.append(f"\n🔔 Напоминание было на: {formatted_reminder}")

    reminder_lines.append(f"\n\n(ID: {task.task_id})") # ID для возможного реплая
    reminder_text = "\n".join(reminder_lines)

    # Создаем клавиатуру с кнопками действий
    keyboard = create_reminder_keyboard(task.task_id)

    try:
        # Используем bot.send_message
        await bot.send_message(
            chat_id=user.telegram_id, # Берем ID из объекта user
            text=reminder_text,
            reply_markup=keyboard
            )
        logger.info(f"Successfully sent reminder for task {task.task_id} to user {user.telegram_id}")
        return True # Возвращаем успех
    except Exception as e:
        # TODO: Более детальная обработка ошибок (BotBlocked, UserDeactivated etc.)
        logger.error(f"Failed to send reminder notification for task {task.task_id} to user {user.telegram_id}: {e}")
        return False # Возвращаем неуспех