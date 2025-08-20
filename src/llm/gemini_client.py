# src/llm/gemini_client.py

import google.generativeai as genai
import json
import logging
# import traceback # Больше не используется

# Импортируем настройки и шаблон промпта
from src.config import settings
import pytz 

# Старые длинные промпты больше не используются в продакшене
# from src.llm.prompts import INTENT_RECOGNITION_PROMPT_TEMPLATE
# from src.llm.prompts import DATE_PARSING_PROMPT_TEMPLATE 
from src.llm.prompts import TIMEZONE_PARSING_PROMPT_TEMPLATE 
from src.llm.prompts import TASK_SEARCH_WITH_CONTEXT_PROMPT_TEMPLATE
from src.llm.prompts import GENERATE_TITLE_PROMPT_TEMPLATE

from src.llm.prompts import (
    SIMPLE_INTENT_DETECTION_PROMPT,
    TASK_PARSING_PROMPT, 
    REMINDER_TIME_PARSING_PROMPT,
    RESCHEDULE_TIME_EXTRACTION_PROMPT,
    EDIT_DESCRIPTION_EXTRACTION_PROMPT,
    RECURRING_DETECTION_PROMPT,
    RRULE_GENERATION_PROMPT
)

import pendulum # Нужен для получения текущего времени

from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)

# --- Настройка клиента Gemini ---
try:
    if not settings.google_api_key:
        logger.warning("GOOGLE_API_KEY is not set in config. LLM features will be disabled.")
        model = None
    else:
        genai.configure(api_key=settings.google_api_key)
        # Настройки генерации (можно вынести в config.py при желании)
        generation_config = {
            "temperature": 0.5, # Низкая температура для более предсказуемого извлечения
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048, # Увеличили лимит для избежания обрезания
            # "response_mime_type": "application/json", # Если модель/API поддерживает
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},  
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        # Выбор модели (убедись, что выбрана подходящая и доступная)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash", # Или gemini-pro, или другая
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        logger.info("Google Gemini client initialized successfully.")

except Exception as e:
    logger.error(f"Failed to initialize Google Gemini client: {e}", exc_info=True)
    model = None

# --- НОВЫЕ ФУНКЦИИ С КОРОТКИМИ ПРОМПТАМИ ---
async def detect_intent_simple(user_text: str, is_reply: bool = False) -> Optional[str]:
    """
    Функция для простого определения интента с помощью короткого промпта.
    Возвращает только строку интента или None при ошибке.
    """
    if not model:
        logger.error("LLM model not available")
        return None
        
    prompt = SIMPLE_INTENT_DETECTION_PROMPT.format(
        USER_TEXT=user_text,
        IS_REPLY=is_reply
    )
    
    logger.debug(f"Testing simple intent detection with prompt: {prompt[:100]}...")
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked by safety filters")
            return None
            
        raw_text = response.text.strip()
        logger.debug(f"Raw LLM response: {raw_text}")

        # Очистка от markdown блоков если есть
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):

            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        # Парсим JSON
        result = json.loads(raw_text)
        intent = result.get("intent", "unknown")
        
        logger.info(f"Detected intent: '{intent}' for text: '{user_text[:50]}...'")
        return intent
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from intent detection: {e}. Raw: {raw_text}")
        return None
    except Exception as e:
        logger.error(f"Error in intent detection: {e}")
        return None


async def parse_task_simple(user_text: str) -> Optional[Dict]:
    """
    Функция для парсинга задачи с помощью короткого промпта.
    Возвращает dict с description и reminder_time или None.
    """
    if not model:
        logger.error("LLM model not available")
        return None
        
    prompt = TASK_PARSING_PROMPT.format(USER_TEXT=user_text)
    
    logger.debug(f"Testing task parsing for: '{user_text}'")
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            block_reason = "Unknown"
            if response.prompt_feedback:
                block_reason = getattr(response.prompt_feedback, 'block_reason', 'Unknown')
            logger.warning(f"LLM response blocked by safety filters. Reason: {block_reason}")
            return None

        # Проверяем что есть валидный контент
        try:
            raw_text = response.text.strip()
        except Exception as e:
            # Проверяем причину завершения
            finish_reason = "unknown"
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = getattr(response.candidates[0], 'finish_reason', 'unknown')
            
            if finish_reason == 2:  # MAX_TOKENS
                logger.error(f"Task parsing hit token limit (finish_reason=2) for text: '{user_text}'")
            else:
                logger.error(f"Failed to get response text (finish_reason={finish_reason}): {e}")
            
            # Fallback: возвращаем простое описание задачи
            return {
                "description": user_text.strip(),
                "reminder_time": None
            }
        logger.debug(f"Raw task parsing response: {raw_text}")
        
        # Очистка от markdown если есть
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        result = json.loads(raw_text)
        
        logger.info(f"Parsed task - Description: '{result.get('description')}', Reminder: '{result.get('reminder_time')}'")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse task JSON: {e}. Raw: {raw_text}")
        return None
    except Exception as e:
        logger.error(f"Error in task parsing: {e}")
        return None


