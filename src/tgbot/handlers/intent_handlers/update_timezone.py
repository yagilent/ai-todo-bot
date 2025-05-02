# src/tgbot/handlers/intent_handlers/update_timezone.py
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from src.database.crud import update_user_timezone
from src.database.models import User
from src.llm.gemini_client import parse_timezone_from_text

logger = logging.getLogger(__name__)

async def handle_update_timezone(
    message: types.Message,
    session: AsyncSession,
    db_user: User,
    params: dict
):
    """Обрабатывает распознанное намерение обновить таймзону."""
    # ... (весь код функции handle_update_timezone_intent) ...
    location_text = params.get("location_text")
    user_telegram_id = db_user.telegram_id
    if not location_text:
        # ... (обработка ошибки) ...
        return

    logger.info(f"Handling update_timezone intent for user {user_telegram_id}. Text: '{location_text}'")
    parsed_timezone_iana = await parse_timezone_from_text(location_text)

    if parsed_timezone_iana:
        try:
            pytz.timezone(parsed_timezone_iana)
            await update_user_timezone(
                session=session,
                telegram_id=user_telegram_id,
                timezone=parsed_timezone_iana,
                timezone_text=location_text
            )
            logger.info(f"Timezone updated via intent for user {user_telegram_id} to {parsed_timezone_iana}")
            await message.reply(f"✅ Ваш часовой пояс обновлен на: {parsed_timezone_iana}")
        except pytz.UnknownTimeZoneError:
             # ... (обработка ошибки) ...
             await message.reply("🤔 Не удалось распознать валидную таймзону...")
        except Exception as e:
             # ... (обработка ошибки) ...
             await message.reply("Произошла ошибка при сохранении таймзоны.")
    else:
        # ... (обработка ошибки) ...
        await message.reply("😕 Не удалось распознать часовой пояс...")