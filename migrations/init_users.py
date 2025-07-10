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
    """Создание новой таблицы пользователей для системы активации"""
    conn = None
    try:
        # Создаем директорию если нужно
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы и её структуру
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            # Проверяем наличие новых полей
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Добавляем поле is_group_member если его нет
            if 'is_group_member' not in columns:
                logger.info("Добавляем поле is_group_member в существующую таблицу")
                cursor.execute("ALTER TABLE users ADD COLUMN is_group_member BOOLEAN DEFAULT 1")
                conn.commit()
                logger.info("✅ Поле is_group_member добавлено")
            
            # Добавляем поле activation_token если его нет
            if 'activation_token' not in columns:
                logger.info("Добавляем поле activation_token в существующую таблицу")
                cursor.execute("ALTER TABLE users ADD COLUMN activation_token TEXT")
                conn.commit()
                logger.info("✅ Поле activation_token добавлено")
            
            # Обновляем ограничения username (убираем NOT NULL, если есть)
            # В SQLite нельзя напрямую изменить ограничение, но можем проверить структуру
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            table_schema = cursor.fetchone()[0]
            
            if 'username TEXT UNIQUE NOT NULL' in table_schema:
                logger.info("Необходимо пересоздать таблицу для изменения ограничений username")
                # Создаем временную таблицу
                cursor.execute("""
                CREATE TABLE users_new (
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
                
                # Копируем данные
                cursor.execute("""
                INSERT INTO users_new 
                SELECT id, user_id, username, full_name, created_at, is_active, is_verified, 
                       COALESCE(is_group_member, 1), last_response, has_responded_today, activation_token
                FROM users
                """)
                
                # Удаляем старую таблицу
                cursor.execute("DROP TABLE users")
                
                # Переименовываем новую таблицу
                cursor.execute("ALTER TABLE users_new RENAME TO users")
                
                conn.commit()
                logger.info("✅ Таблица пересоздана с новой структурой")
            else:
                logger.info("✅ Структура таблицы уже актуальна")
        else:
            # Создаем новую таблицу с правильной структурой
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
            logger.info("✅ Новая таблица users создана")
        
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
        print("🔄 Обновление базы данных для AI Daily Tasks...")
        
        # Создаем/обновляем таблицу
        create_new_users_table()
        
        # Показываем результат
        print_table_structure()
        
        print("\n✅ Миграция завершена успешно!")
        print("\n📝 Возможности системы:")
        print("   • Участники активируются через ссылку от администратора")
        print("   • Username не обязателен (может отсутствовать)")
        print("   • Добавлено поле is_group_member")
        print("   • Система работает только через личные сообщения")
        print("\n📝 Следующие шаги:")
        print("   1. Запустить основное приложение: python -m app.main")
        print("   2. Отправить участникам ссылку: https://t.me/aidailytasksBot?start=group_activation")
        print("   3. Участники активируются самостоятельно")
        
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)