async def parse_reminder_time_simple(
    reminder_text: str, 
    user_timezone: str = "Europe/Moscow"
) -> Optional[str]:
    """
    Функция для парсинга времени напоминания с помощью короткого промпта.
    Возвращает ISO строку UTC времени или None.
    """
    if not model or not reminder_text:
        return None
        
    # Текущее время в пользовательской зоне
    current_time = pendulum.now(user_timezone).to_iso8601_string()
    
    prompt = REMINDER_TIME_PARSING_PROMPT.format(
        CURRENT_DATETIME_ISO=current_time,
        USER_TIMEZONE=user_timezone,
        REMINDER_TEXT=reminder_text
    )
    
    logger.debug(f"Testing reminder time parsing for: '{reminder_text}' in {user_timezone}")
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked")
            return None
            
        raw_text = response.text.strip()
        logger.debug(f"Raw reminder time response: {raw_text}")
        
        # Очистка от markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        result = json.loads(raw_text)
        reminder_utc = result.get("reminder_datetime_utc")
        
        if reminder_utc:
            # Валидируем что это корректное ISO время
            parsed_time = pendulum.parse(reminder_utc)
            logger.info(f"Parsed reminder time: '{reminder_text}' → {reminder_utc} ({parsed_time.format('YYYY-MM-DD HH:mm')} UTC)")
            return reminder_utc
        else:
            logger.warning(f"No reminder time returned for: '{reminder_text}'")
            return None
            
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse reminder time JSON: {e}. Raw: {raw_text}")
        return None
    except Exception as e:
        logger.error(f"Error in reminder time parsing: {e}")
        return None


async def _extract_reschedule_time(user_text: str) -> Optional[Dict]:
    """
    Извлекает новое время напоминания из текста переноса задачи.
    """
    if not model:
        return None
        
    prompt = RESCHEDULE_TIME_EXTRACTION_PROMPT.format(USER_TEXT=user_text)
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked for reschedule time extraction")
            return None
            
        raw_text = response.text.strip()
        
        # Очистка от markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        result = json.loads(raw_text)
        logger.info(f"Extracted reschedule time: {result}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse reschedule time JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in reschedule time extraction: {e}")
        return None


async def _extract_edit_description(user_text: str) -> Optional[Dict]:
    """
    Извлекает новое описание задачи из текста редактирования.
    """
    if not model:
        return None
        
    prompt = EDIT_DESCRIPTION_EXTRACTION_PROMPT.format(USER_TEXT=user_text)
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked for edit description extraction")
            return None
            
        raw_text = response.text.strip()
        
        # Очистка от markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        result = json.loads(raw_text)
        logger.info(f"Extracted edit description: {result}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse edit description JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in edit description extraction: {e}")
        return None

