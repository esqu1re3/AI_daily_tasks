# Модель истории ответов пользователей
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class UserResponse(Base):
    """Модель истории ответов пользователей на утренние вопросы.
    
    Хранит полную историю всех ответов каждого пользователя, что позволяет:
    - Просматривать историю ответов в админ панели
    - Анализировать активность пользователей
    - Восстанавливать данные при необходимости
    - Генерировать отчеты и статистику
    
    Attributes:
        id (int): Уникальный идентификатор записи ответа.
        user_id (int): Внешний ключ на таблицу users.
        response_text (str): Текст ответа пользователя.
        created_at (datetime): Дата и время отправки ответа.
        telegram_user_id (str): Telegram User ID для быстрого поиска.
        telegram_username (str): Telegram username на момент ответа.
        full_name (str): Полное имя пользователя на момент ответа.
    
    Examples:
        >>> # Создание новой записи ответа
        >>> response = UserResponse(
        ...     user_id=1,
        ...     response_text="Сегодня работаю над проектом X",
        ...     telegram_user_id="123456789",
        ...     telegram_username="john_doe",
        ...     full_name="John Doe"
        ... )
    """
    __tablename__ = "user_responses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    response_text = Column(Text, nullable=False)  # Используем Text для длинных ответов
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Дублируем данные пользователя для истории (на случай изменения профиля)
    telegram_user_id = Column(String, nullable=False)  # Telegram User ID
    telegram_username = Column(String, nullable=True)  # Username на момент ответа
    full_name = Column(String, nullable=True)  # Полное имя на момент ответа
    
    # Связь с таблицей users
    user = relationship("User", back_populates="responses") 