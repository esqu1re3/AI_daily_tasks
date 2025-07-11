#!/usr/bin/env python3
"""
Миграция для добавления таблицы user_responses
Добавляет систему истории ответов пользователей
"""

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

def create_user_responses_table():
    """Создание таблицы user_responses для хранения истории ответов"""
    conn = None
    try:
        # Проверяем существование основной БД
        if not DB_PATH.exists():
            logger.error("❌ База данных не найдена. Сначала запустите migrations/init_users.py")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы user_responses
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_responses'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("✅ Таблица user_responses уже существует")
            return True
        
        # Создаем таблицу user_responses
        logger.info("📊 Создание таблицы user_responses...")
        cursor.execute("""
        CREATE TABLE user_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            response_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            telegram_user_id TEXT NOT NULL,
            telegram_username TEXT,
            full_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """)
        
        # Создаем индексы для оптимизации запросов
        cursor.execute("CREATE INDEX idx_user_responses_user_id ON user_responses(user_id)")
        cursor.execute("CREATE INDEX idx_user_responses_telegram_user_id ON user_responses(telegram_user_id)")
        cursor.execute("CREATE INDEX idx_user_responses_created_at ON user_responses(created_at)")
        
        conn.commit()
        logger.info("✅ Таблица user_responses создана успешно")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка работы с БД: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def print_tables_structure():
    """Выводим структуру всех таблиц"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Получаем список всех таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                print(f"\n📋 Структура таблицы {table_name}:")
                cursor.execute(f"PRAGMA table_info({table_name})")
                for col in cursor.fetchall():
                    print(f"  {col[1]:<20} {col[2]:<15} {'NOT NULL' if col[3] else 'NULL'}")
                    
            # Показываем индексы
            print(f"\n📋 Индексы:")
            cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
            for index in cursor.fetchall():
                print(f"  {index[0]} -> {index[1]}")
                
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при проверке структуры: {e}")

def main():
    """Основная функция миграции"""
    try:
        print("🔄 Миграция: добавление таблицы user_responses...")
        
        # Создаем таблицу user_responses
        if create_user_responses_table():
            # Показываем результат
            print_tables_structure()
            
            print("\n✅ Миграция завершена успешно!")
            print("\n📝 Добавленные возможности:")
            print("   • Полная история ответов каждого пользователя")
            print("   • Хранение снимка профиля на момент ответа")
            print("   • Индексы для быстрого поиска по пользователям и датам")
            print("   • Автоматическое удаление истории при удалении пользователя")
            
            print("\n📝 Следующие шаги:")
            print("   1. Обновите bot_service.py для сохранения в новую таблицу")
            print("   2. Добавьте API эндпоинты для получения истории")
            print("   3. Обновите админ панель для отображения истории")
        else:
            print("❌ Ошибка миграции")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 