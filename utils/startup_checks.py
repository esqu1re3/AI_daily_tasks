from pathlib import Path
import subprocess
import sys


def check_env_file() -> bool:
    """Check if .env file exists and provide instructions if missing."""
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


def check_database() -> bool:
    """Ensure database exists, run migrations if needed."""
    db_path = Path("data/reports_backup.sqlite")
    if not db_path.exists():
        print("📊 База данных не найдена. Инициализируем...")
        try:
            subprocess.run([sys.executable, "migrations/init_users.py"], check=True)
            print("✅ База данных инициализирована")
        except subprocess.CalledProcessError:
            print("❌ Ошибка инициализации базы данных")
            return False
    return True
