# Базовая модель SQLAlchemy
from app.core.database import Base
from app.models.user import User
from app.models.report import Report

# Этот файл нужен, чтобы при запуске Base.metadata.create_all()
# все модели были зарегистрированы и таблицы были созданы.

__all__ = ["Base", "User", "Report"]
