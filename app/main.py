import sys
import os
import threading
import logging
import uvicorn
from fastapi import FastAPI

# Добавляем корневую директорию в PYTHONPATH для прямого запуска
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
from app.api.endpoints import users, groups

# Глобальная переменная для предотвращения повторной инициализации
_services_initialized = False

app = FastAPI(title="AI Daily Tasks API")

# Роуты
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])


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
    global _services_initialized
    
    # Убираем блокировку для корректного перезапуска планировщика
    # if _services_initialized:
    #     logging.info("Сервисы уже инициализированы, пропускаем")
    #     return
    
    import os

    # Не запускать бота в процессе-ребутере uvicorn
    if os.environ.get("RUN_MAIN") == "true" or os.environ.get("UVICORN_RELOAD_PROCESS") == "true":
        return

    try:
        # Создание таблиц при первом запуске
        base.Base.metadata.create_all(bind=engine)
        logging.info("✅ База данных инициализирована")

        # Планировщик - ВСЕГДА переинициализируем для обновления расписания
        start_scheduler()

        # Telegram-бот - запускаем только если еще не запущен
        if not _services_initialized:
            threading.Thread(target=_run_telegram_bot, daemon=True).start()
            logging.info("✅ Telegram бот запущен в отдельном потоке")
        
        _services_initialized = True
        logging.info("✅ Все фоновые сервисы инициализированы")
        
    except Exception as e:
        logging.error(f"❌ Ошибка инициализации сервисов: {e}")


# --- События FastAPI -------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    """Запускается автоматически при старте FastAPI (uvicorn)"""
    _init_background_services()


# --- Возможность запуска как скрипта --------------------------------------

if __name__ == "__main__":
    _init_background_services()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)