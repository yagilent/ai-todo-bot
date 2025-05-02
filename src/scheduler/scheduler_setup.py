# src/scheduler/scheduler_setup.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
# from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore # Для персистентности джобов
from pytz import utc # Важно для APScheduler

logger = logging.getLogger(__name__)

# Можно настроить хранилище джобов (пока в памяти)
jobstores = {
    'default': MemoryJobStore()
    # 'default': SQLAlchemyJobStore(url=str(settings.database_url)) # Пример для БД
}
# job_defaults = {
#     'coalesce': False, # Не объединять запуски, если планировщик отстал
#     'max_instances': 3 # Максимум одновременных запусков одной джобы
# }

# Создаем экземпляр планировщика
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=utc) # Используем UTC!

async def setup_scheduler() -> AsyncIOScheduler:
    """Инициализирует и возвращает настроенный планировщик."""
    if not scheduler.running:
        # scheduler.start() # Не стартуем здесь, стартуем в bot.py после регистрации джобов
        logger.info("APScheduler initialized.")
    else:
        logger.warning("APScheduler is already running.")
    return scheduler

async def shutdown_scheduler():
    """Останавливает планировщик."""
    if scheduler.running:
        logger.info("Shutting down APScheduler...")
        scheduler.shutdown(wait=False) # wait=False чтобы не блокировать основной поток
        logger.info("APScheduler shut down.")
    else:
        logger.warning("APScheduler is not running.")