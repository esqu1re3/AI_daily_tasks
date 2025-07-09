# Подключение к SQLite через SQLAlchemy

from pathlib import Path
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Берём строку подключения из глобальных настроек приложения
from app.config import settings

# Если нужно, создаём директорию для файла базы данных
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    # Извлекаем путь к файлу (после последнего '/')
    sqlite_path = db_url.split("///")[-1]
    db_file = Path(sqlite_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

# Синхронный движок SQLAlchemy
engine = create_engine(db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Функция для получения сессии БД (добавьте это)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()