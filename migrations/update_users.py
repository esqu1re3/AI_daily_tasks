import sqlite3
from datetime import datetime

def update_users_table():
    conn = sqlite3.connect('your_database.db')  # Укажите ваш путь к БД
    cursor = conn.cursor()
    
    try:
        # Добавляем недостающие колонки
        cursor.execute("""
        ALTER TABLE users ADD COLUMN created_at TIMESTAMP
        """)
        
        cursor.execute("""
        ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE
        """)
        
        # Приводим типы к единому формату
        cursor.execute("""
        ALTER TABLE users ALTER COLUMN telegram_id TYPE TEXT
        """)
        
        cursor.execute("""
        ALTER TABLE users ALTER COLUMN full_name TYPE TEXT
        """)
        
        conn.commit()
        print(f"[{datetime.now()}] Таблица users успешно обновлена")
        
        # Проверяем структуру
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("\nОбновленная структура users:")
        for col in columns:
            print(f"{col[1]} ({col[2]})")
            
    except Exception as e:
        print(f"Ошибка при обновлении: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_users_table()