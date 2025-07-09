import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path
import logging

# Настройки страницы
st.set_page_config(
    page_title="AI Daily Tasks — Админка",
    page_icon="👥",
    layout="wide"
)

# Путь к базе данных
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "reports_backup.sqlite"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Создание базы данных и таблиц если они не существуют"""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            last_response TEXT,
            has_responded_today BOOLEAN DEFAULT 0
        )
        """)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return False

def load_users():
    """Загрузка пользователей из базы данных"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql_query("SELECT * FROM users ORDER BY created_at DESC", conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователей: {e}")
        return pd.DataFrame()

def add_user(user_id):
    """Добавление нового пользователя"""
    try:
        # Убираем лишние символы и проверяем что это число
        user_id = str(user_id).strip()
        
        if not user_id:
            return False, "User ID не может быть пустым"
        
        # Проверяем что это число
        try:
            int(user_id)
        except ValueError:
            return False, "User ID должен быть числом"
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (user_id, is_active) VALUES (?, 1)",
            (user_id,)
        )
        
        conn.commit()
        conn.close()
        return True, f"Пользователь с ID {user_id} успешно добавлен"
    except sqlite3.IntegrityError:
        return False, "Пользователь с таким ID уже существует"
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        return False, f"Ошибка: {str(e)}"

def update_user_status(user_id, is_active):
    """Обновление статуса пользователя"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (is_active, user_id)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления статуса: {e}")
        return False

def delete_user(user_id):
    """Удаление пользователя"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя: {e}")
        return False

def reset_daily_responses():
    """Сброс флагов ответов на новый день"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET has_responded_today = 0, last_response = NULL")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сброса ответов: {e}")
        return False

# Инициализация БД
if not init_database():
    st.error("❌ Ошибка подключения к базе данных!")
    st.stop()

# ======================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ======================
st.title("👥 AI Daily Tasks — Управление пользователями")
st.caption("Добавляйте пользователей по @username для получения утренних планов")

# Разделяем на вкладки
tab1, tab2, tab3 = st.tabs(["👤 Пользователи", "➕ Добавить", "📊 Статистика"])

with tab1:
    st.subheader("Список пользователей")
    
    # Кнопка обновления
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 Обновить список", type="primary"):
            st.rerun()
    with col2:
        if st.button("🔄 Сбросить ответы дня", help="Сбрасывает флаги ответов для нового дня"):
            if reset_daily_responses():
                st.success("Ответы сброшены!")
                st.rerun()
            else:
                st.error("Ошибка сброса ответов")
    
    # Загрузка и отображение пользователей
    users_df = load_users()
    
    if users_df.empty:
        st.info("👤 Пользователи не найдены. Добавьте первого пользователя!")
    else:
        st.write(f"**Всего пользователей:** {len(users_df)}")
        
        # Отображение таблицы с возможностью управления
        for idx, user in users_df.iterrows():
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
                
                with col1:
                    status_icon = "✅" if user['is_active'] else "❌"
                    st.write(f"{status_icon} **ID: {user['user_id']}**")
                    if user['username']:
                        st.caption(f"@{user['username']}")
                    if user['full_name']:
                        st.caption(f"👤 {user['full_name']}")
                
                with col2:
                    st.write(f"📱 ID: {user['user_id']}")
                    if user['username']:
                        st.write(f"👤 @{user['username']}")
                
                with col3:
                    response_icon = "✅" if user['has_responded_today'] else "⏳"
                    st.write(f"{response_icon} Ответ сегодня")
                    if user['last_response']:
                        with st.expander("Последний ответ"):
                            st.text(user['last_response'][:200] + "..." if len(user['last_response']) > 200 else user['last_response'])
                
                with col4:
                    new_status = not user['is_active']
                    action_text = "Активировать" if new_status else "Деактивировать"
                    if st.button(action_text, key=f"toggle_{user['id']}"):
                        if update_user_status(user['id'], new_status):
                            st.success(f"Статус обновлен!")
                            st.rerun()
                        else:
                            st.error("Ошибка обновления")
                
                with col5:
                    if st.button("🗑️", key=f"delete_{user['id']}", help="Удалить пользователя"):
                        if delete_user(user['id']):
                            st.success("Пользователь удален!")
                            st.rerun()
                        else:
                            st.error("Ошибка удаления")
                
                st.divider()

with tab2:
    st.subheader("➕ Добавить пользователя")
    
    with st.form("add_user_form"):
        st.write("Введите User ID пользователя Telegram")
        user_id_input = st.text_input(
            "User ID", 
            placeholder="123456789 или 987654321",
            help="Введите User ID пользователя Telegram"
        )
        
        submitted = st.form_submit_button("Добавить пользователя", type="primary")
        
        if submitted:
            if user_id_input:
                success, message = add_user(user_id_input)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Введите User ID пользователя!")

with tab3:
    st.subheader("📊 Статистика")
    
    users_df = load_users()
    if not users_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Всего пользователей", len(users_df))
        
        with col2:
            active_users = len(users_df[users_df['is_active'] == 1])
            st.metric("Активных", active_users)
        
        with col3:
            users_with_username = len(users_df[users_df['username'].notna()])
            st.metric("С username", users_with_username)
        
        with col4:
            responded_today = len(users_df[users_df['has_responded_today'] == 1])
            st.metric("Ответили сегодня", responded_today)
        
        # График активности
        if 'created_at' in users_df.columns:
            users_df['created_at'] = pd.to_datetime(users_df['created_at'])
            daily_registrations = users_df.groupby(users_df['created_at'].dt.date).size()
            
            if len(daily_registrations) > 0:
                st.subheader("📈 Регистрации по дням")
                st.line_chart(daily_registrations)

# Боковая панель с информацией
with st.sidebar:
    st.header("ℹ️ Информация")
    st.write("""
    **Как это работает:**
    
    1. 👤 Добавьте пользователей по User ID
    2. 🤖 Бот отправит им сообщение в 17:57 (Бишкек)
    3. ⏳ Ждет ответов от всех пользователей
    4. 🧠 Gemini создает сводку планов
    5. 📬 Админ получает общий отчет
    
    **Как получить User ID:**
    - Напишите @userinfobot в Telegram
    - Или попросите пользователя переслать сообщение боту @JsonDumpBot
    """)
    
    st.divider()
    
    st.write("**Время сервера:**")
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if st.button("🔧 Техническая информация"):
        st.info(f"База данных: {DB_PATH}")
        st.info(f"Статус БД: {'✅ Подключена' if DB_PATH.exists() else '❌ Не найдена'}")