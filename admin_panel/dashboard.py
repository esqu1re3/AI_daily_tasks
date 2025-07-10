import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path
import logging
import secrets
import string
import requests

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

def generate_activation_token():
    """Генерация уникального токена активации"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

def get_bot_username():
    """Получение username бота через API"""
    try:
        response = requests.get("http://127.0.0.1:8000/users/bot/info", timeout=5)
        if response.status_code == 200:
            return response.json().get("bot_username", "your_bot")
        return "your_bot"
    except:
        return "your_bot"

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
            has_responded_today BOOLEAN DEFAULT 0,
            activation_token TEXT UNIQUE
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
        
        # Генерируем токен активации
        activation_token = generate_activation_token()
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (username, is_active, is_verified, activation_token) VALUES (?, 1, 0, ?)",
            (clean_username, activation_token)
        )
        
        conn.commit()
        conn.close()
        
        # Получаем username бота и формируем ссылку
        bot_username = get_bot_username()
        activation_link = f"https://t.me/{bot_username}?start={activation_token}"
        
        return True, f"Пользователь @{clean_username} добавлен!\n\nСсылка для активации:\n{activation_link}\n\nОтправьте эту ссылку пользователю любым удобным способом."
    except sqlite3.IntegrityError:
        return False, "Пользователь с таким username уже существует"
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        return False, f"Ошибка: {str(e)}"

def get_activation_link(user):
    """Получение ссылки активации для пользователя"""
    if user['activation_token']:
        bot_username = get_bot_username()
        return f"https://t.me/{bot_username}?start={user['activation_token']}"
    return None

def regenerate_activation_token(user_id):
    """Регенерация токена активации через API"""
    try:
        response = requests.post(f"http://127.0.0.1:8000/users/{user_id}/regenerate-token", timeout=5)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

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
                    st.write(f"{verify_icon} Статус")
                    if user['is_verified']:
                        st.write("🔗 Активирован")
                    else:
                        st.write("⚠️ Не активирован")
                        # Показываем ссылку активации для неактивированных пользователей
                        activation_link = get_activation_link(user)
                        if activation_link:
                            col_link1, col_link2 = st.columns([3, 1])
                            with col_link1:
                                if st.button("📋 Ссылка активации", key=f"link_{user['id']}"):
                                    st.code(activation_link, language=None)
                                    st.caption("Отправьте эту ссылку пользователю")
                            with col_link2:
                                if st.button("🔄", key=f"regen_{user['id']}", help="Регенерировать ссылку"):
                                    if regenerate_activation_token(user['id']):
                                        st.success("Новая ссылка сгенерирована!")
                                        st.rerun()
                                    else:
                                        st.error("Ошибка регенерации")
                
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
            st.metric("Активированных", verified_users)
        
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
    2. 📱 Отправьте ссылку активации пользователю
    3. 🔗 Пользователь переходит по ссылке и активируется
    4. 🤖 Бот отправит ему сообщение в 9:00
    5. ⏳ Ждет ответов от всех пользователей
    6. 🧠 Gemini создает сводку планов
    7. 📬 Админ получает общий отчет
    
    **Новая система активации:**
    - Система генерирует уникальную ссылку для каждого пользователя
    - Ссылка содержит токен активации
    - При переходе по ссылке пользователь автоматически активируется
    - Только активированные пользователи получают утренние сообщения
    """)
    
    st.divider()
    
    st.write("**Время сервера:**")
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if st.button("🔧 Техническая информация"):
        st.info(f"База данных: {DB_PATH}")
        st.info(f"Статус БД: {'✅ Подключена' if DB_PATH.exists() else '❌ Не найдена'}")
        st.info(f"Бот: @{get_bot_username()}")