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
            user_id TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
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

def validate_username(username):
    """Валидация username"""
    # Убираем @ если есть
    username = username.strip().lstrip('@')
    
    if not username:
        return False, "Username не может быть пустым"
    
    # Проверяем формат username (латиница, цифры, подчеркивания, минимум 5 символов)
    import re
    if not re.match(r'^[a-zA-Z0-9_]{5,}$', username):
        return False, "Username должен содержать только латинские буквы, цифры и подчеркивания (минимум 5 символов)"
    
    return True, username

def add_user(username):
    """Добавление нового пользователя по username"""
    try:
        # Валидируем username
        is_valid, result = validate_username(username)
        if not is_valid:
            return False, result
        
        clean_username = result
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (username, is_active, is_verified) VALUES (?, 1, 0)",
            (clean_username,)
        )
        
        conn.commit()
        conn.close()
        return True, f"Пользователь @{clean_username} добавлен. Попросите его написать боту /start для активации."
    except sqlite3.IntegrityError:
        return False, "Пользователь с таким username уже существует"
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
                    # Статус активности
                    activity_icon = "✅" if user['is_active'] else "❌"
                    # Статус верификации
                    verify_icon = "✅" if user['is_verified'] else "⏳"
                    
                    st.write(f"{activity_icon} **@{user['username']}**")
                    if user['full_name']:
                        st.caption(f"👤 {user['full_name']}")
                    if user['user_id']:
                        st.caption(f"ID: {user['user_id']}")
                
                with col2:
                    st.write(f"{verify_icon} Верификация")
                    if user['is_verified']:
                        st.write("🔗 Подключен к боту")
                    else:
                        st.write("⚠️ Не активирован")
                        st.caption("Нужно написать боту /start")
                
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
    
    # Инициализация session state для уведомлений и управления формой
    if 'success_message' not in st.session_state:
        st.session_state.success_message = None
    if 'error_message' not in st.session_state:
        st.session_state.error_message = None
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
    
    # Показываем уведомления если есть
    if st.session_state.success_message:
        success_col1, success_col2 = st.columns([4, 1])
        with success_col1:
            st.success(st.session_state.success_message)
        with success_col2:
            if st.button("✕", key="close_success", help="Закрыть уведомление"):
                st.session_state.success_message = None
                st.rerun()
    
    if st.session_state.error_message:
        error_col1, error_col2 = st.columns([4, 1])
        with error_col1:
            st.error(st.session_state.error_message)
        with error_col2:
            if st.button("✕", key="close_error", help="Закрыть уведомление"):
                st.session_state.error_message = None
                st.rerun()
    
    # Используем динамический ключ для формы, чтобы очистить поля после успешного добавления
    with st.form(key=f"add_user_form_{st.session_state.form_key}"):
        st.write("Введите @username пользователя Telegram")
        
        username_input = st.text_input(
            "Username", 
            placeholder="@john_doe или john_doe",
            help="Введите username пользователя Telegram (с @ или без)"
        )
        
        submitted = st.form_submit_button("Добавить пользователя", type="primary")
        
        if submitted:
            if username_input.strip():
                success, message = add_user(username_input.strip())
                if success:
                    # Сохраняем сообщение об успехе и увеличиваем ключ формы для очистки
                    st.session_state.success_message = message
                    st.session_state.error_message = None
                    st.session_state.form_key += 1  # Это приведет к очистке формы
                    st.rerun()
                else:
                    # Сохраняем сообщение об ошибке
                    st.session_state.error_message = message
                    st.session_state.success_message = None
                    st.rerun()
            else:
                st.session_state.error_message = "Введите username пользователя!"
                st.session_state.success_message = None
                st.rerun()

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
            verified_users = len(users_df[users_df['is_verified'] == 1])
            st.metric("Подключенных к боту", verified_users)
        
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
    
    1. 👤 Добавьте пользователей по @username
    2. 🔗 Пользователи должны написать боту /start
    3. 🤖 Бот отправит им сообщение в 9:00
    4. ⏳ Ждет ответов от всех пользователей
    5. 🧠 Gemini создает сводку планов
    6. 📬 Админ получает общий отчет
    
    **Новая система добавления:**
    - Добавляйте пользователей по @username
    - Система автоматически свяжет username с user_id при первом контакте
    - Только верифицированные пользователи получают утренние сообщения
    """)
    
    st.divider()
    
    st.write("**Время сервера:**")
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if st.button("🔧 Техническая информация"):
        st.info(f"База данных: {DB_PATH}")
        st.info(f"Статус БД: {'✅ Подключена' if DB_PATH.exists() else '❌ Не найдена'}")