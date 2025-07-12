#!/usr/bin/env python3
"""
Миграция для добавления системы групп в AI Daily Tasks
Добавляет таблицу groups и поле group_id в таблицу users
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging
import sys
import secrets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/reports_backup.sqlite")

def create_groups_table():
    """Создание таблицы groups для системы команд/групп"""
    conn = None
    try:
        # Проверяем существование основной БД
        if not DB_PATH.exists():
            logger.error("❌ База данных не найдена. Сначала запустите migrations/init_users.py")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы groups
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("✅ Таблица groups уже существует")
        else:
            # Создаем таблицу groups
            logger.info("📊 Создание таблицы groups...")
            cursor.execute("""
            CREATE TABLE groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                admin_id TEXT NOT NULL,
                admin_username TEXT,
                admin_full_name TEXT,
                activation_token TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                morning_hour INTEGER DEFAULT 17,
                morning_minute INTEGER DEFAULT 30,
                timezone TEXT DEFAULT 'Asia/Bishkek',
                days_of_week TEXT DEFAULT '0,1,2,3,4' NOT NULL
            )
            """)
            
            # Создаем индексы для таблицы groups
            cursor.execute("CREATE INDEX idx_groups_admin_id ON groups(admin_id)")
            cursor.execute("CREATE UNIQUE INDEX idx_groups_activation_token ON groups(activation_token)")
            cursor.execute("CREATE INDEX idx_groups_is_active ON groups(is_active)")
            
            logger.info("✅ Таблица groups создана с индексами")
        
        # Проверяем наличие поля group_id в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'group_id' not in columns:
            logger.info("📊 Добавление поля group_id в таблицу users...")
            cursor.execute("ALTER TABLE users ADD COLUMN group_id INTEGER REFERENCES groups(id)")
            cursor.execute("CREATE INDEX idx_users_group_id ON users(group_id)")
            logger.info("✅ Поле group_id добавлено в таблицу users")
        else:
            logger.info("✅ Поле group_id уже существует в таблице users")
        
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка работы с БД: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def create_default_group():
    """Создание группы по умолчанию для существующих пользователей (отключено)"""
    # ОТКЛЮЧЕНО: больше не создаем группу "Основная команда" автоматически
    # Администратор должен создать группы самостоятельно через админ-панель
    logger.info("✅ Автоматическое создание группы по умолчанию отключено")
    logger.info("💡 Создайте группы через админ-панель: вкладка 'Группы' → 'Создать новую группу'")
    return True

def print_migration_results():
    """Выводим результаты миграции"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Показываем структуру таблиц
            print(f"\n📋 Результаты миграции:")
            
            # Информация о группах
            cursor.execute("SELECT COUNT(*) FROM groups")
            groups_count = cursor.fetchone()[0]
            print(f"📊 Групп в системе: {groups_count}")
            
            if groups_count > 0:
                cursor.execute("SELECT id, name, admin_full_name, activation_token FROM groups")
                groups = cursor.fetchall()
                print(f"\n📋 Существующие группы:")
                for group in groups:
                    token_preview = group[3][:8] + "..." if group[3] else "None"
                    print(f"  ID {group[0]}: {group[1]} (Админ: {group[2] or 'N/A'}, Токен: {token_preview})")
            
            # Информация о пользователях
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1")
            verified_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1 AND group_id IS NOT NULL")
            users_with_group = cursor.fetchone()[0]
            
            print(f"\n👥 Активированных пользователей: {verified_users}")
            print(f"👥 Пользователей с группой: {users_with_group}")
            
            # Показываем структуру новых таблиц
            print(f"\n📋 Структура таблицы groups:")
            cursor.execute("PRAGMA table_info(groups)")
            for col in cursor.fetchall():
                print(f"  {col[1]:<20} {col[2]:<15} {'NOT NULL' if col[3] else 'NULL'}")
                
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при проверке результатов: {e}")

def main():
    """Основная функция миграции"""
    try:
        print("🔄 Миграция: добавление системы групп...")
        
        # Создаем таблицу groups и обновляем users
        if not create_groups_table():
            print("❌ Ошибка создания таблицы groups")
            sys.exit(1)
        
        # Создаем группу по умолчанию для существующих пользователей
        if not create_default_group():
            print("❌ Ошибка создания группы по умолчанию")
            sys.exit(1)
        
        # Показываем результат
        print_migration_results()
        
        print("\n✅ Миграция системы групп завершена успешно!")
        print("\n📝 Добавленные возможности:")
        print("   • Система групп с отдельными администраторами")
        print("   • Уникальные токены активации для каждой группы")
        print("   • Настройки времени рассылки для каждой группы")
        print("   • Автоматическое создание группы по умолчанию")
        
        print("\n📝 Следующие шаги:")
        print("   1. Добавьте API эндпоинты для управления группами")
        print("   2. Обновите админ панель для управления группами")
        print("   3. Обновите логику бота для работы с группами")
        print("   4. Обновите планировщик для рассылки по группам")
        
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 