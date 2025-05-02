# src/tgbot/keyboards/inline.py
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.models import Task, User

from src.utils.formatters import format_datetime_human

# --- ИЗМЕНЕНИЕ: Пока не нужен префикс для обработчика ---
# TASK_STATUS_TOGGLE_PREFIX = "toggle_status:"
# Вместо этого используем заглушку callback_data
TASK_BUTTON_CALLBACK_DUMMY = "task_button_pressed" # Или просто ID: f"task:{task.task_id}"

TASK_VIEW_PREFIX = "view_task:"

def create_tasks_keyboard(tasks: List[Task], db_user: User) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру со списком задач и визуальными чекбоксами.
    Callback_data пока не несет реальной нагрузки.
    """
    builder = InlineKeyboardBuilder()

    if not tasks:
         return builder.as_markup()

    for task in tasks:
        # Определяем иконку чекбокса
        status_icon = "✅" if task.status == 'done' else "☐"

        # Формируем текст кнопки (описание или заголовок)
        # Используем описание, обрезаем если длинное

        task_title = ""
        if task.title:
            task_title = task.title
        else:
            task_title = task.description[:30]

        task_date_time_text = ""

        due_datetime = format_datetime_human(task.due_date, task.due_datetime, task.has_time, db_user.timezone)
        notification_datetime = format_datetime_human(None, task.next_reminder_at, True, db_user.timezone)

        if (task.status == 'done'):
            task_date_time_text = "✅"
        elif (task.has_time and due_datetime):
            task_date_time_text = "⏱️" + due_datetime
        elif (not notification_datetime and not task.has_time and due_datetime):
            task_date_time_text = "🗓" + due_datetime +" 🔕"
        elif (notification_datetime):
            task_date_time_text = "🔔" + notification_datetime

        
        button_text = f"{task_title} {task_date_time_text}"
        
        # Или можно использовать заголовок, если он есть:
        # text_part = task.title if task.title else task.description
        # text_part_short = text_part[:40] + ("..." if len(text_part) > 40 else "")
        # button_text = f"{status_icon} {text_part_short}"


        # --- ИЗМЕНЕНИЕ: Используем временный callback_data ---
        # Просто чтобы кнопка была кликабельной, но обработчик мы не пишем
        # Можно использовать ID, чтобы в будущем было проще добавить логику
        #callback_data = f"task_view:{task.task_id}" # Префикс для просмотра/действия
        callback_data = f"{TASK_VIEW_PREFIX}{task.task_id}"
        # Или общая заглушка:
        # callback_data = TASK_BUTTON_CALLBACK_DUMMY
        # ---------------------------------------------------

        builder.row(InlineKeyboardButton(text=button_text, callback_data=callback_data))

    # TODO: Добавить кнопки пагинации, "Выбрать"

    return builder.as_markup()