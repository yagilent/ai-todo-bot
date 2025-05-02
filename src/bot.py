# src/bot.py

import asyncio
import logging
import sys

import pendulum

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
# ЗАГЛУШКА: Убери/настрой, если используешь другое хранилище FSM
# from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем объект настроек
from src.config import settings

# Импортируем роутеры

from src.tgbot.handlers.nlp_handler import nlp_router

from src.tgbot.handlers.find_tasks_commands import find_commands_router

from src.tgbot.handlers.task_manage import task_manage_router

from src.scheduler.scheduler_setup import setup_scheduler, shutdown_scheduler, scheduler # Импортируем сам объект scheduler
from src.scheduler.jobs import register_jobs

# Импортируем функции жизненного цикла SQLAlchemy и менеджер сессий
from src.database.db_session import lifespan_startup, lifespan_shutdown, sessionmanager

# Импортируем Middleware для сессий БД
from src.tgbot.middlewares.db_middleware import DbSessionMiddleware

logger = logging.getLogger(__name__)

# --- Функции жизненного цикла бота ---
async def set_bot_commands(bot: Bot):
    """Устанавливает команды, видимые в меню Telegram."""
    commands = [
        types.BotCommand(command="/today", description="Задачи на сегодня"),
        types.BotCommand(command="/tomorrow", description="Задачи на завтра"),
        types.BotCommand(command="/overdue", description="❗️ Просроченные задачи ❗️"),
    ]
    try:
        await bot.set_my_commands(commands, scope=types.BotCommandScopeDefault())
        logger.info("Bot commands set successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

async def on_startup(bot: Bot, dispatcher: Dispatcher):
    """Действия при старте бота: инициализация БД, установка команд."""
    logger.warning("--- Starting Bot ---")
    try:
        # Инициализация менеджера сессий БД (движок и фабрика)
        await lifespan_startup()
    except Exception as e:
        logger.critical(f"Bot startup failed due to DB init error: {e}", exc_info=True)
        sys.exit("Critical: Could not initialize database session manager.")


    try:
        # Получаем настроенный объект планировщика
        await setup_scheduler() # Инициализирует объект scheduler
        # Регистрируем джобы, передавая зависимости
        register_jobs(scheduler, bot, sessionmanager.session_factory)
        # Запускаем планировщик ПОСЛЕ регистрации джобов
        scheduler.start()
        logger.info("Scheduler started successfully.")
    except Exception as e:
         logger.error(f"Failed to setup or start scheduler: {e}", exc_info=True)
         # Решить, критично ли это для старта бота? Пока нет.


    # Установка команд в меню Telegram
    await set_bot_commands(bot)
    logger.warning("--- Bot has been started successfully ---")

async def on_shutdown(dispatcher: Dispatcher):
    """Действия при остановке бота: закрытие соединений."""
    logger.warning("--- Shutting down Bot ---")
    # Закрытие соединений с БД
    await lifespan_shutdown()

    await shutdown_scheduler()

    # Закрытие хранилища FSM (если используется не MemoryStorage)
    try:
        if dispatcher.storage and hasattr(dispatcher.storage, 'close'):
             await dispatcher.storage.close()
             logger.info("FSM storage closed.")
    except Exception as e:
        logger.error(f"Error closing FSM storage: {e}", exc_info=True)

    logger.warning("--- Bot has been shut down ---")

async def main():
    """Основная функция запуска бота."""
    logger.info("Initializing bot application...")

    try:
        pendulum.set_locale('ru')
        logger.info(f"Pendulum locale set to '{pendulum.get_locale()}'.")
    except Exception as e:
        # Обработка ошибки, если локаль 'ru' не поддерживается системой
        logger.warning(f"Could not set Pendulum locale to 'ru': {e}. Using default.")

    # Создаем объект Bot, используя токен из настроек
    # Обрати внимание на имя переменной в Settings: telegram_bot_token
    bot = Bot(token=settings.telegram_bot_token,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Создаем Dispatcher (по умолчанию с MemoryStorage для FSM)
    # storage = MemoryStorage()
    # dp = Dispatcher(storage=storage)
    dp = Dispatcher()

    # --- Регистрация Middleware ---
    # DbSessionMiddleware будет создавать сессию для каждого апдейта
    session_middleware = DbSessionMiddleware(session_pool=sessionmanager.session_factory)
    dp.update.middleware(session_middleware)
    logger.info("DbSessionMiddleware registered.")

    # Регистрируем обработчики жизненного цикла
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Подключаем роутеры для обработки команд и сообщений
    dp.include_router(find_commands_router)
    dp.include_router(nlp_router)
    dp.include_router(task_manage_router) 
    logger.info("Routers included.")

    # Пропускаем старые апдейты, чтобы бот не отвечал на сообщения,
    # пришедшие во время его отключения
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.debug("Dropped pending updates.")
    except Exception as e:
        # Игнорируем ошибку, если вебхук не был установлен
        logger.warning(f"Could not delete webhook (maybe not set): {e}")

    # Запускаем long polling
    logger.info("Starting polling...")
    try:
        # allowed_updates можно настроить для оптимизации, но пока получаем все типы
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Unhandled exception during polling: {e}", exc_info=True)
    finally:
        # Корректное завершение сессии бота при остановке
        logger.warning("Closing bot session...")
        await bot.session.close()
        logger.warning("Bot session closed.")


if __name__ == '__main__':
    # Настройка базового логирования (можно улучшить, например, с Loguru)
    # logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Логирование уже настроено в config.py при импорте settings

    # Запуск асинхронной функции main
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user or system signal.")
    except Exception as e:
        # Ловим любые другие критические ошибки на самом верхнем уровне
        logger.critical(f"Critical error during bot execution: {e}", exc_info=True)
        sys.exit(1) # Выход с кодом ошибки