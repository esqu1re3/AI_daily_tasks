#!/usr/bin/env python3
"""
Запуск всей системы AI Daily Tasks: и админ панели, и основного приложения (бота)
"""
import subprocess
import sys
import signal
import time

processes = []

def run_process(cmd, name):
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, bufsize=1)

def main():
    try:
        print("Запуск админ панели (Streamlit)...")
        admin_proc = run_process([sys.executable, '-m', 'streamlit', 'run', 'admin_panel/dashboard.py'], 'admin_panel')
        processes.append(admin_proc)

        time.sleep(2)  # Даем админке стартануть

        print("Запуск основного приложения (бот + планировщик, с --reload)...")
        main_proc = run_process([
            sys.executable, '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8000'
        ], 'main_app')
        processes.append(main_proc)

        print("\nСистема запущена!\n- Админ панель: http://localhost:8501\n- API/бот: http://127.0.0.1:8000\n")
        print("Для остановки нажмите Ctrl+C")

        # Ожидание завершения любого процесса
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"Процесс {p.args} завершился с кодом {p.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nОстановка всех процессов...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
        print("Все процессы остановлены.")

if __name__ == "__main__":
    main() 