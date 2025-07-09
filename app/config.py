# Настройки проекта (время опросов, API-ключи и пр.)
# app/config.py

# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     GEMINI_API_KEY: str
#     #GEMINI_MODEL: str = "gemini-1.5-pro"
#     GEMINI_MODEL: str = "gemini-2.5-flash"
#     TG_BOT_TOKEN: str

#     DATABASE_URL: str = "sqlite:///./sql_app.db"

#     class Config:
#         env_file = ".env"

# settings = Settings()  # <- импортируй это везде

from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Обязательные переменные (без значений по умолчанию)
    GEMINI_API_KEY: str = Field(..., min_length=1)
    TG_BOT_TOKEN: str = Field(..., min_length=1)
    
    # Опциональные переменные со значениями по умолчанию
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")
    DATABASE_URL: str = Field(default="sqlite:///./data/reports_backup.sqlite")
    ADMIN_ID: str | None = None  # Добавляем опциональное поле
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорировать лишние переменные в .env

settings = Settings()