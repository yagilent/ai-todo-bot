# src/llm/gemini_client.py

import google.generativeai as genai
import json
import logging
import traceback # Для логирования стека вызовов

# Импортируем настройки и шаблон промпта
from src.config import settings
import pytz 

from src.llm.prompts import INTENT_RECOGNITION_PROMPT_TEMPLATE
from src.llm.prompts import DATE_PARSING_PROMPT_TEMPLATE 
from src.llm.prompts import TIMEZONE_PARSING_PROMPT_TEMPLATE 
from src.llm.prompts import TASK_SEARCH_WITH_CONTEXT_PROMPT_TEMPLATE
from src.llm.prompts import GENERATE_TITLE_PROMPT_TEMPLATE

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
            "max_output_tokens": 1024, # Достаточно для JSON ответа
            # "response_mime_type": "application/json", # Если модель/API поддерживает
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
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

# --- Основная функция обработки ввода ---
async def process_user_input(user_text: str) -> dict:
    """
    Обрабатывает текст пользователя с помощью LLM для извлечения намерения и параметров.

    Args:
        user_text: Текст, введенный пользователем.

    Returns:
        Словарь со структурированным результатом (success, clarification_needed, unknown_intent, error).
    """
    if not model:
        logger.error("LLM client is not available.")
        return {"status": "error", "message": "LLM сервис недоступен."}

    if not user_text or user_text.isspace():
        logger.warning("Received empty or whitespace-only user text.")
        return {"status": "unknown_intent", "original_text": user_text}

    prompt = INTENT_RECOGNITION_PROMPT_TEMPLATE.format(USER_TEXT=user_text)
    logger.debug(f"Sending request to LLM for text: '{user_text[:100]}...'")
    # logger.debug(f"Full prompt:\n{prompt}") # Раскомментировать для отладки промпта

    raw_response_text = "" # Инициализируем на случай ошибки до получения ответа
    try:
        # Асинхронный вызов API
        response = await model.generate_content_async(prompt)

        # Проверка на наличие блокировок безопасности
        if not response.candidates:
             # Обработка случая, когда контент заблокирован или не сгенерирован
             block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
             safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else "N/A"
             logger.warning(f"LLM content generation blocked. Reason: {block_reason}. Safety Ratings: {safety_ratings}. Original text: '{user_text[:100]}...'")
             return {"status": "error", "message": f"Запрос был заблокирован из-за настроек безопасности (Причина: {block_reason})."}

        # Извлечение текста ответа
        raw_response_text = response.text.strip()
        logger.debug(f"Raw response from LLM: {raw_response_text}")

        # Очистка от возможных markdown-блоков JSON
        json_response_text = raw_response_text
        if json_response_text.startswith("```json"):
            json_response_text = json_response_text[7:]
        if json_response_text.endswith("```"):
            json_response_text = json_response_text[:-3]
        json_response_text = json_response_text.strip()

        if not json_response_text:
             logger.error("LLM returned an empty response after stripping.")
             return {"status": "error", "message": "LLM вернула пустой ответ."}

        # Парсинг JSON
        result_data = json.loads(json_response_text)
        logger.info(f"LLM processing result: {result_data.get('status', 'N/A')}, intent: {result_data.get('intent', 'N/A')}")
        return result_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from LLM response: {e}\nRaw response: {raw_response_text}\nOriginal text: '{user_text[:100]}...'", exc_info=True)
        return {"status": "error", "message": "Не удалось обработать ответ от языковой модели (ошибка формата).", "raw_response": raw_response_text}
    except Exception as e:
        # Ловим другие возможные ошибки API (сеть, авторизация, лимиты и т.д.)
        error_type = type(e).__name__
        logger.error(f"Error during LLM API call ({error_type}): {e}\nOriginal text: '{user_text[:100]}...'\nTraceback: {traceback.format_exc()}", exc_info=False) # Логируем стек
        # Попытка получить детали из ответа, если он есть
        feedback_info = "N/A"
        if 'response' in locals() and hasattr(response, 'prompt_feedback'):
             feedback_info = response.prompt_feedback
        return {"status": "error", "message": f"Ошибка при обращении к языковой модели ({error_type}).", "details": str(e), "feedback": str(feedback_info)}

async def process_date_text_with_llm(
    date_text: str, user_timezone: str = 'UTC'
    ) -> Optional[Dict[str, Any]]:
    """
    Использует LLM для парсинга текста даты/времени/повторения.

    Args:
        date_text: Текст для парсинга.
        user_timezone: Таймзона пользователя.

    Returns:
        Словарь с ключами 'date_utc_iso' и 'recurrence_rule' или None в случае ошибки.
    """
    if not model:
        logger.error("LLM client is not available for date parsing.")
        return None
    if not date_text:
        return None

    try:
        # Получаем текущее время в таймзоне пользователя
        now_in_tz = pendulum.now(user_timezone)
        current_dt_iso = now_in_tz.to_iso8601_string()

        prompt = DATE_PARSING_PROMPT_TEMPLATE.format(
            USER_DATE_TEXT=date_text,
            CURRENT_DATETIME_ISO=current_dt_iso,
            USER_TIMEZONE=user_timezone
        )
        logger.debug(f"Sending date parsing request to LLM for text: '{date_text}'")

        logger.debug(f"LLM prompt: '{prompt}'")

        response = await model.generate_content_async(prompt)

        if not response.candidates:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            logger.warning(f"LLM date parsing blocked. Reason: {block_reason}. Text: '{date_text}'")
            return None # Или можно вернуть словарь с ошибкой

        raw_response_text = response.text.strip()
        logger.debug(f"Raw date parsing response from LLM: {raw_response_text}")

        json_response_text = raw_response_text
        if json_response_text.startswith("```json"): json_response_text = json_response_text[7:]
        if json_response_text.endswith("```"): json_response_text = json_response_text[:-3]
        json_response_text = json_response_text.strip()

        if not json_response_text:
            logger.error("LLM returned empty response for date parsing.")
            return None

        parsed_data = json.loads(json_response_text)
        logger.info(f"LLM date parsing result: {parsed_data}")
        return parsed_data # Возвращаем словарь {'date_utc_iso': ..., 'recurrence_rule': ...}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from LLM date parsing response: {e}\nRaw response: {raw_response_text}", exc_info=True)
        return None
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error during LLM date parsing API call ({error_type}): {e}", exc_info=True)
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