# --- Основная функция обработки ввода (НОВАЯ ВЕРСИЯ с цепочкой коротких промптов) ---
async def process_user_input(user_text: str, is_reply: bool = False, user_timezone: str = "Europe/Moscow") -> dict:
    """
    Обрабатывает текст пользователя с помощью цепочки коротких LLM запросов.

    Args:
        user_text: Текст, введенный пользователем.
        is_reply: Является ли сообщение ответом на сообщение бота.
        user_timezone: Часовой пояс пользователя для корректного парсинга времени.

    Returns:
        Словарь со структурированным результатом для каждого интента.
    """
    if not model:
        logger.error("LLM client is not available.")
        return {"status": "error", "message": "LLM сервис недоступен."}

    if not user_text or user_text.isspace():
        logger.warning("Received empty or whitespace-only user text.")
        return {"status": "unknown_intent", "original_text": user_text}

    logger.debug(f"Processing user input with new chain approach: '{user_text[:100]}...'")

    try:
        # Шаг 1: Определяем интент
        intent = await detect_intent_simple(user_text, is_reply)
        if not intent or intent == "unknown":
            return {"status": "unknown_intent", "original_text": user_text}

        logger.info(f"Detected intent: '{intent}' for text: '{user_text[:50]}...'")

        # Шаг 2: Обработка в зависимости от интента
        if intent == "add_task":
            return await _process_add_task(user_text, user_timezone)
        elif intent == "find_tasks":
            return {"status": "success", "intent": "find_tasks", "params": {"query_text": user_text}}
        elif intent == "complete_task":
            return {"status": "success", "intent": "complete_task", "params": {}}
        elif intent == "reschedule_task":
            # Извлекаем новое время из текста через короткий промпт
            return await _process_reschedule_task(user_text, user_timezone)
        elif intent == "edit_task_description":
            # Извлекаем новое описание из текста через короткий промпт
            return await _process_edit_description(user_text)
        elif intent == "update_timezone":
            return {"status": "success", "intent": "update_timezone", "params": {"location_text": user_text}}
        else:
            return {"status": "unknown_intent", "original_text": user_text}

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during new chain processing ({error_type}): {e}", exc_info=True)
        return {"status": "error", "message": f"Ошибка при обработке запроса ({error_type}).", "details": str(e)}


async def _process_add_task(user_text: str, user_timezone: str) -> dict:
    """Обрабатывает интент добавления задачи через цепочку промптов."""
    try:
        # Парсим задачу
        task_details = await parse_task_simple(user_text)
        if not task_details:
            return {"status": "error", "message": "Не удалось разобрать задачу."}

        description = task_details.get("description")
        reminder_time_text = task_details.get("reminder_time")

        if not description:
            return {"status": "clarification_needed", "intent": "add_task", 
                   "question": "Уточните, что нужно сделать?", "partial_params": {}}

        params = {"description": description}

        # НОВОЕ: Проверяем на рекуррентность (используем оригинальный текст)
        recurring_info = await detect_recurring_pattern(user_text)
        if recurring_info and recurring_info.get("is_recurring"):
            pattern = recurring_info.get("pattern")
            logger.info(f"Detected recurring task: '{pattern}'")
            
            # Генерируем RRULE
            rrule = await generate_rrule(pattern) if pattern else None
            
            # Добавляем информацию о повторении в параметры
            params["is_repeating"] = True
            params["recurrence_pattern"] = pattern
            params["recurrence_rule"] = rrule
        else:
            params["is_repeating"] = False
            params["recurrence_rule"] = None

        # Обрабатываем время напоминания
        if reminder_time_text:
            # Обычный случай - время напоминания извлечено из описания
            reminder_utc = await parse_reminder_time_simple(reminder_time_text, user_timezone)
            if reminder_utc:
                params["due_date_time_text"] = reminder_time_text
                params["parsed_reminder_utc"] = reminder_utc
            else:
                logger.warning(f"Failed to parse reminder time: '{reminder_time_text}'")
        elif params.get("is_repeating") and params.get("recurrence_pattern"):
            # ИСПРАВЛЕНИЕ: Для рекуррентных задач без времени напоминания используем pattern
            pattern = params.get("recurrence_pattern")
            logger.info(f"Recurring task without reminder_time, using pattern for reminder: '{pattern}'")
            
            reminder_utc = await parse_reminder_time_simple(pattern, user_timezone)
            if reminder_utc:
                params["due_date_time_text"] = pattern
                params["parsed_reminder_utc"] = reminder_utc
                logger.info(f"Successfully parsed reminder from pattern: {reminder_utc}")
            else:
                logger.warning(f"Failed to parse reminder time from pattern: '{pattern}'")

        return {"status": "success", "intent": "add_task", "params": params}

    except Exception as e:
        logger.error(f"Error processing add_task: {e}", exc_info=True)
        return {"status": "error", "message": "Ошибка при обработке создания задачи."}


