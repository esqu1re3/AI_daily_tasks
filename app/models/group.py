# Модель группы (команды)
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from app.core.database import Base

class Group(Base):
    """Модель группы (команды) в системе AI Daily Tasks.
    
    Позволяет создавать отдельные команды с собственными администраторами,
    что обеспечивает масштабируемость системы для нескольких независимых команд.
    
    Каждая группа имеет:
    - Уникальное название и описание
    - Собственного администратора
    - Уникальный токен активации для участников
    - Настройки времени рассылки
    - Независимую систему сбора ответов и генерации сводок
    
    Attributes:
        id (int): Уникальный идентификатор группы.
        name (str): Название группы/команды.
        description (str): Описание группы.
        admin_id (str): Telegram User ID администратора группы.
        admin_username (str): Telegram username администратора.
        admin_full_name (str): Полное имя администратора.
        activation_token (str): Уникальный токен для активации участников.
        is_active (bool): Флаг активности группы.
        created_at (datetime): Дата создания группы.
        morning_hour (int): Час отправки вечерних сообщений (по умолчанию 17).
        morning_minute (int): Минута отправки вечерних сообщений (по умолчанию 30).
        timezone (str): Временная зона группы (по умолчанию Asia/Bishkek).
        members: Связь с участниками группы.
    
    Examples:
        >>> # Создание новой группы
        >>> group = Group(
        ...     name="Команда разработки",
        ...     description="Команда разработчиков проекта X",
        ...     admin_id="123456789",
        ...     admin_username="team_lead",
        ...     admin_full_name="John Smith"
        ... )
        >>> # Группа создана с автоматически сгенерированным токеном
    """
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # Название группы
    description = Column(Text, nullable=True)  # Описание группы
    
    # Информация об администраторе группы
    admin_id = Column(String, nullable=False)  # Telegram User ID администратора
    admin_username = Column(String, nullable=True)  # Telegram username администратора
    admin_full_name = Column(String, nullable=True)  # Полное имя администратора
    
    # Уникальный токен для активации участников
    activation_token = Column(String, unique=True, nullable=False, index=True)
    
    # Настройки группы
    is_active = Column(Boolean, default=True)  # Активна ли группа
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Настройки времени рассылки
    morning_hour = Column(Integer, default=17)  # Час рассылки (0-23)
    morning_minute = Column(Integer, default=30)  # Минута рассылки (0-59)
    timezone = Column(String, default="Asia/Bishkek")  # Временная зона
    
    # Связь с участниками группы
    members = relationship("User", back_populates="group", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Инициализация группы с автоматической генерацией токена активации."""
        super().__init__(**kwargs)
        if not self.activation_token:
            self.activation_token = self.generate_activation_token()

    @staticmethod
    def generate_activation_token():
        """Генерирует уникальный токен активации для группы.
        
        Returns:
            str: Уникальный токен длиной 32 символа.
        
        Examples:
            >>> token = Group.generate_activation_token()
            >>> print(len(token))
            32
        """
        return secrets.token_urlsafe(32)

    def get_activation_link(self, bot_username):
        """Формирует ссылку активации для участников группы.
        
        Args:
            bot_username (str): Username Telegram бота без символа @.
        
        Returns:
            str: Готовая ссылка для отправки участникам.
        
        Examples:
            >>> group = Group(name="My Team")
            >>> link = group.get_activation_link("my_bot")
            >>> print(link)
            https://t.me/my_bot?start=abc123...
        """
        return f"https://t.me/{bot_username}?start={self.activation_token}"

    def get_schedule_cron(self):
        """Возвращает cron-выражение для планировщика группы.
        
        Returns:
            dict: Параметры для APScheduler с временем рассылки группы.
        
        Examples:
            >>> group = Group(morning_hour=10, morning_minute=15)
            >>> cron = group.get_schedule_cron()
            >>> print(cron)
            {'hour': 10, 'minute': 15, 'timezone': 'Asia/Bishkek'}
        """
        return {
            'hour': self.morning_hour,
            'minute': self.morning_minute,
            'timezone': self.timezone
        }

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}', admin_id='{self.admin_id}', active={self.is_active})>" 