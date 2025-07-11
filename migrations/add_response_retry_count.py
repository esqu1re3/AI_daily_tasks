#!/usr/bin/env python3
"""
Миграция: Добавление поля response_retry_count в таблицу users
Добавляет поле для отслеживания количества попыток улучшить ответ пользователя
"""

import sqlite3
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Выполняет миграцию базы данных"""
    
    # Путь к базе данных (берем из конфигурации)
    db_path = Path(__file__).parent.parent / "data" / "reports_backup.sqlite"
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("🔄 Начинаем миграцию: добавление response_retry_count...")
        
        # Проверяем, существует ли уже поле
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'response_retry_count' in columns:
            logger.info("✅ Поле response_retry_count уже существует, миграция не требуется")
            return True
        
        # Добавляем новое поле
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN response_retry_count INTEGER DEFAULT 0
        """)
        
        # Обновляем все существующие записи (устанавливаем значение по умолчанию)
        cursor.execute("""
            UPDATE users 
            SET response_retry_count = 0 
            WHERE response_retry_count IS NULL
        """)
        
        # Сохраняем изменения
        conn.commit()
        
        logger.info("✅ Успешно добавлено поле response_retry_count в таблицу users")
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM users WHERE response_retry_count = 0")
        updated_count = cursor.fetchone()[0]
        logger.info(f"✅ Обновлено записей: {updated_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения миграции: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    logger.info("🚀 Запуск миграции добавления response_retry_count...")
    
    success = run_migration()
    
    if success:
        logger.info("🎉 Миграция успешно завершена!")
    else:
        logger.error("💥 Миграция завершилась с ошибкой!")
        exit(1) 