#!/usr/bin/env python3
"""
Запуск всей системы AI Daily Tasks: админ панели и основного приложения (бота)
"""
import subprocess
import sys
import signal
import time
import os
from pathlib import Path

processes = []

def check_env_file():
    """Проверка наличия .env файла с обязательными переменными"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("\n📝 Создайте файл .env со следующими переменными:")
        print("GEMINI_API_KEY=your_gemini_api_key_here")
        print("TG_BOT_TOKEN=your_telegram_bot_token_here")
        print("ADMIN_ID=your_telegram_user_id_here")
        print("GEMINI_MODEL=gemini-2.5-flash")
        print("\nИли скопируйте из примера:")
        print("cp docker.env.example .env")
        return False
    
    # Проверяем наличие обязательных переменных
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()
        
        required_vars = ['GEMINI_API_KEY', 'TG_BOT_TOKEN']
        missing_vars = []
        
        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=your_" in env_content:
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ В файле .env не настроены переменные: {', '.join(missing_vars)}")
            print("📝 Пожалуйста, укажите реальные значения вместо примеров")
            return False
        
        print("✅ Файл .env найден и настроен")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка чтения файла .env: {e}")
        return False

def check_database():
    """Проверка и инициализация базы данных"""
    db_path = Path("data/reports_backup.sqlite")
    
    if not db_path.exists():
        print("📊 База данных не найдена. Инициализируем...")
        try:
            # Сначала пробуем использовать новую миграцию инициализации
            init_script = Path("migrations/init_users.py")
            if init_script.exists():
                subprocess.run([sys.executable, str(init_script)], check=True)
                print("✅ База данных инициализирована")
            else:
                print("❌ Скрипт инициализации не найден")
                return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка инициализации базы данных: {e}")
            print("💡 Попробуйте запустить: python migrations/init_users.py")
            return False
    else:
        print("✅ База данных найдена")
        
        # Проверяем наличие всех необходимых таблиц
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['users', 'groups', 'user_responses']
            missing_tables = set(expected_tables) - set(tables)
            
            if missing_tables:
                print(f"⚠️ В базе данных отсутствуют таблицы: {', '.join(missing_tables)}")
                print("💡 Рекомендуется запустить миграции:")
                
                # Предлагаем запустить миграции
                if 'groups' in missing_tables:
                    print("   python migrations/add_groups_system.py")
                if 'user_responses' in missing_tables:
                    print("   python migrations/add_user_responses_table.py")
                
                conn.close()
                
                # Спрашиваем, продолжать ли
                response = input("Продолжить запуск без миграций? (y/n): ")
                if response.lower() not in ['y', 'yes', 'да']:
                    return False
            else:
                print("✅ Все необходимые таблицы найдены")
            
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки структуры БД: {e}")
            print("⚠️ Продолжаем запуск...")
    
    return True

def check_dependencies():
    """Проверка установленных зависимостей"""
    try:
        # Проверяем ключевые зависимости
        import streamlit
        import uvicorn
        import fastapi
        import telebot
        import google.generativeai
        print("✅ Основные зависимости установлены")
        return True
    except ImportError as e:
        print(f"❌ Отсутствует зависимость: {e}")
        print("💡 Установите зависимости: pip install -r requirements.txt")
        return False

def run_process(cmd, name):
    """Запуск процесса с правильным выводом"""
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, bufsize=1)

def main():
    print("🤖 AI Daily Tasks - Запуск системы")
    print("=" * 50)
    
    # Проверяем окружение
    print("🔍 Проверка окружения...")
    
    if not check_env_file():
        print("\n❌ Проверка .env файла не прошла")
        return 1
    
    if not check_dependencies():
        print("\n❌ Проверка зависимостей не прошла")
        return 1
    
    if not check_database():
        print("\n❌ Проверка базы данных не прошла")
        return 1
    
    print("✅ Все проверки пройдены!\n")
    
    try:
        print("🎛️ Запуск админ панели (Streamlit)...")
        admin_proc = run_process([
            sys.executable,
            '-m', 'streamlit', 'run', 'admin_panel/dashboard.py',
            '--server.address', '0.0.0.0',
            '--server.port', '8501',
            '--server.headless', 'true'
        ], 'admin_panel')
        processes.append(admin_proc)

        time.sleep(3)  # Даем админке время стартануть

        print("🚀 Запуск основного приложения (API + бот + планировщик)...")
        main_proc = run_process([
            sys.executable, '-m', 'uvicorn', 'app.main:app', 
            '--host', '0.0.0.0', '--port', '8000'
        ], 'main_app')
        processes.append(main_proc)

        print("\n" + "="*60)
        print("✅ Система AI Daily Tasks запущена успешно!")
        print("="*60)
        print("🌐 Админ панель:      http://localhost:8501")
        print("🌐 API сервер:       http://localhost:8000")
        print("📖 API документация: http://localhost:8000/docs")
        print("🤖 Telegram бот:     запущен в фоне")
        print("⏰ Планировщик:      запущен в фоне")
        print("="*60)
        print("💡 Отправьте ссылку активации участникам команды")
        print("⏹️  Для остановки нажмите Ctrl+C")
        print("="*60)

        # Ожидание завершения любого процесса
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\n⚠️ Процесс завершился с кодом {p.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n" + "="*40)
        print("⏹️ Остановка всех процессов...")
        print("="*40)
        
        for i, p in enumerate(processes):
            if p.poll() is None:
                try:
                    print(f"🛑 Останавливаем процесс {i+1}...")
                    p.terminate()
                    # Ждем 5 секунд для graceful shutdown
                    p.wait(timeout=5)
                    print(f"✅ Процесс {i+1} остановлен")
                except subprocess.TimeoutExpired:
                    print(f"⚡ Принудительно завершаем процесс {i+1}...")
                    p.kill()
                    print(f"✅ Процесс {i+1} принудительно завершен")
                except Exception as e:
                    print(f"⚠️ Ошибка остановки процесса {i+1}: {e}")
        
        print("✅ Все процессы остановлены")
        print("👋 До свидания!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 