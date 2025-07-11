#!/usr/bin/env python3
"""
Полный сброс базы данных AI Daily Tasks
Удаляет старую базу и создает новую со всеми таблицами
"""
import sys
import os
from pathlib import Path
import sqlite3

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def remove_db_file():
    """Удаляет файл базы данных если он существует"""
    db_paths = [
        project_root / "data" / "reports_backup.sqlite",
        project_root / "reports_backup.sqlite",
        project_root / "app.db"
    ]
    
    removed_files = []
    for db_path in db_paths:
        if db_path.exists():
            try:
                db_path.unlink()
                removed_files.append(str(db_path))
                print(f"🗑️ Удален файл базы данных: {db_path}")
            except Exception as e:
                print(f"❌ Ошибка удаления {db_path}: {e}")
    
    if not removed_files:
        print("ℹ️ Файлы базы данных не найдены")
    
    return len(removed_files) > 0

def create_database_structure():
    """Создает новую базу данных со всеми таблицами"""
    try:
        # Импортируем модели и создаем все таблицы
        from app.core.database import engine, Base
        from app.models.user import User
        from app.models.user_response import UserResponse  
        from app.models.group import Group
        
        print("📊 Создание структуры базы данных...")
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        
        print("✅ Структура базы данных создана успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания структуры БД: {e}")
        return False

def create_default_group():
    """Создает группу по умолчанию для обратной совместимости"""
    try:
        from app.core.database import SessionLocal
        from app.models.group import Group
        from app.config import settings
        
        db = SessionLocal()
        
        # Проверяем, есть ли уже группы
        existing_groups = db.query(Group).count()
        if existing_groups > 0:
            print("ℹ️ Группы уже существуют, пропускаем создание группы по умолчанию")
            db.close()
            return True
        
        # Создаем группу по умолчанию
        admin_id = getattr(settings, 'ADMIN_ID', None)
        if not admin_id:
            print("⚠️ ADMIN_ID не настроен в .env, создаем группу с временным админом")
            admin_id = "000000000"  # Временный ID
        
        default_group = Group(
            name="Основная команда",
            description="Группа по умолчанию для существующих пользователей",
            admin_id=admin_id,
            admin_username="admin",
            admin_full_name="Администратор",
            morning_hour=17,
            morning_minute=30,
            timezone="Asia/Bishkek"
        )
        
        db.add(default_group)
        db.commit()
        
        group_id = default_group.id
        activation_token = default_group.activation_token
        
        print(f"✅ Создана группа по умолчанию (ID: {group_id})")
        print(f"🔗 Токен активации: {activation_token}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания группы по умолчанию: {e}")
        return False

def print_database_info():
    """Выводит информацию о созданной базе данных"""
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        from app.models.user_response import UserResponse
        from app.models.group import Group
        
        db = SessionLocal()
        
        # Считаем записи в таблицах
        users_count = db.query(User).count()
        responses_count = db.query(UserResponse).count()
        groups_count = db.query(Group).count()
        
        print("\n📊 Информация о базе данных:")
        print(f"   👥 Пользователи: {users_count}")
        print(f"   💬 Ответы: {responses_count}")
        print(f"   🏢 Группы: {groups_count}")
        
        # Показываем информацию о группах
        if groups_count > 0:
            print("\n🏢 Созданные группы:")
            groups = db.query(Group).all()
            for group in groups:
                print(f"   • {group.name} (ID: {group.id})")
                print(f"     Администратор: {group.admin_full_name or group.admin_username or group.admin_id}")
                print(f"     Расписание: {group.morning_hour:02d}:{group.morning_minute:02d} ({group.timezone})")
                print(f"     Ссылка активации: https://t.me/YOUR_BOT?start={group.activation_token}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о БД: {e}")

def verify_database():
    """Проверяет корректность созданной базы данных"""
    try:
        db_path = project_root / "data" / "reports_backup.sqlite"
        if not db_path.exists():
            print("❌ Файл базы данных не найден после создания")
            return False
        
        # Проверяем подключение к БД
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Проверяем существование таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['users', 'groups', 'user_responses']
        missing_tables = set(expected_tables) - set(tables)
        
        if missing_tables:
            print(f"❌ Отсутствуют таблицы: {', '.join(missing_tables)}")
            conn.close()
            return False
        
        print("✅ Все необходимые таблицы созданы")
        
        # Проверяем структуру таблиц
        for table in expected_tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            print(f"   📋 {table}: {len(columns)} столбцов")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки базы данных: {e}")
        return False

def main():
    """Основная функция сброса базы данных"""
    print("🔄 AI Daily Tasks - Сброс базы данных")
    print("=" * 50)
    
    # Удаляем подтверждение пользователя, всегда сбрасываем
    print("⚠️ Сброс базы данных будет выполнен без подтверждения пользователя!")
    
    print("\n🚀 Начинаем сброс базы данных...")
    
    # Шаг 1: Удаляем старые файлы БД
    print("\n1️⃣ Удаление старых файлов базы данных...")
    remove_db_file()
    
    # Шаг 2: Создаем структуру БД
    print("\n2️⃣ Создание новой структуры базы данных...")
    if not create_database_structure():
        print("❌ Не удалось создать структуру БД")
        sys.exit(1)
    
    # Шаг 3: Создаем группу по умолчанию
    print("\n3️⃣ Создание группы по умолчанию...")
    if not create_default_group():
        print("⚠️ Группа по умолчанию не создана, но это не критично")
    
    # Шаг 4: Проверяем результат
    print("\n4️⃣ Проверка результата...")
    if not verify_database():
        print("❌ Проверка базы данных не прошла")
        sys.exit(1)
    
    # Шаг 5: Выводим информацию
    print_database_info()
    
    print("\n✅ Сброс базы данных завершен успешно!")
    print("\n📝 Что дальше:")
    print("   1. Запустите систему: python run_all.py")
    print("   2. Отправьте ссылку активации участникам команды")
    print("   3. Проверьте админ панель: http://localhost:8501")
    
    db_path = project_root / "data" / "reports_backup.sqlite"
    print(f"\n📁 Файл базы данных: {db_path}")

if __name__ == "__main__":
    main() 