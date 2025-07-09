import threading
import logging
import uvicorn
from fastapi import FastAPI

from app.services.scheduler import start_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
from app.core.database import engine
from app.models import base
from app.api.endpoints import users, reports, admin


app = FastAPI(title="AI Daily Tasks API")

# Роуты
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


# --- Базовый эндпоинт
@app.get("/")
async def root():
    return {"message": "Добро пожаловать в AI Daily Tasks API"}


# --- Функции инициализации -----------------------------------------------

def _run_telegram_bot():
    """Запуск Telegram-бота (в отдельном потоке)"""
    from app.core.telegram_bot import TelegramBot
    bot = TelegramBot()
    bot.run()


def _init_background_services():
    """Создание БД, запуск планировщика и бота"""
    import os

    # Не запускать бота в процессе-ребутере uvicorn
    if os.environ.get("RUN_MAIN") == "true" or os.environ.get("UVICORN_RELOAD_PROCESS") == "true":
        return

    # Создание таблиц при первом запуске
    base.Base.metadata.create_all(bind=engine)

    # Планировщик
    start_scheduler()

    # Telegram-бот
    threading.Thread(target=_run_telegram_bot, daemon=True).start()


# --- События FastAPI -------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    """Запускается автоматически при старте FastAPI (uvicorn)"""
    _init_background_services()


# --- Возможность запуска как скрипта --------------------------------------

if __name__ == "__main__":
    _init_background_services()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)