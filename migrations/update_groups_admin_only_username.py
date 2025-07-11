#!/usr/bin/env python3
"""
Миграция: изменение системы администраторов групп - только username
Удаляем admin_id и admin_full_name, делаем admin_username обязательным
"""

import sqlite3
import sys
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Путь к базе данных
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "reports_backup.sqlite"


def run_migration():
    """Основная функция миграции"""
    
    logger.info("🔄 Начинаем миграцию: изменение системы администраторов групп")
    
    if not DB_PATH.exists():
        logger.error(f"❌ База данных не найдена: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1. Проверяем существование таблицы groups
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups';")
        if not cursor.fetchone():
            logger.warning("⚠️ Таблица groups не найдена, миграция не нужна")
            conn.close()
            return True
        
        # 2. Проверяем текущую структуру таблицы
        cursor.execute("PRAGMA table_info(groups);")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        has_admin_id = 'admin_id' in columns
        has_admin_full_name = 'admin_full_name' in columns
        has_admin_username = 'admin_username' in columns
        
        logger.info(f"📊 Текущая структура: admin_id={has_admin_id}, admin_username={has_admin_username}, admin_full_name={has_admin_full_name}")
        
        if not has_admin_id and not has_admin_full_name and has_admin_username:
            logger.info("✅ Таблица уже имеет правильную структуру")
            conn.close()
            return True
        
        # 3. Проверяем есть ли группы с пустым admin_username
        cursor.execute("SELECT COUNT(*) FROM groups WHERE admin_username IS NULL OR admin_username = '';")
        groups_without_username = cursor.fetchone()[0]
        
        if groups_without_username > 0:
            logger.warning(f"⚠️ Найдено {groups_without_username} групп без admin_username")
            
            # Пытаемся установить дефолтные значения
            cursor.execute("""
                UPDATE groups 
                SET admin_username = 'admin_' || id 
                WHERE admin_username IS NULL OR admin_username = ''
            """)
            logger.info(f"🔄 Установлены дефолтные username для {groups_without_username} групп")
        
        # 4. Создаем новую таблицу с правильной структурой
        cursor.execute("""
            CREATE TABLE groups_new (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                admin_username VARCHAR NOT NULL,
                activation_token VARCHAR UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                morning_hour INTEGER DEFAULT 17,
                morning_minute INTEGER DEFAULT 30,
                timezone VARCHAR DEFAULT 'Asia/Bishkek'
            );
        """)
        logger.info("✅ Создана новая таблица groups_new")
        
        # 5. Копируем данные из старой таблицы в новую (только нужные поля)
        cursor.execute("""
            INSERT INTO groups_new (
                id, name, description, admin_username, activation_token, 
                is_active, created_at, morning_hour, morning_minute, timezone
            )
            SELECT 
                id, name, description, 
                COALESCE(admin_username, 'admin_' || id) as admin_username,
                activation_token, is_active, created_at, 
                morning_hour, morning_minute, timezone
            FROM groups;
        """)
        
        migrated_count = cursor.rowcount
        logger.info(f"📤 Скопировано {migrated_count} групп в новую таблицу")
        
        # 6. Удаляем старую таблицу и переименовываем новую
        cursor.execute("DROP TABLE groups;")
        cursor.execute("ALTER TABLE groups_new RENAME TO groups;")
        logger.info("🔄 Заменена старая таблица на новую")
        
        # 7. Создаем индексы для новой таблицы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_activation_token ON groups(activation_token);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_admin_username ON groups(admin_username);")
        logger.info("📊 Созданы индексы для новой таблицы")
        
        conn.commit()
        logger.info("✅ Миграция завершена успешно")
        
        # 8. Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM groups;")
        total_groups = cursor.fetchone()[0]
        
        cursor.execute("PRAGMA table_info(groups);")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        logger.info(f"📈 Результат миграции:")
        logger.info(f"   • Всего групп: {total_groups}")
        logger.info(f"   • Поля таблицы: {', '.join(new_columns)}")
        logger.info(f"   • Удалены поля: admin_id, admin_full_name")
        logger.info(f"   • admin_username теперь обязательное поле")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False


def verify_migration():
    """Проверка результатов миграции"""
    
    logger.info("🔍 Проверка результатов миграции")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(groups);")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        required_fields = ['id', 'name', 'admin_username', 'activation_token']
        removed_fields = ['admin_id', 'admin_full_name']
        
        success = True
        for field in required_fields:
            if field not in columns:
                logger.error(f"❌ Отсутствует обязательное поле: {field}")
                success = False
            else:
                logger.info(f"✅ Поле {field}: OK")
        
        for field in removed_fields:
            if field in columns:
                logger.error(f"❌ Поле {field} не было удалено")
                success = False
            else:
                logger.info(f"✅ Поле {field}: удалено")
        
        # Проверяем что admin_username не nullable
        admin_username_info = columns.get('admin_username')
        if admin_username_info and admin_username_info[3] == 0:  # notnull = 0
            logger.warning(f"⚠️ Поле admin_username может быть NULL (это нормально для SQLite)")
        
        # Проверяем данные
        cursor.execute("SELECT COUNT(*) FROM groups WHERE admin_username IS NULL OR admin_username = '';")
        null_usernames = cursor.fetchone()[0]
        
        if null_usernames > 0:
            logger.error(f"❌ Найдено {null_usernames} групп без admin_username")
            success = False
        else:
            logger.info("✅ Все группы имеют admin_username")
        
        conn.close()
        
        if success:
            logger.info("✅ Миграция прошла успешно, все проверки пройдены")
        else:
            logger.error("❌ Обнаружены проблемы в результате миграции")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки миграции: {e}")
        return False


def main():
    """Главная функция"""
    
    print("🔄 Миграция: изменение системы администраторов групп")
    print("=" * 60)
    
    # Запрашиваем подтверждение
    print("📝 Что будет сделано:")
    print("   • Удалены поля admin_id и admin_full_name из таблицы groups")
    print("   • admin_username станет обязательным полем")
    print("   • Группы без username получат дефолтные значения")
    print()
    
    confirm = input("Продолжить миграцию? (y/N): ")
    if confirm.lower() not in ['y', 'yes', 'да']:
        print("❌ Миграция отменена")
        return 1
    
    # Создаем резервную копию
    backup_path = DB_PATH.with_suffix('.sqlite.backup_groups_admin')
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"💾 Создана резервная копия: {backup_path}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось создать резервную копию: {e}")
        confirm_without_backup = input("Продолжить без резервной копии? (y/N): ")
        if confirm_without_backup.lower() not in ['y', 'yes', 'да']:
            return 1
    
    # Выполняем миграцию
    if run_migration():
        # Проверяем результат
        if verify_migration():
            print("\n" + "=" * 60)
            print("✅ Миграция завершена успешно!")
            print("✅ Теперь группы используют только admin_username")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("⚠️ Миграция выполнена, но есть предупреждения")
            print("=" * 60)
            return 0
    else:
        print("\n" + "=" * 60)
        print("❌ Миграция не удалась")
        if backup_path.exists():
            print(f"💾 Восстановите из резервной копии: {backup_path}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 