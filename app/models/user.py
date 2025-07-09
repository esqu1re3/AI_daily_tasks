# Модель пользователя (сотрудника)
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)  # @username без @
    telegram_id = Column(String, unique=True, nullable=True)  # заполняется после первого сообщения
    full_name = Column(String, nullable=True)  # заполняется автоматически при первом сообщении
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_response = Column(String, nullable=True)  # последний ответ на утренний вопрос
    has_responded_today = Column(Boolean, default=False)  # ответил ли сегодня
