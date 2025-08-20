# src/utils/formatters.py
import logging
import pendulum
from typing import List, Optional
import datetime

# Импортируем модель Task ИЗ models, а не через относительный путь
from src.database.models import Task

logger = logging.getLogger(__name__)

def format_reminder_time_human(
    reminder_datetime: Optional[datetime.datetime], # UTC
    timezone: str
    ) -> Optional[str]:
    """
    НОВАЯ УПРОЩЁННАЯ функция - форматирует только время напоминания.
    Время события больше не используется.
    """
    if not reminder_datetime:
        return None

    try:
        # Конвертируем UTC время напоминания в локальную зону
        reminder_local = pendulum.instance(reminder_datetime).in_timezone(timezone)
        now_local = pendulum.now(timezone)
        
        # Форматируем дату
        if reminder_local.is_same_day(now_local): 
            date_str = "сегодня"
        elif reminder_local.is_same_day(now_local.add(days=1)): 
            date_str = "завтра"
        elif reminder_local.is_same_day(now_local.subtract(days=1)): 
            date_str = "вчера"
        else:
            if now_local.start_of('week') <= reminder_local <= now_local.end_of('week').add(weeks=1):
                try:
                    with pendulum.locale('ru'): 
                        day_name = reminder_local.format("dddd").capitalize()
                    if not reminder_local.is_same_week(now_local): 
                        date_str = f"{day_name}, {reminder_local.format('D MMM')}"
                    else: 
                        date_str = day_name
                except Exception: 
                    date_str = reminder_local.format("ddd, DD.MM")
            else: 
                date_str = reminder_local.format("D MMMM YYYY", locale='ru')

        # Добавляем время
        time_str = reminder_local.format(" в HH:mm")
        
        return f"{date_str}{time_str}"

    except Exception as e:
        logger.error(f"Error formatting reminder time {reminder_datetime}: {e}", exc_info=True)
        return f"{reminder_datetime.strftime('%Y-%m-%d %H:%M')} UTC (ошибка)"


# УСТАРЕВШАЯ функция - оставляем для обратной совместимости, но больше не используем
def format_datetime_human(
    date: Optional[datetime.date],
    date_time: Optional[datetime.datetime], # UTC
    has_time: bool,
    timezone: str
    ) -> Optional[str]:
    """
    УСТАРЕВШАЯ функция для форматирования времени события.
    Используйте format_reminder_time_human() для времени напоминания.
    """
    # Теперь просто возвращаем None, так как время события больше не используется
    return None

def format_task_list(tasks: List[Task], timezone: str, criteria_text: Optional[str] = None) -> str:
    """Форматирует ТЕКСТОВУЮ часть списка задач (используется редко, основной интерфейс - кнопки)."""
    if not tasks:
        return "✅ Задач, соответствующих вашему запросу, не найдено."

    title = f"**Задачи по запросу '{criteria_text}':**\n" if criteria_text else "**Ваши задачи:**\n"
    response_lines = [title]

    for task in tasks:
        # НЕ выводим иконку статуса здесь
        description_safe = task.description or 'Без описания'
        title_safe = task.title

        line = "\n• " # Маркер списка
        if title_safe:
            line += f"<b>{title_safe}</b>: "
        line += f"<i>{description_safe}</i>"

        # Показываем время напоминания с правильной иконкой
        if task.next_reminder_at:
            formatted_reminder = format_reminder_time_human(
                reminder_datetime=task.next_reminder_at,
                timezone=timezone
            )
            if formatted_reminder:
                # Проверяем, не прошло ли время напоминания
                try:
                    import pendulum
                    now_local = pendulum.now(timezone)
                    reminder_local = pendulum.instance(task.next_reminder_at).in_timezone(timezone)
                    is_overdue = reminder_local < now_local
                    
                    # Выбираем иконку: перечеркнутый колокольчик если время прошло
                    reminder_icon = "🔕" if is_overdue else "🔔"
                    line += f" ({reminder_icon} <i>{formatted_reminder}</i>)"
                except Exception as e:
                    # Fallback при ошибке
                    line += f" (🔔 <i>{formatted_reminder}</i>)"
                    
        # Показываем RRULE если есть
        if task.recurrence_rule:
            line += f" ({task.recurrence_rule})"

        response_lines.append(line)

    return "\n".join(response_lines)