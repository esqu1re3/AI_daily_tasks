import sqlite3
from pathlib import Path
from datetime import datetime
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/reports_backup.sqlite")

def create_new_users_table():
    """Создание новой таблицы пользователей"""
    conn = None
    try:
        # Создаем директорию если нужно
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Удаляем старую таблицу если существует
        cursor.execute("DROP TABLE IF EXISTS users")
        
        # Создаем новую таблицу с правильной структурой
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            telegram_id TEXT UNIQUE,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            last_response TEXT,
            has_responded_today BOOLEAN DEFAULT 0
        )
        """)
        
        conn.commit()
        logger.info("✅ Новая таблица users успешно создана")
        
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка работы с БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

def print_table_structure():
    """Выводим структуру таблицы"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            print("\n📋 Структура таблицы users:")
            cursor.execute("PRAGMA table_info(users)")
            for col in cursor.fetchall():
                print(f"  {col[1]:<20} {col[2]:<15} {'NOT NULL' if col[3] else 'NULL'}")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при проверке структуры: {e}")

if __name__ == "__main__":
    try:
        print("🔄 Создание базы данных для AI Daily Tasks...")
        
        # Создаем новую таблицу
        create_new_users_table()
        
        # Показываем результат
        print_table_structure()
        
        print("\n✅ Миграция завершена успешно!")
        print("\n📝 Теперь вы можете:")
        print("   1. Запустить админ панель: streamlit run admin_panel/dashboard.py")
        print("   2. Добавить пользователей через админ панель")
        print("   3. Запустить основное приложение: python -m app.main")
        
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)