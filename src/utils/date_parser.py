# src/utils/date_parser.py

import logging
from typing import Optional, Dict, Any
import pendulum
import datetime

# Импортируем LLM функцию
try:
    from src.llm.gemini_client import process_date_text_with_llm
except ImportError:
    logging.error("Could not import LLM client for date parsing!")
    process_date_text_with_llm = None

logger = logging.getLogger(__name__)

async def text_to_datetime_obj(text_date: Optional[str], user_timezone: str = 'UTC') -> Dict[str, Any]:
    """
    Парсит дату/время/повторение.
    Возвращает словарь с:
        'date': datetime.date | None
        'date_time': datetime.datetime | None (в UTC)
        'has_time': bool
        'is_repeating': bool
        'rrule': str | None
    """
    if not text_date:
        return {'has_time': False, 'is_repeating': False} # Возвращаем пустой словарь, но с флагами

    cleaned_text = text_date.strip()
    date: Optional[datetime.date] = None
    date_time: Optional[datetime.datetime] = None
    has_time = False
    is_repeating = False # пока не используется
    rrule = None  # пока не используется

    if process_date_text_with_llm:
        llm_result = await process_date_text_with_llm(cleaned_text, user_timezone)
        if llm_result:
            iso_date_str = llm_result.get("date_utc_iso")
            has_time = llm_result.get("has_time", False)
            rrule = llm_result.get("recurrence_rule") # пока не используется

            if iso_date_str:
                try:
                    dt_utc_from_llm = pendulum.parse(iso_date_str).in_timezone('UTC')
                    if has_time:
                        date_time = dt_utc_from_llm # Сохраняем только datetime
                        date = None
                    else:
                        date_time = None
                        date = dt_utc_from_llm.in_timezone(user_timezone).date() # Сохраняем только дату
                        
                    logger.info(f"LLM parsed -> Date: {date}, DateTimeUTC: {date_time}, HasTime: {has_time}")
                except Exception as parse_exc:
                    logger.error(f"LLM returned invalid ISO date format: '{iso_date_str}'. Error: {parse_exc}")
                    # Сбрасываем все результаты даты/времени
                    date = None
                    date_time = None
                    has_time = False

            if rrule: is_repeating = True
            else: is_repeating = False
        else: ... # обработка ошибки LLM
    else: ... # обработка недоступности LLM

    # Формируем финальный результат
    # Возвращаем только если удалось получить дату или правило

    

    if date or date_time:
        return {
            'date': date,
            'datetime': date_time,
            'has_time': has_time,
            'is_repeating': is_repeating, # пока не используется
            'rrule': rrule # пока не используется
        }
    else:
        logger.warning(f"Could not parse date from text: '{text_date}'")
        return {'has_time': False, 'is_repeating': False}