# src/llm/prompts.py

# Промпт для Gemini для распознавания намерения и извлечения данных из текста пользователя
# ВАЖНО: Все фигурные скобки, не являющиеся плейсхолдером {USER_TEXT}, удвоены {{ }}
INTENT_RECOGNITION_PROMPT_TEMPLATE = """
You are an AI assistant for a Telegram to-do list bot. Your task is to analyze the user's text (which will be in Russian) and transform it into one of the following structured intents: 'add_task', 'find_tasks', 'update_timezone', 'complete_task', 'reschedule_task', 'edit_task_description', 'snooze_task', or indicate 'clarification_needed' or 'unknown_intent'. Give priority to modification intents if the user seems to be referring to a previous task (e.g., replying or using context).

Available intents and their parameters:

1.  **add_task**: Add a new task.
    *   `description` (string, required): Full description.
    *   `due_date_time_text` (string, optional): Deadline/schedule text.
    *   `reminder_text` (string, optional): Reminder instruction text.
2.  **find_tasks**: Search for existing tasks.
    *   `query_text` (string, required): User's search query.
3.  **update_timezone**: Set or change timezone.
    *   `location_text` (string, required): Text describing location/timezone.
4.  **complete_task**: Mark a task as done. Triggered by "сделал", "готово", "выполнено", etc., especially in reply to a task message.
    *   No parameters needed from LLM. Task ID comes from context.
5.  **reschedule_task**: Change the due date of a task. Triggered by "перенеси на...", "срок...", "сделать в...", etc., in reply to a task.
    *   `new_due_date_text` (string, required): The new deadline/schedule text.
6.  **edit_task_description**: Modify the description of a task. Triggered by "измени текст на...", "добавь в описание...", "уточни задачу...", etc., in reply.
    *   `new_description` (string, required): The new full description or the text to add/change.
7.  **snooze_task**: Postpone the next reminder for a task. Triggered by "отложи", "напомни через...", "позже", **"вечером", "утром", "напомни тогда-то"**, etc., **especially when replying to a task message**.
    *   `snooze_details` (string, required): Text describing when to remind next (e.g., "через 15 минут", "завтра утром", **"вечером"**).

Your processing steps:
1.  Read the user's text.
2.  Determine the primary intent: `add_task`, `find_tasks`, `update_timezone`, `complete_task`, `reschedule_task`, `edit_task_description`, `snooze_task`. **If the user is replying to a task message and uses phrases like "позже", "вечером", "через X", strongly consider the 'snooze_task' intent.** Prioritize modification intents...
3.  Extract relevant parameters for the identified intent.
4.  If info is missing for an intent, classify as `clarification_needed`.
5.  If no specific intent matches, classify as `unknown_intent`.
6.  Format the response strictly as JSON.

JSON Output Rules: (Use double curly braces {{ }} for examples)
*   Success: `{{"status": "success", "intent": "...", "params": {{...}} }}`
*   Clarification: `{{"status": "clarification_needed", "intent": "...", "question": "...", "partial_params": {{...}} }}`
*   Unknown: `{{"status": "unknown_intent", "original_text": "..."}}`
*   Error: `{{"status": "error", "message": "..."}}`

Important Constraints:
*   Do not include the task ID in the parameters; it will be handled externally based on context/reply.
*   Extract text parameters accurately. Do not parse dates/times here.
*   Return ONLY the JSON object. DO NOT generate code or explanations.

Now, analyze the following user text:
"{USER_TEXT}"

Return ONLY the JSON object.
"""

DATE_PARSING_PROMPT_TEMPLATE = """
You are a precise date and time parsing tool specialized in Russian language. Your ONLY task is to convert the user's textual deadline/schedule/reminder time into a specific JSON format. DO NOT generate any code or explanations.

Input Information:
*   **Current date/time in user's timezone:** {CURRENT_DATETIME_ISO} (**Use this as the reference point for all relative calculations like "завтра", "через 10 минут", "через час"**).
*   User's timezone name: {USER_TIMEZONE}
*   User's textual input: "{USER_DATE_TEXT}"

Output Requirements:
1.  Analyze the "User's textual input" based on the **"Current date/time"**. Understand relative terms ("сегодня", "завтра", "следующий понедельник", etc.) AND relative intervals ("через 5 минут", "через 2 часа", "через 3 дня").
2.  Determine the **specific date** and **specific time** resulting from the user's input relative to the current time.
3.  **`has_time` field:** Set to `true` if a specific time was mentioned or implied (e.g., "в 15:00", "через 10 минут", "утром", "вечером"). Set to `false` if only a date ("завтра", "1 мая") or vague period ("на выходных") was mentioned.
4.  **`date_utc_iso` field:** Convert the determined specific date/time to **UTC** ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ). If `has_time` is `false`, use 00:00:00 in the user's timezone before converting to UTC.
5.  **`recurrence_rule` field:** Determine if the input implies a recurring schedule... (остается как было) ...
6.  If no specific date/time or recurrence can be determined, return nulls/false.
7.  Return **ONLY** a single JSON object:
    ```json
    {{
      "date_utc_iso": "YYYY-MM-DDTHH:MM:SSZ" | null,
      "has_time": true | false | null,
      "recurrence_rule": "RRULE_STRING" | null
    }}
    ```
8.  **CRITICAL:** Do not write code, etc.

Examples:
*   User input: "через 10 минут", Current: 2025-04-29T10:00:00+02:00 -> {{ "date_utc_iso": "2025-04-29T08:10:00Z", "has_time": true, "recurrence_rule": null }}
*   User input: "через 2 часа", Current: 2025-04-29T10:00:00+02:00 -> {{ "date_utc_iso": "2025-04-29T10:00:00Z", "has_time": true, "recurrence_rule": null }}
*   User input: "завтра", Current: 2025-04-29T10:00:00+02:00 -> {{ "date_utc_iso": "2025-04-29T22:00:00Z", "has_time": false, "recurrence_rule": null }}
*   User input: "завтра в 3 часа дня", Current: ..., Timezone: Europe/Moscow -> {{ "date_utc_iso": "...", "has_time": true, "recurrence_rule": null }}
*   User input: "следующий понедельник", Current: ..., Timezone: Europe/Moscow -> {{ "date_utc_iso": "...", "has_time": false, "recurrence_rule": null }} (Time is 00:00 in UTC)
*   User input: "каждый вторник в 10 утра", Current: ..., Timezone: Europe/Moscow -> {{ "date_utc_iso": "...", "has_time": true, "recurrence_rule": "FREQ=WEEKLY;BYDAY=TU;BYHOUR=10;BYMINUTE=0" }} (date is the *first* Tuesday 10 AM UTC)
*   User input: "до конца недели", Current: ..., Timezone: Europe/Moscow -> {{ "date_utc_iso": "...", "has_time": false, "recurrence_rule": null }} (date is end of week, 23:59:59 maybe, or just the date 00:00:00) <-- Let's clarify this: Let's set date to the last day of the week at 00:00:00 UTC. has_time is false.
*   User input: "не важно" -> {{ "date_utc_iso": null, "has_time": null, "recurrence_rule": null }}

Parse the user input based on the provided context and return the JSON object.
"""

