# src/utils/parsers.py
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def extract_task_id_from_text(text: Optional[str]) -> Optional[int]:
    """
    Извлекает ID задачи из текста сообщения бота (ищет '(ID: ЧИСЛО)').
    """
    if not text:
        return None
    # Ищем паттерн (ID: число) в конце строки, возможно с пробелами перед
    match = re.search(r'\s*\(ID:\s*(\d+)\)\s*$', text)
    if match:
        try:
            task_id = int(match.group(1))
            logger.debug(f"Extracted task ID {task_id} from text.")
            return task_id
        except ValueError:
            logger.error(f"Could not convert extracted ID '{match.group(1)}' to int.")
            return None
    else:
        logger.debug("No task ID pattern found in text.")
        return None

# Можно добавить другие парсеры сюда