async def _process_reschedule_task(user_text: str, user_timezone: str) -> dict:
    """Обрабатывает интент переноса задачи через короткие промпты."""
    try:
        # Извлекаем новое время из текста
        time_result = await _extract_reschedule_time(user_text)
        if not time_result:
            return {"status": "error", "message": "Не удалось извлечь новое время."}

        new_time_text = time_result.get("new_reminder_time")
        if not new_time_text:
            return {"status": "error", "message": "Не указано новое время напоминания."}

        # Парсим новое время напоминания
        new_reminder_utc = await parse_reminder_time_simple(new_time_text, user_timezone)
        
        params = {"new_due_date_text": new_time_text}
        if new_reminder_utc:
            params["parsed_reminder_utc"] = new_reminder_utc

        return {"status": "success", "intent": "reschedule_task", "params": params}

    except Exception as e:
        logger.error(f"Error processing reschedule_task: {e}", exc_info=True)
        return {"status": "error", "message": "Ошибка при обработке переноса задачи."}


async def _process_edit_description(user_text: str) -> dict:
    """Обрабатывает интент редактирования описания через короткие промпты."""
    try:
        # Извлекаем новое описание из текста
        desc_result = await _extract_edit_description(user_text)
        if not desc_result:
            return {"status": "error", "message": "Не удалось извлечь новое описание."}

        new_description = desc_result.get("new_description")
        if not new_description:
            return {"status": "error", "message": "Не указано новое описание задачи."}

        return {"status": "success", "intent": "edit_task_description", "params": {"new_description": new_description}}

    except Exception as e:
        logger.error(f"Error processing edit_task_description: {e}", exc_info=True)
        return {"status": "error", "message": "Ошибка при обработке редактирования описания."}

async def process_date_text_with_llm(
    date_text: str, user_timezone: str = 'UTC'
    ) -> Optional[Dict[str, Any]]:
    """
    Использует новую цепочку коротких промптов для парсинга даты/времени.
    ОБНОВЛЕННАЯ ВЕРСИЯ - теперь использует test_parse_reminder_time_simple.

    Args:
        date_text: Текст для парсинга.
        user_timezone: Таймзона пользователя.

    Returns:
        Словарь с ключами 'date_utc_iso', 'has_time' и 'recurrence_rule' или None в случае ошибки.
    """
    if not model or not date_text:
        logger.error("LLM client is not available or date_text is empty.")
        return None

    try:
        # Используем новую функцию парсинга времени
        reminder_utc = await parse_reminder_time_simple(date_text, user_timezone)
        
        if reminder_utc:
            # Возвращаем в формате, совместимом со старой функцией
            return {
                "date_utc_iso": reminder_utc,
                "has_time": True,  # Новая функция всегда включает время
                "recurrence_rule": None  # Пока не поддерживается в новой цепочке
            }
        else:
            logger.warning(f"Failed to parse date text with new chain: '{date_text}'")
            return None

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during new chain date parsing ({error_type}): {e}", exc_info=True)
        return None
    

async def generate_title_with_llm(
    description: str
    ) -> Optional[str]:

    if not model:
        logger.error("LLM client is not available for date parsing.")
        return None
    if not description:
        return None
    try:
        prompt = GENERATE_TITLE_PROMPT_TEMPLATE.format(
            MAX_TITLE_LENGTH=21,
            DESCRIPTION=description
        )
        logger.debug(f"Sending title generation request to LLM for description: '{description}'")

        logger.debug(f"LLM prompt: '{prompt}'")

        response = await model.generate_content_async(prompt)
        
        return response.text.strip()

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during LLM date parsing API call ({error_type}): {e}", exc_info=True)
        return None
    

