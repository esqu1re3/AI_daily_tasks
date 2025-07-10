import os
from pathlib import Path
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path("data/reports_backup.sqlite")

def remove_db_file():
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
            logger.info(f"✅ Файл базы данных {DB_PATH} удален.")
        except Exception as e:
            logger.error(f"❌ Не удалось удалить файл БД: {e}")
            return False
    else:
        logger.info(f"Файл базы данных {DB_PATH} не найден (ничего удалять не нужно)")
    return True

def create_empty_users_table():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            username TEXT UNIQUE,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            is_group_member BOOLEAN DEFAULT 1,
            last_response TEXT,
            has_responded_today BOOLEAN DEFAULT 0,
            activation_token TEXT
        )
        """)
        
        # Добавляем индекс для уникальности activation_token
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_activation_token ON users(activation_token) WHERE activation_token IS NOT NULL")
        
        conn.commit()
        conn.close()
        logger.info("✅ Пустая таблица users создана с актуальной структурой (включая activation_token)")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблицы users: {e}")
        return False

def main():
    print("🔄 Сброс базы данных AI Daily Tasks...")
    print("⚠️  Удаляю все данные в базе данных...")
    
    if remove_db_file():
        if create_empty_users_table():
            print("\n✅ База данных сброшена и готова к использованию!")
            print("\n📝 Структура таблицы users обновлена:")
            print("   - user_id: nullable (заполняется при активации)")
            print("   - username: nullable (может отсутствовать)")
            print("   - is_verified: поле для отслеживания активации")
            print("   - activation_token: токен для активации через ссылки")
            print("   - is_group_member: участие в команде")
        else:
            print("❌ Ошибка при создании новой таблицы users.")
    else:
        print("❌ Ошибка при удалении файла базы данных.")

if __name__ == "__main__":
    main() 
