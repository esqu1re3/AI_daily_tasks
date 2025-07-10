"""
Shared utility functions for AI Daily Tasks.

This module contains helper functions used across the application for common tasks
such as environment validation, database initialization, and system setup.
"""

import subprocess
import sys
from pathlib import Path


def check_env_file():
    """Проверяет наличие файла .env в корневой директории проекта.
    
    Выполняет валидацию конфигурации приложения перед запуском.
    При отсутствии файла выводит инструкции по созданию.
    
    Returns:
        bool: True если файл .env существует, False в противном случае.
    
    Examples:
        >>> if check_env_file():
        ...     print("Конфигурация готова")
        ... else:
        ...     print("Создайте файл .env")
        Конфигурация готова
    """
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("\n📝 Создайте файл .env со следующими переменными:")
        print("GEMINI_API_KEY=your_gemini_api_key_here")
        print("TG_BOT_TOKEN=your_telegram_bot_token_here")
        print("ADMIN_ID=your_telegram_user_id_here")
        print("\nИли скопируйте из примера:")
        print("cp docker.env.example .env")
        return False
    return True


def check_database():
    """Проверяет наличие базы данных SQLite.
    
    Проверяет существование файла базы данных в ожидаемом расположении.
    При отсутствии выводит инструкции по инициализации.
    
    Returns:
        bool: True если база данных существует, False в противном случае.
    
    Examples:
        >>> if check_database():
        ...     print("База данных готова")
        ... else:
        ...     print("Требуется инициализация")
        База данных готова
    """
    db_path = Path("data/reports_backup.sqlite")
    if not db_path.exists():
        print("❌ База данных не найдена!")
        print("\n🔧 Для инициализации запустите:")
        print("python migrations/init_users.py")
        return False
    return True


def init_database():
    """Инициализирует базу данных если она не существует.
    
    Автоматически запускает скрипт инициализации базы данных.
    Создает необходимую структуру таблиц для работы приложения.
    
    Returns:
        bool: True при успешной инициализации, False при ошибке.
    
    Raises:
        subprocess.CalledProcessError: При ошибке выполнения скрипта инициализации.
    
    Examples:
        >>> if init_database():
        ...     print("База данных инициализирована")
        ... else:
        ...     print("Ошибка инициализации")
        База данных инициализирована
    """
    db_path = Path("data/reports_backup.sqlite")
    if not db_path.exists():
        print("📊 База данных не найдена. Инициализируем...")
        try:
            subprocess.run([sys.executable, "migrations/init_users.py"], check=True)
            print("✅ База данных инициализирована")
            return True
        except subprocess.CalledProcessError:
            print("❌ Ошибка инициализации базы данных")
            return False
    return True


def run_migration():
    """Запускает миграцию базы данных.
    
    Выполняет скрипт инициализации/обновления структуры базы данных.
    Создает новые таблицы или обновляет существующие до актуальной схемы.
    
    Returns:
        bool: True при успешном выполнении миграции, False при ошибке.
    
    Raises:
        subprocess.CalledProcessError: При ошибке выполнения скрипта миграции.
    
    Examples:
        >>> if run_migration():
        ...     print("Миграция выполнена успешно")
        ... else:
        ...     print("Ошибка миграции")
        Миграция выполнена успешно
    """
    print("🔄 Инициализация базы данных...")
    try:
        subprocess.run([sys.executable, "migrations/init_users.py"], check=True)
        print("✅ База данных инициализирована")
        return True
    except subprocess.CalledProcessError:
        print("❌ Ошибка инициализации базы данных")
        return False