async def parse_timezone_from_text(text: str) -> Optional[str]:
    """
    Использует LLM для определения IANA таймзоны по тексту.

    Args:
        text: Текст для парсинга (город, страна, смещение и т.д.).

    Returns:
        Строку с валидным именем таймзоны IANA или None в случае ошибки/неудачи.
    """
    if not model: # Проверяем, инициализирована ли модель
        logger.error("LLM client is not available for timezone parsing.")
        return None
    if not text or text.isspace():
        logger.warning("Received empty or whitespace text for timezone parsing.")
        return None

    # Используем UTC как "текущую" таймзону для LLM, т.к. ей важно само описание, а не точное текущее время
    # Но можно передать и реальную таймзону пользователя, если она известна и может помочь контексту
    now_utc_iso = pendulum.now('UTC').to_iso8601_string()

    prompt = TIMEZONE_PARSING_PROMPT_TEMPLATE.format(
        USER_TIMEZONE_TEXT=text,
        CURRENT_DATETIME_ISO=now_utc_iso, # Передаем UTC
        USER_TIMEZONE='UTC' # Указываем, что время в UTC
    )
    logger.debug(f"Sending timezone parsing request to LLM for text: '{text}'")

    raw_response_text = ""
    try:
        response = await model.generate_content_async(prompt)

        if not response.candidates:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            logger.warning(f"LLM timezone parsing blocked. Reason: {block_reason}. Text: '{text}'")
            return None

        raw_response_text = response.text.strip()
        logger.debug(f"Raw timezone parsing response from LLM: {raw_response_text}")

        # Очистка от ```json
        json_response_text = raw_response_text
        if json_response_text.startswith("```json"): json_response_text = json_response_text[7:]
        if json_response_text.endswith("```"): json_response_text = json_response_text[:-3]
        json_response_text = json_response_text.strip()

        if not json_response_text:
            logger.error("LLM returned empty response for timezone parsing.")
            return None

        # Парсинг JSON
        parsed_data = json.loads(json_response_text)
        iana_timezone = parsed_data.get("iana_timezone")

        if iana_timezone:
            # Валидация с помощью pytz
            try:
                pytz.timezone(iana_timezone)
                logger.info(f"LLM successfully parsed timezone '{text}' as '{iana_timezone}'")
                return iana_timezone
            except pytz.UnknownTimeZoneError:
                logger.warning(f"LLM returned an invalid IANA timezone: '{iana_timezone}' for input '{text}'")
                return None # Считаем невалидный ответ неудачей
        else:
            logger.warning(f"LLM could not determine timezone for: '{text}'")
            return None

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from LLM timezone response. Raw: {raw_response_text}", exc_info=True)
        return None
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during LLM timezone parsing API call ({error_type}): {e}", exc_info=True)
        return None
      

async def find_tasks_with_llm(
    user_query: str,
    tasks_list: List[Dict[str, Any]] # Список задач в виде словарей
    ) -> Optional[List[int]]:
    """
    Использует LLM для поиска релевантных задач в предоставленном списке.

    Args:
        user_query: Текстовый запрос пользователя.
        tasks_list: Список задач пользователя, каждая задача - словарь с 'id', 'description', 'title', 'status', 'date_utc_iso'.

    Returns:
        Список ID подходящих задач или None в случае ошибки.
    """
    if not model:
        logger.error("LLM client is not available for task search.")
        return None
    if not user_query:
        logger.warning("Received empty query for LLM task search.")
        return [] # Пустой запрос - пустой результат

    # Преобразуем список задач в JSON строку для промпта
    try:
        # Ограничим количество задач, если их слишком много, чтобы не превысить лимит токенов
        MAX_TASKS_FOR_LLM = 100 # Примерный лимит, подобрать экспериментально
        tasks_json_str = json.dumps(tasks_list[:MAX_TASKS_FOR_LLM], ensure_ascii=False, indent=2)
        if len(tasks_list) > MAX_TASKS_FOR_LLM:
             logger.warning(f"Too many tasks ({len(tasks_list)}) for user. Sending only first {MAX_TASKS_FOR_LLM} to LLM search.")
    except Exception as e:
        logger.error(f"Failed to serialize task list to JSON: {e}")
        return None # Ошибка сериализации

    # Текущее время для контекста LLM
    now_utc_iso = pendulum.now('UTC').to_iso8601_string()

    prompt = TASK_SEARCH_WITH_CONTEXT_PROMPT_TEMPLATE.format(
        USER_QUERY=user_query,
        TASK_LIST_JSON=tasks_json_str,
        CURRENT_TIME_UTC_ISO=now_utc_iso
    )
    logger.debug(f"Sending task search request to LLM. Query: '{user_query}', Tasks count: {len(tasks_list)}")
    logger.debug(f"Prompt: '{prompt}'")
    # logger.debug(f"Full search prompt (potentially large):\n{prompt[:1000]}...") # Логируем начало промпта

    raw_response_text = ""
    try:
        response = await model.generate_content_async(prompt)

        if not response.candidates:
            # ... (обработка блокировки) ...
             logger.warning(f"LLM task search blocked. Query: '{user_query}'")
             return None

        raw_response_text = response.text.strip()
        logger.debug(f"Raw task search response from LLM: {raw_response_text}")

        
        json_start_index = raw_response_text.find('{')
        json_end_index = raw_response_text.rfind('}')

        if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
            # Извлекаем текст между первой { и последней } включительно
            json_response_text = raw_response_text[json_start_index : json_end_index + 1]
            logger.debug(f"Extracted JSON part: {repr(json_response_text)}")
        else:
            # Если не нашли { или }, считаем ответ некорректным
            logger.error(f"Could not find valid JSON structure in LLM response. Raw: {repr(raw_response_text)}")
            json_response_text = "" # Устанавливаем пустую строку


        if not json_response_text:
             logger.error("LLM returned empty response for task search.")
             return None

        # Парсинг JSON
        parsed_data = json.loads(json_response_text)
        task_ids = parsed_data.get("matching_task_ids")

        # Валидация результата
        if isinstance(task_ids, list) and all(isinstance(tid, int) for tid in task_ids):
            logger.info(f"LLM found {len(task_ids)} matching task IDs for query '{user_query}'")
            return task_ids
        else:
            logger.error(f"LLM returned invalid format for task IDs: {task_ids}. Expected list of integers.")
            return None # Ошибка формата

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from LLM task search response. Raw: {raw_response_text}", exc_info=True)
        return None
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during LLM task search API call ({error_type}): {e}", exc_info=True)
        return None


