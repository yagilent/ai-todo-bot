# src/utils/formatters.py
import logging
import pendulum
from typing import List, Optional
import datetime

# Импортируем модель Task ИЗ models, а не через относительный путь
from src.database.models import Task

logger = logging.getLogger(__name__)

def format_datetime_human(
    date: Optional[datetime.date],
    date_time: Optional[datetime.datetime], # UTC
    has_time: bool,
    timezone: str
    ) -> Optional[str]:
    """
    Форматирует дату или дату+время в человекочитаемый формат.
    """
    base_dt_obj = date_time if has_time else date
    if not base_dt_obj:
        return None

    try:
        dt_local: pendulum.DateTime = None # Переменная для локального времени

        # --- ИСПРАВЛЕНИЕ: Обработка date и datetime ---
        if has_time and isinstance(base_dt_obj, datetime.datetime):
            # Если есть время и это datetime (из due_datetime), конвертируем из UTC
            dt_local = pendulum.instance(base_dt_obj).in_timezone(timezone)
        elif not has_time and isinstance(base_dt_obj, datetime.date):
            # Если времени нет и это date (из due_date), создаем datetime с 00:00 в ЛОКАЛЬНОЙ зоне
            dt_local = pendulum.datetime(
                base_dt_obj.year, base_dt_obj.month, base_dt_obj.day,
                tz=timezone # Сразу указываем зону пользователя
            )
        else:
            # Неожиданный тип или несоответствие has_time и типа данных
            logger.warning(f"Unexpected data type or mismatch for formatting: "
                           f"has_time={has_time}, type={type(base_dt_obj)}")
            # Попробуем универсальный instance, но он может дать не то время для date
            dt_local = pendulum.instance(base_dt_obj).in_timezone(timezone)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        now_local = pendulum.now(timezone)
        date_str = ""
        time_str = ""

        # 1. Форматируем ДАТУ
        if dt_local.is_same_day(now_local): date_str = "сегодня"
        elif dt_local.is_same_day(now_local.add(days=1)): date_str = "завтра"
        elif dt_local.is_same_day(now_local.subtract(days=1)): date_str = "вчера"
        else:
            if now_local.start_of('week') <= dt_local <= now_local.end_of('week').add(weeks=1):
                try:
                    with pendulum.locale('ru'): day_name = dt_local.format("dddd").capitalize()
                    if not dt_local.is_same_week(now_local): date_str = f"{day_name}, {dt_local.format('D MMM')}"
                    else: date_str = day_name
                except Exception: date_str = dt_local.format("ddd, DD.MM")
            else: date_str = dt_local.format("D MMMM YYYY", locale='ru')

        # 2. Форматируем ВРЕМЯ (только если has_time == True)
        if has_time:
            # Проверяем, что время не полночь (на всякий случай)
            if dt_local.time() != pendulum.Time(0, 0, 0):
                 time_str = dt_local.format(" [в] HH:mm")

        result_str = f"{date_str}{time_str}"
        return result_str.strip()

    except Exception as e:
        logger.error(f"Error formatting date/datetime {base_dt_obj}: {e}", exc_info=True)
        # Запасной вариант
        if has_time and due_datetime_obj:
             return f"{due_datetime_obj.strftime('%Y-%m-%d %H:%M')} UTC (ошибка)"
        elif due_date_obj:
             return f"{due_date_obj.strftime('%Y-%m-%d')} (ошибка)"
        else:
             return "(ошибка даты)"

def format_task_list(tasks: List[Task], timezone: str, criteria_text: Optional[str] = None) -> str:
    """Форматирует ТЕКСТОВУЮ часть списка задач."""
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

        # Форматируем срок с помощью утилиты
        formatted_due = format_datetime_human(
            date=task.due_date,       # Передаем date
            date_time=task.due_datetime, # Передаем datetime
            has_time=task.has_time,           # Передаем флаг
            timezone=timezone
        )
        if formatted_due:
            line += f" (<i>срок: {formatted_due}</i>)"

        # НЕ выводим ID здесь
        #response_lines.append(line)

    # Убираем подсказку про нажатие, т.к. пока нет функционала
    # if tasks:
    #     response_lines.append("\n\nНажмите на задачу, чтобы отметить/вернуть.")

    return "\n".join(response_lines)