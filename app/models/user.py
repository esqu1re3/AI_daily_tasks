# Модель пользователя (сотрудника)
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default='CURRENT_TIMESTAMP')
    is_active = Column(Boolean, default=True)

    messages = relationship("Message", back_populates="user")