# === ФУНКЦИИ ДЛЯ РАБОТЫ С РЕКУРРЕНТНЫМИ ЗАДАЧАМИ ===

async def detect_recurring_pattern(description: str) -> Optional[Dict[str, Any]]:
    """
    Определяет, является ли задача повторяющейся и извлекает паттерн.
    
    Args:
        description: Описание задачи
        
    Returns:
        Dict с ключами is_recurring, pattern или None при ошибке
    """
    if not model or not description:
        return None
        
    prompt = RECURRING_DETECTION_PROMPT.format(DESCRIPTION=description)
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked for recurring detection")
            return None
            
        raw_text = response.text.strip()
        
        # Очистка от markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        result = json.loads(raw_text)
        
        is_recurring = result.get("is_recurring", False)
        pattern = result.get("pattern")
        
        logger.info(f"Recurring detection - Description: '{description[:50]}...', "
                   f"Is recurring: {is_recurring}, Pattern: '{pattern}'")
        
        return {
            "is_recurring": is_recurring,
            "pattern": pattern
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recurring detection JSON: {e}. Raw: {raw_text}")
        return None
    except Exception as e:
        logger.error(f"Error in recurring pattern detection: {e}")
        return None


async def generate_rrule(pattern: str) -> Optional[str]:
    """
    Генерирует RRULE строку для повторяющегося паттерна.
    
    Args:
        pattern: Паттерн повторения на русском языке
        
    Returns:
        RRULE строка или None при ошибке
    """
    if not model or not pattern:
        return None
        
    current_time = pendulum.now().to_iso8601_string()
    prompt = RRULE_GENERATION_PROMPT.format(
        CURRENT_TIME=current_time,
        PATTERN=pattern
    )
    
    try:
        response = await model.generate_content_async(prompt)
        
        if not response.candidates:
            logger.warning("LLM response blocked for RRULE generation")
            return None
            
        raw_text = response.text.strip()
        
        # RRULE обычно возвращается как простой текст, не JSON
        if raw_text and raw_text.lower() != "null":
            # Валидируем что это похоже на RRULE
            if "FREQ=" in raw_text:
                logger.info(f"Generated RRULE for pattern '{pattern}': {raw_text}")
                return raw_text
            else:
                logger.warning(f"Invalid RRULE format: {raw_text}")
                return None
        else:
            logger.info(f"No RRULE could be generated for pattern: '{pattern}'")
            return None
        
    except Exception as e:
        logger.error(f"Error in RRULE generation: {e}")
        return None
