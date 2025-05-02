# src/tgbot/handlers/intent_handlers/__init__.py

# Импортируем функции из соседних модулей для удобства

from .add_task import handle_add_task
from .find_tasks import handle_find_tasks
from .update_timezone import handle_update_timezone
from .complete_task import handle_complete_task       
from .reschedule_task import handle_reschedule_task   
from .edit_description import handle_edit_task_description 
from .snooze_task import handle_snooze_task           
from .clarification import handle_clarification_request
from .unknown import handle_unknown_intent, handle_error_intent

# Экспортируем их все с новыми именами
__all__ = [
    "handle_add_task",
    "handle_find_tasks",
    "handle_update_timezone",
    "handle_complete_task",
    "handle_reschedule_task",
    "handle_edit_task_description",
    "handle_snooze_task",
    "handle_clarification_request",
    "handle_unknown_intent",
    "handle_error_intent",
]