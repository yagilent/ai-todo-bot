# src/database/models.py

import datetime
from typing import Optional, List

from sqlalchemy import (
    MetaData, BigInteger, Integer, String, Text,
    TIMESTAMP, Boolean, CheckConstraint, ForeignKey,
    DATE
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func # Для server_default=func.now()

# Соглашение об именовании (опционально, но полезно)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    metadata = metadata_obj

class User(Base):
    __tablename__ = "users"

    # Используем telegram_id как первичный ключ
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Убираем отдельное поле id
    # id: Mapped[int] = mapped_column(Integer, primary_key=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True) # Добавим username тоже
    timezone: Mapped[str] = mapped_column(String(64), default='UTC', nullable=False) # Сделаем не nullable, дефолт UTC
    timezone_text: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Связь с задачами (один пользователь - много задач)
    tasks: Mapped[List["Task"]] = relationship(back_populates="user")

    def __repr__(self):
        # Используем telegram_id в repr
        return f"<User(telegram_id={self.telegram_id}, name='{self.full_name}', tz='{self.timezone}')>"


# Модель таблицы Tasks
class Task(Base):
    __tablename__ = "tasks"

    # Основная информация о задаче
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default='pending', nullable=False, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Дата выполнения (если время не указано)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(DATE, index=True, nullable=True)
    # Дата и время выполнения (если время указано)
    due_datetime: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True), index=True, nullable=True)
    # Флаг, указывающий, какое поле использовать (due_date или due_datetime)
    has_time: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default='false')

    original_due_text: Mapped[Optional[str]] = mapped_column(String(255))

    # Информация о повторении
    is_repeating: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(255)) # RRULE

    # Информация о напоминаниях
    next_reminder_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP(timezone=True), index=True
    )
    last_reminder_sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Дополнительная информация
    raw_input: Mapped[Optional[str]] = mapped_column(Text)

    # Используем telegram_id пользователя как внешний ключ
    user_telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)

    # Определяем связь с моделью User
    user: Mapped["User"] = relationship(back_populates="tasks")


    # Ограничение на допустимые значения статуса
    __table_args__ = (
         CheckConstraint(status.in_(['pending', 'done']), name='ck_tasks_status_values'),
         # Можно добавить другие __table_args__ при необходимости
    )

    def __repr__(self):
        # Для удобного вывода при отладке
        return f"<Task(task_id={self.task_id}, user_id={self.user_id}, description='{self.description[:30]}...', status='{self.status}')>"