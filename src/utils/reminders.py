# src/utils/reminders.py
import logging
import datetime
import pendulum
from typing import Optional

logger = logging.getLogger(__name__)

def calculate_next_reminder(
    due_date_utc: Optional[datetime.datetime],
    # user_timezone: str = 'UTC' # Таймзона больше не нужна здесь
    ) -> Optional[datetime.datetime]:
    """
    Вычисляет время напоминания по умолчанию: за 1 час до срока,
    если у срока указано точное время.
    """
    if not due_date_utc:
        return None # Нет срока - нет напоминания

    now_utc = pendulum.now('UTC')
    due_moment = pendulum.instance(due_date_utc)

    # Если срок уже прошел
    if due_moment <= now_utc:
        return None

    # Напоминаем только если указано время (не 00:00:00)
    if due_moment.time() != pendulum.Time(0, 0, 0):
        reminder_time = due_moment.subtract(hours=1)
        # Напоминаем только если время "за час" еще не прошло
        if reminder_time > now_utc:
            logger.debug(f"Default reminder: 1 hour before due time -> {reminder_time}")
            return reminder_time
        else:
            logger.debug("Default reminder time (1 hour before) has passed.")
            # Можно вернуть due_moment, чтобы напомнить точно в срок? Пока нет.
            return None
    else:
        # Если только дата, напоминания по умолчанию нет
        logger.debug("No default reminder for date-only task.")
        return None