#!/usr/bin/env python3
"""
Запуск всей системы AI Daily Tasks: и админ панели, и основного приложения (бота)
"""
import subprocess
import sys
import signal
import time
import os
from utils.startup_checks import check_env_file, check_database

processes = []

def run_process(cmd, name):
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, bufsize=1)

def main():
    print("🤖 AI Daily Tasks - Запуск системы")
    print("=" * 40)
    
    # Проверяем .env файл
    if not check_env_file():
        return 1
    
    # Проверяем и инициализируем базу данных
    if not check_database():
        return 1
    
    try:
        print("\n🎛️ Запуск админ панели (Streamlit)...")
        admin_proc = run_process([
            sys.executable,
            '-m', 'streamlit', 'run', 'admin_panel/dashboard.py',
            '--server.address', '0.0.0.0',
            '--server.port', '8501'
        ], 'admin_panel')
        processes.append(admin_proc)

        time.sleep(3)  # Даем админке стартануть

        print("🚀 Запуск основного приложения (бот + планировщик)...")
        main_proc = run_process([
            sys.executable, '-m', 'uvicorn', 'app.main:app', 
            '--host', '0.0.0.0', '--port', '8000'
        ], 'main_app')
        processes.append(main_proc)

        print("\n✅ Система запущена!")
        print("🌐 Админ панель: http://localhost:8501")
        print("🌐 API: http://localhost:8000")
        print("📖 API документация: http://localhost:8000/docs")
        print("\n⏹️ Для остановки нажмите Ctrl+C")

        # Ожидание завершения любого процесса
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\n⚠️ Процесс завершился с кодом {p.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹️ Остановка всех процессов...")
        for p in processes:
            if p.poll() is None:
                try:
                    p.terminate()
                    # Ждем 5 секунд для graceful shutdown
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Принудительно убиваем если не завершился
                    p.kill()
                except Exception:
                    pass
        print("✅ Все процессы остановлены.")
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 