# src/config.py

import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    """
    Класс для хранения настроек приложения.
    Загружает переменные из .env файла и системного окружения.
    """
    # Конфигурация модели Pydantic Settings
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore', # Игнорировать переменные в .env, не определенные в этой модели
    )

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    telegram_bot_token: str
    google_api_key: str
    log_level: str

    @computed_field
    @property
    def database_url_asyncpg(self) -> str: # Для асинхронных операций
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

settings = Settings()

logging.basicConfig(
    level=settings.log_level.upper(), # Устанавливаем уровень из настроек
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)
logger.info("Configuration loaded successfully via Pydantic.")
logger.debug(f"Logging level set to: {settings.log_level.upper()}")

# Для проверки можно добавить в конец файла:
# if __name__ == "__main__":
#    print(settings.model_dump()) # Используем model_dump() в Pydantic v2+
#    print(settings.database_url_psycopg)
#    print(settings.redis_url)