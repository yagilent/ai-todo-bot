# alembic/env.py
import os
import sys
import asyncio # Добавляем импорт asyncio
from logging.config import fileConfig

from sqlalchemy import pool
# Импортируем create_engine для offline режима, engine_from_config для online
from sqlalchemy import create_engine
from sqlalchemy import engine_from_config
# Импортируем тип для асинхронного движка SQLAlchemy
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context

# --- НАЧАЛО ИЗМЕНЕНИЙ ---
# Добавляем путь к нашему проекту в sys.path, чтобы импортировать src
# Путь строится относительно текущего файла env.py
project_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_dir)

# Импортируем настройки нашего приложения
# Предполагаем, что Settings инициализируется при импорте config.py
from src.config import settings
# Импортируем базовый класс наших моделей SQLAlchemy
# Важно: Модели должны быть определены и импортированы ДО использования Base.metadata
from src.database.models import Base
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# --- НАЧАЛО ИЗМЕНЕНИЙ ---
# Устанавливаем URL базы данных из наших настроек (используем вычисляемое поле)
# Убедись, что в settings.database_url_asyncpg строка начинается с 'postgresql+asyncpg://'
if not settings.database_url_asyncpg.startswith("postgresql+asyncpg://"):
     raise ValueError("DATABASE_URL in config must use the 'postgresql+asyncpg' driver for Alembic async support.")
# Для Alembic (и SQLAlchemy Core/ORM) нам нужен URL без '+asyncpg' для некоторых операций
sync_db_url = settings.database_url_asyncpg.replace("+asyncpg", "")
config.set_main_option('sqlalchemy.url', sync_db_url)
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# --- НАЧАЛО ИЗМЕНЕНИЙ ---
# Указываем Alembic на метаданные наших моделей
target_metadata = Base.metadata
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    # Используем синхронный URL для оффлайн режима
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata, # Указываем метаданные
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Добавляем поддержку соглашения об именовании для генерации имен ограничений
        compare_type=True, # Сравнивать типы данных
        render_as_batch=True, # Для поддержки SQLite и некоторых операций ALTER
        user_module_prefix='sa.', # Префикс для типов SQLAlchemy в генерируемом коде
        # naming_convention=Base.metadata.naming_convention # Передаем конвенцию
    )
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Helper function to run synchronous Alembic migrations."""
    # Передаем naming_convention в context.configure
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
        # naming_convention=Base.metadata.naming_convention # Передаем конвенцию
        )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    # Используем AsyncEngine для асинхронного подключения
    # Берем секцию конфигурации из alembic.ini
    connectable_config = config.get_section(config.config_ini_section, {})
    # Устанавливаем URL с asyncpg драйвером из наших настроек
    connectable_config['sqlalchemy.url'] = settings.database_url_asyncpg

    connectable = AsyncEngine(
        engine_from_config(
            connectable_config, # Передаем модифицированную конфигурацию
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True, # Обязательно для SQLAlchemy 2.0 async
        )
    )
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # Получаем асинхронное соединение
    async with connectable.connect() as connection:
        # Запускаем синхронный код миграций внутри run_sync
        await connection.run_sync(do_run_migrations)

    # Закрываем асинхронный движок
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Используем asyncio.run для запуска асинхронной функции run_migrations_online
    asyncio.run(run_migrations_online())