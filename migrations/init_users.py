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

def get_table_columns(cursor, table_name):
    """Получаем список колонок таблицы"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {col[1]: col for col in cursor.fetchall()}

def safe_migrate(conn):
    """Безопасная миграция с обработкой всех ошибок"""
    cursor = conn.cursor()
    
    # Шаг 1: Проверяем текущую структуру
    old_columns = get_table_columns(cursor, 'users')
    
    # Шаг 2: Удаляем временную таблицу, если она существует
    cursor.execute("DROP TABLE IF EXISTS users_new")
    conn.commit()
    
    # Шаг 3: Создаем новую таблицу с правильной структурой
    cursor.execute("""
    CREATE TABLE users_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT UNIQUE NOT NULL,
        username TEXT,
        full_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT (datetime('now')),
        is_active BOOLEAN DEFAULT 1
    )
    """)
    
    # Шаг 4: Переносим данные с преобразованием
    try:
        # Собираем доступные колонки
        available_columns = []
        if 'id' in old_columns:
            available_columns.append('id')
        if 'telegram_id' in old_columns:
            available_columns.append('telegram_id')
        if 'username' in old_columns:
            available_columns.append('username')
        if 'name' in old_columns:
            available_columns.append('name AS full_name')
        elif 'full_name' in old_columns:
            available_columns.append('full_name')
        else:
            available_columns.append("'Unknown' AS full_name")
        
        # Перенос данных
        if available_columns:
            cursor.execute(f"""
            INSERT INTO users_new (id, telegram_id, username, full_name)
            SELECT {', '.join(available_columns)} FROM users
            """)
        else:
            logger.warning("Не найдено подходящих колонок для переноса")
        
        # Шаг 5: Заменяем таблицы
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        conn.commit()
        logger.info("Миграция успешно завершена")
        
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Ошибка при переносе данных: {e}")
        raise

def create_users_table():
    """Основная функция создания/миграции таблицы"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("Начинаем миграцию существующей таблицы")
            safe_migrate(conn)
        else:
            logger.info("Создаем новую таблицу")
            cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now')),
                is_active BOOLEAN DEFAULT 1
            )
            """)
            conn.commit()
            logger.info("Новая таблица успешно создана")
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка работы с БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

def print_table_structure():
    """Выводим текущую структуру таблицы"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            print("\nТекущая структура users:")
            cursor.execute("PRAGMA table_info(users)")
            for col in cursor.fetchall():
                print(f"{col[1]:<15} {col[2]:<10} {'NOT NULL' if col[3] else ''}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при проверке структуры: {e}")

if __name__ == "__main__":
    try:
        # Создаем директорию если нужно
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Выполняем миграцию
        create_users_table()
        
        # Показываем результат
        print_table_structure()
        
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        sys.exit(1)