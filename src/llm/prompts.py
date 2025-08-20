# src/llm/prompts.py - НОВЫЕ КОРОТКИЕ ПРОМПТЫ

# УСТАРЕВШИЕ ДЛИННЫЕ ПРОМПТЫ УДАЛЕНЫ. Теперь используются короткие промпты с цепочкой вызовов.

# СТАРЫЙ ДЛИННЫЙ ПРОМПТ ДЛЯ ПАРСИНГА ДАТ УДАЛЕН - больше не используется

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


# src/llm/prompts.py - ДОБАВЛЯЕМ новые промпты, старые пока оставляем

# === НОВЫЕ УПРОЩЕННЫЕ ПРОМПТЫ ===

# 1. КОРОТКИЙ промпт для определения интента (вместо INTENT_RECOGNITION_PROMPT_TEMPLATE)
SIMPLE_INTENT_DETECTION_PROMPT = """
Analyze Russian text and return intent:

add_task - создать задачу/напоминание
find_tasks - найти/показать задачи  
complete_task - отметить выполненной (ТОЛЬКО при ответе на сообщение бота)
reschedule_task - изменить время напоминания (ТОЛЬКО при ответе на сообщение бота)
edit_task_description - изменить описание задачи (ТОЛЬКО при ответе на сообщение бота)
update_timezone - установить/изменить часовой пояс или местоположение
unknown - не понятно

ВАЖНО: Если это ответ на сообщение бота (reply=True), приоритет у контекстных интентов!

Examples for NEW tasks (reply=False):
"купить молоко завтра" → add_task
"напомни про встречу" → add_task
"напомни через час позвонить маме" → add_task

Examples for REPLIES to bot messages (reply=True):
"сделал" → complete_task
"готово" → complete_task
"выполнено" → complete_task

"перенеси на завтра" → reschedule_task
"отложи на вечер" → reschedule_task
"напомни через 3 часа" → reschedule_task
"сделаю в понедельник" → reschedule_task

"измени на купить хлеб и молоко" → edit_task_description
"поменяй описание на позвонить врачу" → edit_task_description
"добавь в описание что нужно взять документы" → edit_task_description
"уточни задачу: встреча с клиентом в офисе" → edit_task_description
"исправь на написать отчет по продажам" → edit_task_description
"смени текст" → edit_task_description

Examples for other intents:
"найди задачи про банк" → find_tasks
"я в Барселоне" → update_timezone
"переехал в Лондон" → update_timezone

Text: "{USER_TEXT}"
Is reply to bot message: {IS_REPLY}

Return only JSON: {{"intent": "add_task"}}
"""

# 2. Промпт для парсинга задачи (только для add_task)
TASK_PARSING_PROMPT = """
Parse task creation request. Extract:
1. Task description (what to do/remember) - include ALL context about when/where something happens
2. Reminder time (when user wants to be notified)

Rules:
- Put ALL details about time/place into description
- Reminder time = when user wants notification
- If no reminder time specified, return null

Examples:
"купить молоко завтра" → 
{{"description": "купить молоко", "reminder_time": "завтра"}}

"напомни вечером воскресенья про встречу в понедельник в 10:00" → 
{{"description": "встреча в понедельник в 10:00", "reminder_time": "воскресенье вечер"}}

"написать письмо в банк во вторник" →
{{"description": "написать письмо в банк", "reminder_time": "вторник"}}

"купить подарок маме" →
{{"description": "купить подарок маме", "reminder_time": null}}

Text: "{USER_TEXT}"

Return only JSON:
"""

# 3. Промпт для парсинга времени напоминания
REMINDER_TIME_PARSING_PROMPT = """
Convert reminder time text to specific datetime in UTC.

Current time: {CURRENT_DATETIME_ISO} in {USER_TIMEZONE}
Reminder text: "{REMINDER_TEXT}"

Rules:
- Always include specific time (hour:minute)
- If only date given, use smart defaults:
  - "утром" = 09:00
  - "днем"/"день" = 12:00  
  - "вечером" = 18:00
  - "ночью" = 21:00
  - No time specified = 12:00

Examples:
"завтра" → tomorrow at 12:00 in user timezone → convert to UTC
"вечером воскресенья" → next Sunday at 18:00 → convert to UTC
"через 2 часа" → current time + 2 hours → convert to UTC

Return only JSON:
{{"reminder_datetime_utc": "2025-01-15T10:00:00Z"}}
"""

