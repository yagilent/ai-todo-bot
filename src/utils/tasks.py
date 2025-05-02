# src/utils/tasks.py

import logging
import datetime
from typing import Optional, Dict, Any
import pendulum

logger = logging.getLogger(__name__)

# --- Константы ---
DEFAULT_REMINDER_OFFSET_HOURS = 1
DEFAULT_DATE_REMINDER_TIME_HOUR = 12 # UTC

# --- Функция вычисления времени напоминания по умолчанию ---
def calculate_default_reminder(
    due_date: Optional[datetime.date],
    due_datetime_utc: Optional[datetime.datetime], # UTC
    has_time: bool
    ) -> Optional[datetime.datetime]:
    """
    Вычисляет время напоминания по умолчанию (в UTC).
    """
    now_utc = pendulum.now('UTC')
    reminder_time_utc: Optional[datetime.datetime] = None

    if has_time and due_datetime_utc:
        due_moment = pendulum.instance(due_datetime_utc)
        if due_moment > now_utc:
             calculated_reminder = due_moment.subtract(hours=DEFAULT_REMINDER_OFFSET_HOURS)
             if calculated_reminder > now_utc:
                 reminder_time_utc = calculated_reminder
                 logger.debug(f"Default reminder for datetime: {DEFAULT_REMINDER_OFFSET_HOURS}h before -> {reminder_time_utc}")
             else:
                 logger.debug(f"Default reminder time ({DEFAULT_REMINDER_OFFSET_HOURS}h before) has passed for datetime task.")
    elif not has_time and due_date:
        try:
            date_moment_utc = pendulum.datetime(due_date.year, due_date.month, due_date.day, tz='UTC')
            calculated_reminder = date_moment_utc.set(hour=DEFAULT_DATE_REMINDER_TIME_HOUR, minute=0, second=0, microsecond=0)
            if calculated_reminder > now_utc:
                reminder_time_utc = calculated_reminder
                logger.debug(f"Default reminder for date: {DEFAULT_DATE_REMINDER_TIME_HOUR}:00 UTC -> {reminder_time_utc}")
            else:
                logger.debug(f"Default reminder time ({DEFAULT_DATE_REMINDER_TIME_HOUR}:00 UTC) for date task has passed.")
        except Exception as e:
             logger.error(f"Error calculating date reminder for {due_date}: {e}")

    return reminder_time_utc


# --- Обновленная Функция определения итоговых дат/времени ---
def get_due_and_notification_datetime(
    current_due_obj: Optional[Dict[str, Any]],
    current_notification_dt: Optional[datetime.datetime], # UTC
    new_due_obj: Optional[Dict[str, Any]],
    new_notification_obj: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
    """
    Определяет итоговые дату/время выполнения и время уведомления.
    Если явное время уведомления не задано, вычисляет его по умолчанию на основе срока.
    Если срока нет, но есть уведомление, использует время уведомления как срок.
    """
    logger.debug(f"Calculating final dates/times. Current due: {current_due_obj}, "
                 f"Current notif: {current_notification_dt}, New due: {new_due_obj}, "
                 f"New notif: {new_notification_obj}")

    final_due_date: Optional[datetime.date] = None
    final_due_datetime: Optional[datetime.datetime] = None # UTC
    final_due_has_time: bool = False
    due_date_changed = False # Флаг для логики уведомлений

    # 1. Определяем итоговый срок (due date/datetime/has_time)
    effective_due_obj = None
    if new_due_obj and (new_due_obj.get('date') or new_due_obj.get('datetime')):
        effective_due_obj = new_due_obj
        # Сравниваем с текущим, чтобы понять, изменился ли срок
        if not current_due_obj or \
           current_due_obj.get('date') != new_due_obj.get('date') or \
           current_due_obj.get('datetime') != new_due_obj.get('datetime') or \
           current_due_obj.get('has_time') != new_due_obj.get('has_time'):
            due_date_changed = True
        logger.debug("Using NEW due date object.")
    elif current_due_obj and (current_due_obj.get('date') or current_due_obj.get('datetime')):
        effective_due_obj = current_due_obj
        logger.debug("Using CURRENT due date object.")
    # else: Срока не было и нет

    if effective_due_obj:
        final_due_has_time = effective_due_obj.get('has_time', False)
        if final_due_has_time:
            final_due_datetime = effective_due_obj.get('datetime')
            final_due_date = effective_due_obj.get('date')
        else:
            final_due_date = effective_due_obj.get('date')
            final_due_datetime = None

    # 2. Определяем итоговое время уведомления
    final_notification_datetime: Optional[datetime.datetime] = None

    if new_notification_obj and new_notification_obj.get('datetime'):
        # Явное новое время уведомления - используем его
        final_notification_datetime = new_notification_obj.get('datetime')
        logger.debug(f"Using explicitly provided NEW notification datetime: {final_notification_datetime}")
    elif new_notification_obj and new_notification_obj.get('date'):
        # Явная новая дятя уведомления - используем её
        final_notification_datetime = calculate_default_reminder(
             due_date=new_notification_obj.get('date'),
             due_datetime_utc=None, # Времени нет
             has_time=False # Времени нет
         )
        logger.debug(f"Using explicitly provided NEW notification date: {final_notification_datetime}")
    elif not due_date_changed and current_notification_dt:
        # Нового уведомления нет, срок НЕ менялся - оставляем старое уведомление
        final_notification_datetime = current_notification_dt
        logger.debug(f"Keeping CURRENT notification datetime: {final_notification_datetime}")
    else:
        # Нового уведомления нет И (срок изменился ИЛИ старого уведомления не было)
        # -> Вычисляем напоминание по умолчанию на основе ИТОГОВОГО срока
        logger.debug("Explicit notification not provided or due date changed. Calculating default reminder.")
        final_notification_datetime = calculate_default_reminder(
            due_date=final_due_date,
            due_datetime_utc=final_due_datetime,
            has_time=final_due_has_time
        )
        if final_notification_datetime:
             logger.info(f"Default reminder calculated: {final_notification_datetime}")
        else:
             logger.info("No default reminder could be calculated (due date might be past or has no time).")


    # 3. Корректировка: Если срока нет, но уведомление есть/вычислено, ставим срок по уведомлению
    if not final_due_date and not final_due_datetime and final_notification_datetime:
        logger.debug("No due date determined, but notification exists. Setting due date = notification datetime.")
        final_due_datetime = final_notification_datetime
        final_due_date = pendulum.instance(final_notification_datetime).date()
        final_due_has_time = True # Считаем, что раз уведомление точное, то и у срока есть время

    # 4. Формирование результата
    result = {
        'due_date': final_due_date,
        'due_datetime': final_due_datetime,
        'due_has_time': final_due_has_time,
        'notification_datetime': final_notification_datetime
        # Убираем 'due_date_changed', т.к. он больше не нужен снаружи
    }
    logger.debug(f"Final calculated task times: {result}")
    return result
