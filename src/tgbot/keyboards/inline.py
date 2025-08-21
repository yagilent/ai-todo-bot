# src/tgbot/keyboards/inline.py
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.models import Task, User

from src.utils.formatters import format_reminder_time_human

# --- ИЗМЕНЕНИЕ: Пока не нужен префикс для обработчика ---
# TASK_STATUS_TOGGLE_PREFIX = "toggle_status:"
# Вместо этого используем заглушку callback_data
TASK_BUTTON_CALLBACK_DUMMY = "task_button_pressed" # Или просто ID: f"task:{task.task_id}"

TASK_VIEW_PREFIX = "view_task:"

# Префиксы для кнопок напоминаний
REMINDER_COMPLETE_PREFIX = "reminder_complete:"
REMINDER_SNOOZE_HOUR_PREFIX = "reminder_snooze_hour:"  
REMINDER_SNOOZE_TOMORROW_PREFIX = "reminder_snooze_tomorrow:"

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

        # УПРОЩЕНИЕ: Показываем только время напоминания (время события больше не используется)
        if (task.status == 'done'):
            task_date_time_text = "✅"
        elif task.next_reminder_at:
            # Проверяем, не прошло ли время напоминания
            try:
                import pendulum
                now_local = pendulum.now(db_user.timezone)
                reminder_local = pendulum.instance(task.next_reminder_at).in_timezone(db_user.timezone)
                is_overdue = reminder_local < now_local
                
                # Форматируем время напоминания
                notification_datetime = format_reminder_time_human(task.next_reminder_at, db_user.timezone)
                if notification_datetime:
                    # Выбираем иконку: перечеркнутый колокольчик если время прошло
                    reminder_icon = "🔕" if is_overdue else "🔔"
                    task_date_time_text = reminder_icon + notification_datetime
                else:
                    # Если форматирование не удалось, всё равно показываем время с иконкой
                    reminder_icon = "🔕" if is_overdue else "🔔"
                    fallback_time = reminder_local.format("DD.MM HH:mm")
                    task_date_time_text = reminder_icon + fallback_time
            except Exception:
                # Fallback при любой ошибке - показываем хотя бы время напоминания
                try:
                    fallback_time = task.next_reminder_at.strftime("%d.%m %H:%M")
                    task_date_time_text = "🔔" + fallback_time
                except Exception:
                    task_date_time_text = "🔔"
        else:
            # Нет времени напоминания - показываем перечеркнутый колокольчик
            task_date_time_text = "🔕"
        
        # Добавляем иконку повторения если есть RRULE
        repeat_icon = "🔄" if task.recurrence_rule else ""
        
        button_text = f"{task_title} {task_date_time_text}{repeat_icon}"
        
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


def create_task_actions_keyboard(task_id: int, context: str = "reminder") -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с действиями для задачи.
    
    Args:
        task_id: ID задачи для которой создается клавиатура
        context: Контекст использования ("reminder" или "view")
        
    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Сделано" - отмечает задачу как выполненную
    builder.row(InlineKeyboardButton(
        text="✅ Сделано",
        callback_data=f"{REMINDER_COMPLETE_PREFIX}{task_id}"
    ))
    
    # Кнопка "Напомни через час"
    builder.row(InlineKeyboardButton(
        text="⏰ Напомни через час",
        callback_data=f"{REMINDER_SNOOZE_HOUR_PREFIX}{task_id}"
    ))
    
    # Кнопка "Напомни завтра"
    builder.row(InlineKeyboardButton(
        text="📅 Напомни завтра",
        callback_data=f"{REMINDER_SNOOZE_TOMORROW_PREFIX}{task_id}"
    ))
    
    return builder.as_markup()


def create_reminder_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для уведомления о задаче.
    Обертка для обратной совместимости.
    """
    return create_task_actions_keyboard(task_id, "reminder")