# === ПРОМПТЫ ДЛЯ РЕКУРРЕНТНОСТИ (для будущего использования) ===

RECURRING_DETECTION_PROMPT = """
Analyze Russian text to detect if task contains recurring/repeating pattern.

Recurring indicators:
- "каждый день/неделю/месяц/год"
- "каждый понедельник/вторник..." 
- "каждые 2 недели/3 дня..."
- "15 числа каждого месяца"
- "раз в неделю/месяц"
- "ежедневно/еженедельно/ежемесячно"
- "по понедельникам/вторникам..."
- Anniversary patterns: "день рождения", "годовщина"

Examples:
"каждый понедельник встреча с командой" → {{"is_recurring": true, "pattern": "каждый понедельник"}}
"15 числа каждого месяца оплата интернета" → {{"is_recurring": true, "pattern": "15 числа каждого месяца"}}
"день рождения мамы 15 марта" → {{"is_recurring": true, "pattern": "15 марта каждый год"}}
"поливать цветы каждые 3 дня" → {{"is_recurring": true, "pattern": "каждые 3 дня"}}
"ежедневно принимать витамины" → {{"is_recurring": true, "pattern": "каждый день"}}
"раз в неделю уборка" → {{"is_recurring": true, "pattern": "каждую неделю"}}
"купить молоко завтра" → {{"is_recurring": false, "pattern": null}}
"сделать презентацию до пятницы" → {{"is_recurring": false, "pattern": null}}

Text: "{DESCRIPTION}"

Return only JSON:
{{"is_recurring": true/false, "pattern": "extracted pattern or null"}}
"""

RRULE_GENERATION_PROMPT = """
Convert Russian recurring pattern to RRULE format (RFC 5545 standard).

Current time: {CURRENT_TIME}
Recurring pattern: "{PATTERN}"

Day mapping: понедельник=MO, вторник=TU, среда=WE, четверг=TH, пятница=FR, суббота=SA, воскресенье=SU
Month mapping: январь=1, февраль=2, март=3, апрель=4, май=5, июнь=6, июль=7, август=8, сентябрь=9, октябрь=10, ноябрь=11, декабрь=12

Examples:
"каждый день" → "FREQ=DAILY"
"каждый понедельник" → "FREQ=WEEKLY;BYDAY=MO"
"каждые 3 дня" → "FREQ=DAILY;INTERVAL=3"
"каждые 2 недели" → "FREQ=WEEKLY;INTERVAL=2"
"15 числа каждого месяца" → "FREQ=MONTHLY;BYMONTHDAY=15"
"первый понедельник месяца" → "FREQ=MONTHLY;BYDAY=1MO"
"последний день месяца" → "FREQ=MONTHLY;BYMONTHDAY=-1"
"15 марта каждый год" → "FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15"
"каждую неделю" → "FREQ=WEEKLY"
"ежедневно" → "FREQ=DAILY"
"по понедельникам" → "FREQ=WEEKLY;BYDAY=MO"

Return only RRULE string (without "RRULE:" prefix) or null if cannot parse:
"""

# === ПРОМПТЫ ДЛЯ ДРУГИХ ИНТЕНТОВ ===

RESCHEDULE_TIME_EXTRACTION_PROMPT = """
Extract new reminder time from reschedule request text.

User wants to reschedule a task reminder. Extract when they want to be reminded.

Examples:
"перенеси на завтра" → {{"new_reminder_time": "завтра"}}
"отложи на вечер" → {{"new_reminder_time": "вечер"}}
"напомни через 3 часа" → {{"new_reminder_time": "через 3 часа"}}
"сделаю в понедельник" → {{"new_reminder_time": "понедельник"}}
"перенеси на завтра в 15:00" → {{"new_reminder_time": "завтра в 15:00"}}

Text: "{USER_TEXT}"

Return only JSON:
"""

EDIT_DESCRIPTION_EXTRACTION_PROMPT = """
Extract new task description from edit request.

Examples:
"измени на купить хлеб и молоко" → {{"new_description": "купить хлеб и молоко"}}
"поменяй описание на позвонить врачу" → {{"new_description": "позвонить врачу"}}
"добавь в описание что нужно взять документы" → {{"new_description": "взять документы"}}
"уточни задачу: встреча с клиентом в офисе" → {{"new_description": "встреча с клиентом в офисе"}}

Text: "{USER_TEXT}"

Return only JSON:
"""

