# src/utils/rrule_helper.py

import logging
from datetime import datetime
from typing import Optional
import pendulum
from dateutil import rrule
from dateutil.rrule import rrulestr

logger = logging.getLogger(__name__)


def calculate_next_reminder_time(
    current_reminder: datetime, 
    rrule_string: str,
    timezone: str = "UTC"
) -> Optional[datetime]:
    """
    Вычисляет следующее время напоминания на основе RRULE.
    
    Args:
        current_reminder: Текущее время напоминания (UTC)
        rrule_string: RRULE строка (например, "FREQ=WEEKLY;BYDAY=MO")
        timezone: Часовой пояс пользователя для расчетов
        
    Returns:
        Следующее время напоминания в UTC или None при ошибке
    """
    try:
        # Конвертируем текущее время в пользовательскую зону
        current_local = pendulum.instance(current_reminder).in_timezone(timezone)
        
        # Создаем полную RRULE строку
        full_rrule = f"DTSTART:{current_local.format('YYYYMMDD[T]HHmmss')}\nRRULE:{rrule_string}"
        
        logger.debug(f"Calculating next reminder with RRULE: {full_rrule}")
        
        # Парсим RRULE  
        rule = rrulestr(full_rrule, dtstart=current_local.naive())
        
        # Находим следующее вхождение после текущего времени
        next_occurrence = rule.after(current_local.naive())
        
        if next_occurrence:
            # Конвертируем обратно в UTC через pendulum
            next_local = pendulum.instance(next_occurrence, tz=timezone)
            next_utc = next_local.in_timezone("UTC")
            
            logger.info(f"Next reminder calculated: {next_utc} (from {current_reminder})")
            return next_utc
        else:
            logger.warning(f"No next occurrence found for RRULE: {rrule_string}")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating next reminder time: {e}", exc_info=True)
        return None


def validate_rrule(rrule_string: str) -> bool:
    """
    Проверяет корректность RRULE строки.
    
    Args:
        rrule_string: RRULE строка для проверки
        
    Returns:
        True если RRULE корректный, False иначе
    """
    try:
        # Пробуем создать простой RRULE для валидации
        test_dtstart = datetime(2025, 1, 1, 12, 0, 0)
        full_rrule = f"DTSTART:20250101T120000\nRRULE:{rrule_string}"
        rule = rrulestr(full_rrule, dtstart=test_dtstart)
        
        # Пробуем получить первое вхождение
        first = rule[0] if rule else None
        return first is not None
        
    except Exception as e:
        logger.error(f"Invalid RRULE: {rrule_string}, error: {e}")
        return False


# Примеры использования для тестирования
if __name__ == "__main__":
    # Тестовые случаи
    test_cases = [
        ("FREQ=WEEKLY;BYDAY=MO", "каждый понедельник"),
        ("FREQ=MONTHLY;BYMONTHDAY=15", "15 числа каждого месяца"),
        ("FREQ=YEARLY;BYMONTH=6;BYMONTHDAY=1", "1 июня каждый год"),
        ("FREQ=DAILY", "каждый день"),
        ("FREQ=WEEKLY", "каждую неделю")
    ]
    
    current_time = pendulum.now("UTC")
    
    for rrule_str, description in test_cases:
        print(f"\nТест: {description}")
        print(f"RRULE: {rrule_str}")
        print(f"Текущее время: {current_time}")
        
        next_time = calculate_next_reminder_time(
            current_time, 
            rrule_str,
            "Europe/Moscow"
        )
        
        if next_time:
            next_pendulum = pendulum.instance(next_time)
            print(f"Следующее напоминание: {next_pendulum} UTC")
            print(f"В московском времени: {next_pendulum.in_timezone('Europe/Moscow')}")
        else:
            print("Ошибка расчета")