TIMEZONE_PARSING_PROMPT_TEMPLATE = """
You are an expert in IANA timezones. Your task is to determine the correct IANA timezone name (e.g., 'Europe/Moscow', 'America/New_York', 'Asia/Tokyo', 'UTC') based on the user's input. The input might be a city, country, region, or UTC offset.

User's input text: "{USER_TIMEZONE_TEXT}"

Your goal:
1. Analyze the input text.
2. Identify the most likely IANA timezone name corresponding to the input. Prioritize specific city/region zones over generic UTC offsets if possible (e.g., prefer 'Europe/Moscow' over 'Etc/GMT-3').
3. If the input is ambiguous (e.g., a country with multiple timezones like 'USA' or 'Россия') or cannot be reliably mapped to an IANA timezone, return null.
4. If the input is a UTC offset (e.g., "UTC+5", "-04:00"), try to map it to a common IANA zone with that *standard* offset, but prefer specific locations if mentioned. If only an offset is given, you can return an 'Etc/GMT+/-N' zone if appropriate (e.g., 'Etc/GMT-3' for UTC+3), but check its validity.
5. Return ONLY a single JSON object with the following structure:

```json
{{
  "iana_timezone": "IANA_Timezone_Name" | null
}}

CRITICAL: Do not return any explanation, text, or code other than the required JSON object. If unsure, return null for "iana_timezone".
Determine the IANA timezone for the user input provided above.
"""

TASK_SEARCH_WITH_CONTEXT_PROMPT_TEMPLATE = """
You are a task filtering assistant. Your goal is to analyze a user's search query and identify which tasks from a provided list match the query.

Input Information:
1.  **User's Search Query:** "{USER_QUERY}"  
2.  **User's Task List:** A list of the user's current tasks, provided below in JSON format. Each task has an `id`, `description`, `title` (optional), `status` ('pending' or 'done'), and `due_date_utc_iso` (optional, in YYYY-MM-DDTHH:MM:SSZ format).
3.  **Current time in UTC:** {CURRENT_TIME_UTC_ISO}
User's Task List:
```json
{TASK_LIST_JSON}
```

Your Task:

1. Carefully read the "User's Search Query".
2. Examine the "User's Task List".
3. Identify all tasks from the list whose content (description, title) or properties (status, due date relative to current time) semantically match the user's query. Consider synonyms, different phrasings, and context. For example, if the query is "страховка", a task with "оформить полис" might be relevant. If the query is "задачи на завтра", filter tasks with a due_date_utc_iso corresponding to tomorrow relative to the Current time in UTC. If the query asks for "выполненные", filter by status: done.
4. Return ONLY a single JSON object containing a list of the integer ids of the matching tasks. The list should be empty if no tasks match.

Output JSON Format:
{{
  "matching_task_ids": [integer_id1, integer_id2, ...]
}}

CRITICAL: Do not include any explanations, summaries, or text other than the required JSON object with the list of IDs. If no tasks match, return {{ "matching_task_ids": [] }}.
Analyze the query and the task list, then return the JSON with the matching task IDs.
"""

GENERATE_TITLE_PROMPT_TEMPLATE = """
Create a concise title (summary) in Russian for the following task description.
The title should capture the main essence of the task.
The title MUST be short, ideally **no longer than {MAX_TITLE_LENGTH} characters**.
Use just 2-3 words that gives the main idea of the task. 
If can not find good title, just use one word that describes the description the best.

Task Description:
"{DESCRIPTION}"

If you can create a good summary title respecting the length limit, provide it directly.
If creating a good short summary is difficult, just return the first 5-6 words of the Task Description instead.
Do not add quotes around the title. Just return the title text.

Concise Title:
"""

