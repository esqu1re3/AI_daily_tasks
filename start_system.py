#!/usr/bin/env python3
"""
Скрипт для запуска AI Daily Tasks системы
"""

import os
import sys
import subprocess
import argparse
from utils.startup_checks import check_env_file, check_database


def run_migration():
    """Запуск миграции базы данных"""
    print("🔄 Инициализация базы данных...")
    try:
        subprocess.run([sys.executable, "migrations/init_users.py"], check=True)
        print("✅ База данных инициализирована")
        return True
    except subprocess.CalledProcessError:
        print("❌ Ошибка инициализации базы данных")
        return False

def run_admin_panel():
    """Запуск админ панели"""
    print("🎛️ Запуск админ панели...")
    try:
        subprocess.run([
            "streamlit", "run", "admin_panel/dashboard.py",
            "--server.address", "0.0.0.0",
            "--server.port", "8501"
        ], check=True)
    except subprocess.CalledProcessError:
        print("❌ Ошибка запуска админ панели")
    except KeyboardInterrupt:
        print("\n⏹️ Админ панель остановлена")

def run_main_app():
    """Запуск основного приложения"""
    print("🚀 Запуск основного приложения...")
    try:
        subprocess.run([sys.executable, "-m", "app.main"], check=True)
    except subprocess.CalledProcessError:
        print("❌ Ошибка запуска приложения")
    except KeyboardInterrupt:
        print("\n⏹️ Приложение остановлено")

def main():
    parser = argparse.ArgumentParser(description="AI Daily Tasks - Управление системой")
    parser.add_argument("command", choices=["init", "admin", "start", "all"], 
                       help="Команда для выполнения")
    
    args = parser.parse_args()
    
    print("🤖 AI Daily Tasks - Система утренних планов команды")
    print("=" * 50)
    
    if args.command == "init":
        # Инициализация базы данных
        if not check_env_file():
            return 1
        if run_migration():
            print("\n✅ Система готова к работе!")
            print("\n📝 Следующие шаги:")
            print("1. python start_system.py admin  # Добавить пользователей")
            print("2. python start_system.py start  # Запустить систему")
        return 0
        
    elif args.command == "admin":
        # Запуск только админ панели
        if not check_env_file() or not check_database():
            return 1
        run_admin_panel()
        return 0
        
    elif args.command == "start":
        # Запуск основного приложения
        if not check_env_file() or not check_database():
            return 1
        run_main_app()
        return 0
        
    elif args.command == "all":
        # Полная инициализация и запуск
        if not check_env_file():
            return 1
        
        print("\n1. Инициализация базы данных...")
        if not run_migration():
            return 1
            
        print("\n2. Запуск админ панели для настройки...")
        print("   Откройте http://<ваш_IP>:8501 в браузере (или http://0.0.0.0:8501)")
        print("   Добавьте пользователей и нажмите Ctrl+C когда закончите")
        
        try:
            run_admin_panel()
        except KeyboardInterrupt:
            pass
            
        print("\n3. Запуск основного приложения...")
        run_main_app()
        return 0

if __name__ == "__main__":
    sys.exit(main()) 
