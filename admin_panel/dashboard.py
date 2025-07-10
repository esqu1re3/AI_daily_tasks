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
            username TEXT UNIQUE,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            is_group_member BOOLEAN DEFAULT 1,
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
st.title("👥 AI Daily Tasks — Управление командой")
st.caption("Система сбора утренних планов команды")

# Информационная панель
with st.container():
    st.info("""
    🔗 **Ссылка для активации участников команды:**
    
    `https://t.me/aidailytasksBot?start=group_activation`
    
    Отправьте эту ссылку участникам команды для активации в системе.
    """)

# Разделяем на вкладки
tab1, tab2 = st.tabs(["👤 Участники", "📊 Статистика"])

with tab1:
    st.subheader("Участники команды")
    
    # Кнопка обновления
    col1, col2 = st.columns([2, 1])
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
        st.info("👤 Нет участников. Отправьте ссылку активации участникам команды!")
    else:
        # Фильтруем только активированных участников
        activated_users = users_df[users_df['is_verified'] == 1]
        
        if activated_users.empty:
            st.info("👤 Нет активированных участников. Участники должны перейти по ссылке активации.")
        else:
            st.write(f"**Активированных участников:** {len(activated_users)}")
            
            # Отображение таблицы с возможностью управления
            for idx, user in activated_users.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
                    
                    with col1:
                        # Статус активности
                        activity_icon = "✅" if user['is_active'] else "❌"
                        
                        # Формируем отображаемое имя
                        if user['full_name']:
                            display_name = user['full_name']
                        elif user['username']:
                            display_name = f"@{user['username']}"
                        else:
                            display_name = f"ID:{user['user_id']}"
                        
                        st.write(f"{activity_icon} **{display_name}**")
                        
                        if user['username'] and user['full_name']:
                            st.caption(f"@{user['username']}")
                        if user['user_id']:
                            st.caption(f"ID: {user['user_id']}")
                    
                    with col2:
                        st.write("✅ Активирован")
                        if user['created_at']:
                            created_date = pd.to_datetime(user['created_at']).strftime('%d.%m.%Y')
                            st.caption(f"Присоединился: {created_date}")
                    
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
                        if st.button("🗑️", key=f"delete_{user['id']}", help="Удалить участника"):
                            if delete_user(user['id']):
                                st.success("Участник удален!")
                                st.rerun()
                            else:
                                st.error("Ошибка удаления")
                    
                    st.divider()

with tab2:
    st.subheader("📊 Статистика команды")
    
    users_df = load_users()
    if not users_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_users = len(users_df)
            st.metric("Всего записей", total_users)
        
        with col2:
            activated_users = len(users_df[users_df['is_verified'] == 1])
            st.metric("Активированных", activated_users)
        
        with col3:
            active_users = len(users_df[(users_df['is_active'] == 1) & (users_df['is_verified'] == 1)])
            st.metric("Активных", active_users)
        
        with col4:
            responded_today = len(users_df[users_df['has_responded_today'] == 1])
            st.metric("Ответили сегодня", responded_today)
        
        # График активности по дням
        if 'created_at' in users_df.columns and len(users_df) > 0:
            users_df['created_at'] = pd.to_datetime(users_df['created_at'])
            daily_activations = users_df[users_df['is_verified'] == 1].groupby(users_df['created_at'].dt.date).size()
            
            if len(daily_activations) > 0:
                st.subheader("📈 Активации по дням")
                st.line_chart(daily_activations)
        
        # Статистика ответов
        if activated_users > 0:
            st.subheader("📝 Статистика ответов")
            response_rate = (responded_today / activated_users) * 100 if activated_users > 0 else 0
            st.progress(response_rate / 100)
            st.write(f"Процент ответивших сегодня: {response_rate:.1f}%")

# Боковая панель с информацией
with st.sidebar:
    st.header("ℹ️ Система управления")
    
    st.markdown("### 🔗 Ссылка активации")
    st.code("https://t.me/aidailytasksBot?start=group_activation")
    st.caption("Отправьте эту ссылку участникам команды")
    
    st.write("""
    **Принцип работы:**
    
    🏢 **Для администратора:**
    1. Отправьте ссылку активации участникам
    2. Следите за активациями в админ панели
    3. Получайте ежедневные сводки планов
    
    👥 **Для участников:**
    1. Переходят по ссылке от администратора
    2. Нажимают /start в боте
    3. Автоматически активируются
    
    ⏰ **Ежедневный процесс:**
    - 9:00 - бот отправляет вопросы участникам
    - 9:05 - генерация сводки для администратора
    """)
    
    st.divider()
    
    st.write("**Время сервера:**")
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if st.button("🔧 Техническая информация"):
        st.info(f"База данных: {DB_PATH}")
        st.info(f"Статус БД: {'✅ Подключена' if DB_PATH.exists() else '❌ Не найдена'}")
        st.info("Бот: @aidailytasksBot")