# Настройки проекта (время опросов, API-ключи и пр.)
# app/config.py

from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Обязательные переменные (без значений по умолчанию)
    GEMINI_API_KEY: str = Field(..., min_length=1)
    TG_BOT_TOKEN: str = Field(..., min_length=1)
    
    # Опциональные переменные со значениями по умолчанию
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")
    DATABASE_URL: str = Field(default="sqlite:///./data/reports_backup.sqlite")
    ADMIN_ID: str | None = None  # ID администратора для получения сводок
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорировать лишние переменные в .env

settings = Settings()
