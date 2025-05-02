# src/tgbot/responses.py

import logging
from typing import Optional
from aiogram import types, Bot
import pendulum # Для форматирования дат

# Импортируем модели для тайп-хинтов
from src.database.models import Task, User

from src.utils.formatters import format_datetime_human

logger = logging.getLogger(__name__)

# --- НОВАЯ Функция Подтверждения Действий с Задачей ---
async def send_task_operation_confirmation(
    message: types.Message,
    action_title: str, # Что было сделано: "Задача добавлена", "Срок изменен" и т.д.
    task: Task, # Объект задачи (уже обновленный или новый)
    user: User # Объект пользователя (нужен для таймзоны)
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



    due_date_value = task.due_datetime if task.has_time else task.due_date
    is_overdue = False # Флаг просрочки
    date_time_text = ""

    if due_date_value:
        formatted_due = format_datetime_human(
            date=task.due_date,
            date_time=task.due_datetime,
            has_time=task.has_time,
            timezone=user_timezone
        )

        if formatted_due:
            # --- ПРОВЕРКА НА ПРОСРОЧКУ ---
            try:
                now_local = pendulum.now(user_timezone)
                due_moment_local: pendulum.DateTime = None

                if task.has_time and task.due_datetime:
                    # Для datetime сравниваем с текущим моментом
                    due_moment_local = pendulum.instance(task.due_datetime).in_timezone(user_timezone)
                    if due_moment_local < now_local:
                         is_overdue = True
                elif not task.has_time and task.due_date:
                     # Для date сравниваем только дату (считаем просроченным, если сегодня уже ПОСЛЕ этой даты)
                     date_local = pendulum.Date(task.due_date.year, task.due_date.month, task.due_date.day)
                     if date_local < now_local.date():
                          is_overdue = True

                if is_overdue:
                    logger.debug(f"Task {task.task_id} is overdue. Due: {due_moment_local or date_local}, Now: {now_local}")
            except Exception as e:
                 logger.error(f"Error checking overdue status for task {task.task_id}: {e}")
            # --- КОНЕЦ ПРОВЕРКИ НА ПРОСРОЧКУ ---

            # Добавляем строку с форматированием
            due_prefix = "❗️<b>Срок ИСТЕК:</b>" if is_overdue else "📅 " # Добавим жирность к префиксу
            # Применяем ТОЛЬКО жирность, если просрочено
            formatted_string = f'<b>{formatted_due}</b>' if is_overdue else formatted_due
            date_time_text = f"\n{due_prefix} {formatted_string}"

    
    # Добавляем информацию о напоминании
    if task.next_reminder_at:
        formatted_reminder = format_datetime_human(None, task.next_reminder_at, True, user_timezone)
        if formatted_reminder:
            date_time_text += f" 🔔 {formatted_reminder}"

    
    response_lines.append(date_time_text)
    # Всегда добавляем ID
    response_lines.append(f"(ID: {task.task_id})")

    response_text = "\n".join(response_lines)

    # Отправляем ответ на исходное сообщение пользователя
    try:
        await message.answer(response_text)
    except Exception as e:
        # Ловим возможные ошибки отправки (например, сообщение удалено)
        logger.error(f"Failed to send task confirmation reply to user {message.from_user.id}: {e}")
        # Пытаемся отправить обычное сообщение
        try:
            await message.answer(response_text)
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

    # Форматируем срок
    formatted_due = format_datetime_human(
        date=task.due_date,
        date_time=task.due_datetime,
        has_time=task.has_time,
        timezone=user_timezone
    )
    if formatted_due:
        reminder_lines.append(f"\n📅 Срок: {formatted_due}")

    reminder_lines.append(f"\n\n(ID: {task.task_id})") # ID для возможного реплая
    reminder_text = "\n".join(reminder_lines)

    # TODO: Создать и добавить инлайн-кнопки ("Сделано", "Отложить...")
    # keyboard = create_reminder_keyboard(task.task_id)
    keyboard = None # Пока без кнопок

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