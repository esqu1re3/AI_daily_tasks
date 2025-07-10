# Модель пользователя (сотрудника)
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=True)  # Telegram User ID (nullable до активации)
    username = Column(String, unique=True, nullable=True)  # @username (может отсутствовать)
    full_name = Column(String, nullable=True)  # заполняется автоматически при первом сообщении
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # подтвержден ли пользователь (активирован ли)
    is_group_member = Column(Boolean, default=True)  # является ли участником группы
    last_response = Column(String, nullable=True)  # последний ответ на утренний вопрос
    has_responded_today = Column(Boolean, default=False)  # ответил ли сегодня
    activation_token = Column(String, nullable=True, index=True)  # токен для активации через диплинк

