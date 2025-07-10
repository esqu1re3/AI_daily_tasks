# Модель пользователя (сотрудника)
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    """Модель пользователя системы AI Daily Tasks.
    
    Представляет участника команды в системе сбора утренних планов.
    Хранит информацию о пользователе, его статусе активации и ответах на вопросы.
    
    Поддерживает различные этапы жизненного цикла пользователя:
    - Создание записи при первом контакте
    - Активация через ссылку от администратора
    - Ежедневные ответы на утренние вопросы
    - Управление активностью администратором
    
    Attributes:
        id (int): Уникальный идентификатор записи в базе данных.
        user_id (str): Telegram User ID пользователя (заполняется при активации).
        username (str): Telegram username пользователя (может отсутствовать).
        full_name (str): Полное имя пользователя из Telegram профиля.
        created_at (datetime): Дата и время создания записи.
        is_active (bool): Флаг активности пользователя (управляется администратором).
        is_verified (bool): Флаг активации через ссылку (подтверждение участия).
        is_group_member (bool): Флаг принадлежности к команде.
        last_response (str): Последний ответ на утренний вопрос.
        has_responded_today (bool): Флаг ответа на сегодняшний вопрос.
        activation_token (str): Токен для активации через ссылку.
    
    Examples:
        >>> # Создание нового пользователя при активации
        >>> user = User(
        ...     user_id="123456789",
        ...     username="john_doe",
        ...     full_name="John Doe",
        ...     is_verified=True,
        ...     is_group_member=True
        ... )
        >>> # Пользователь готов получать утренние вопросы
    """
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
