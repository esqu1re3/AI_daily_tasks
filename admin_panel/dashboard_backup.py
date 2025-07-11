import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime
from pathlib import Path
import logging
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Настройки страницы
st.set_page_config(
    page_title="AI Daily Tasks — Админка",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Кастомный CSS для красивого дизайна
st.markdown("""
<style>
    /* Импорт современных шрифтов */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Основные переменные */
    :root {
        --primary-color: #667eea;
        --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --secondary-color: #f093fb;
        --success-color: #4ade80;
        --warning-color: #fbbf24;
        --error-color: #f87171;
        --background-color: #0f1419;
        --surface-color: #1a1f2e;
        --card-color: #242b3d;
        --text-primary: #ffffff;
        --text-secondary: #94a3b8;
        --border-color: #334155;
        --shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        --radius: 12px;
    }
    
    /* Основные стили */
    .stApp {
        background: var(--background-color);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Скрытие элементов Streamlit */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Заголовки */
    .main-title {
        background: var(--primary-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
        line-height: 1.2;
    }
    
    .subtitle {
        color: var(--text-secondary);
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Карточки */
    .metric-card {
        background: var(--card-color);
        border: 1px solid var(--border-color);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin: 0.5rem 0;
        box-shadow: var(--shadow);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        border-color: var(--primary-color);
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--primary-gradient);
    }
    
    /* Информационная панель */
    .info-panel {
        background: linear-gradient(135deg, var(--card-color) 0%, #2d3748 100%);
        border: 1px solid var(--border-color);
        border-radius: var(--radius);
        padding: 2rem;
        margin: 1rem 0;
        position: relative;
        overflow: hidden;
    }
    
    .info-panel::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--primary-gradient);
    }
    
    .activation-link {
        background: var(--surface-color);
        border: 1px solid var(--primary-color);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        font-family: 'Fira Code', monospace;
        font-size: 0.9rem;
        color: var(--primary-color);
        word-break: break-all;
    }
    
    /* Кнопки */
    .stButton > button {
        background: var(--primary-gradient);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
    }
    
    /* Пользовательские карточки */
    .user-card {
        background: var(--card-color);
        border: 1px solid var(--border-color);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .user-card:hover {
        border-color: var(--primary-color);
        box-shadow: var(--shadow);
    }
    
    .user-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: var(--primary-gradient);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 1.2rem;
        margin-right: 1rem;
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-active {
        background: rgba(74, 222, 128, 0.2);
        color: var(--success-color);
        border: 1px solid var(--success-color);
    }
    
    .status-inactive {
        background: rgba(248, 113, 113, 0.2);
        color: var(--error-color);
        border: 1px solid var(--error-color);
    }
    
    .status-pending {
        background: rgba(251, 191, 36, 0.2);
        color: var(--warning-color);
        border: 1px solid var(--warning-color);
    }
    
    /* Вкладки */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: var(--surface-color);
        border-radius: var(--radius);
        padding: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: var(--text-secondary);
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary-gradient) !important;
        color: white !important;
    }
    
    /* Метрики */
    .stMetric {
        background: var(--card-color);
        border: 1px solid var(--border-color);
        border-radius: var(--radius);
        padding: 1rem;
        text-align: center;
    }
    
    .stMetric > div > div {
        color: var(--text-primary);
    }
    
    /* Боковая панель */
    .sidebar-content {
        background: var(--surface-color);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid var(--border-color);
    }
    
    /* Прогресс бар */
    .stProgress > div > div {
        background: var(--primary-gradient);
        border-radius: 10px;
    }
    
    /* Экспандеры */
    .streamlit-expanderHeader {
        background: var(--surface-color);
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }
    
    /* Датафреймы */
    .stDataFrame {
        border-radius: var(--radius);
        overflow: hidden;
    }
    
    /* Селектбоксы и инпуты */
    .stSelectbox > div > div {
        background: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
    }
    
    /* Спиннер */
    .stSpinner > div {
        border-top-color: var(--primary-color) !important;
    }
    
    /* Уведомления */
    .stAlert {
        border-radius: var(--radius) !important;
        border: 1px solid var(--border-color) !important;
        animation: slideInDown 0.4s ease-out !important;
        transition: all 0.3s ease !important;
        min-width: 300px !important;
        max-width: 450px !important;
        width: fit-content !important;
        min-height: 50px !important;
        max-height: 120px !important;
        overflow: visible !important;
        position: relative !important;
        z-index: 1000 !important;
        line-height: 1.5 !important;
        font-size: 0.9rem !important;
        padding: 14px 18px !important;
        margin: 8px 0 !important;
        display: block !important;
        box-shadow: var(--shadow) !important;
    }
    
    .stAlert[data-testid="stAlert"] {
        min-width: 300px !important;
        max-width: 450px !important;
        min-height: 50px !important;
        max-height: 120px !important;
        overflow: visible !important;
    }
    
    .stAlert > div,
    .stAlert p {
        display: block !important;
        overflow: visible !important;
        text-overflow: unset !important;
        max-width: 100% !important;
        line-height: 1.5 !important;
        margin: 0 !important;
        padding: 0 !important;
        word-wrap: break-word !important;
        white-space: normal !important;
    }
    
    .stSuccess {
        background: linear-gradient(135deg, rgba(74, 222, 128, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
        border-left: 4px solid var(--success-color);
    }
    
    .stError {
        background: linear-gradient(135deg, rgba(248, 113, 113, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
        border-left: 4px solid var(--error-color);
    }
    
    .stWarning {
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
        border-left: 4px solid var(--warning-color);
    }
    
    .stInfo {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%);
        border-left: 4px solid var(--primary-color);
    }
    
    /* Анимации для уведомлений */
    @keyframes slideInDown {
        from {
            opacity: 0;
            transform: translateY(-30px) scale(0.95);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    @keyframes slideOutUp {
        from {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
        to {
            opacity: 0;
            transform: translateY(-30px) scale(0.95);
        }
    }
    
    .notification-enter {
        animation: slideInDown 0.4s ease-out;
    }
    
    .notification-exit {
        animation: slideOutUp 0.3s ease-in;
    }
    
    /* Адаптивность */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2rem;
        }
        
        .metric-card, .user-card {
            margin: 0.25rem 0;
            padding: 1rem;
        }
        
        .info-panel {
            padding: 1.5rem;
        }
    }
    
    /* Анимации */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .metric-card, .user-card, .info-panel {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Кастомные иконки */
    .icon {
        width: 24px;
        height: 24px;
        display: inline-block;
        margin-right: 8px;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)

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

def reset_daily_responses_and_send_messages():
    """Сброс флагов ответов на новый день И отправка повторных сообщений участникам"""
    try:
        # 1. Сбрасываем флаги ответов в БД
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET has_responded_today = 0, last_response = NULL")
        conn.commit()
        conn.close()
        
        # 2. Отправляем повторные сообщения через API
        import requests
        try:
            response = requests.post("http://localhost:8000/users/send-repeat-questions", timeout=30)
            if response.status_code == 200:
                result = response.json()
                success_count = result.get('success_count', 0)
                total_count = result.get('total_count', 0)
                errors = result.get('errors', [])
                
                if success_count > 0:
                    logger.info(f"Повторные сообщения отправлены: {success_count}/{total_count}")
                    return {"success": True, "message": f"Ответы сброшены и повторные сообщения отправлены участникам ({success_count}/{total_count})", "details": result}
                else:
                    logger.warning("Не удалось отправить ни одного повторного сообщения")
                    return {"success": True, "message": "Ответы сброшены, но повторные сообщения не отправлены (нет активных участников)", "details": result}
            else:
                logger.error(f"Ошибка API отправки сообщений: {response.status_code}")
                return {"success": True, "message": "Ответы сброшены, но не удалось отправить повторные сообщения (ошибка API)", "details": None}
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка подключения к API: {e}")
            return {"success": True, "message": "Ответы сброшены, но не удалось отправить повторные сообщения (API недоступен)", "details": None}
        
    except Exception as e:
        logger.error(f"Ошибка сброса ответов: {e}")
        return {"success": False, "message": f"Ошибка сброса ответов: {e}", "details": None}

# Инициализация БД
if not init_database():
    st.error("❌ Ошибка подключения к базе данных!")
    st.stop()

# ======================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ======================

# Заголовок с градиентом
st.markdown('<h1 class="main-title">👥 AI Daily Tasks</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Система управления командой и сбора вечерних планов</p>', unsafe_allow_html=True)

# Информационная панель
st.markdown("""
<div class="info-panel">
    <h3 style="color: var(--text-primary); margin-top: 0;">🔗 Ссылка для активации участников команды</h3>
    <div class="activation-link">
        https://t.me/aidailytasksBot?start=group_activation
    </div>
    <p style="color: var(--text-secondary); margin-bottom: 0;">
        📧 Отправьте эту ссылку участникам команды для автоматической активации в системе<br>
        ⏰ <strong>Время рассылки:</strong> 17:30 (UTC+6)<br>
        💡 <strong>Совет:</strong> При сбросе ответов всем участникам отправляется повторное напоминание
    </p>
</div>
""", unsafe_allow_html=True)

# Разделяем на вкладки
tab1, tab2, tab3 = st.tabs(["👤 Участники", "📊 Статистика", "🔧 Диагностика"])

with tab1:
    st.markdown("### 👥 Управление участниками команды")
    
    # Кнопки управления
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("🔄 Обновить список", type="primary", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🔄 Сбросить ответы дня", help="Сбрасывает флаги ответов и отправляет повторные сообщения участникам", use_container_width=True):
            with st.spinner("Сброс ответов и отправка сообщений..."):
                result = reset_daily_responses_and_send_messages()
                if result["success"]:
                    st.success(result["message"])
                    if result["details"]:
                        details = result["details"]
                        if details.get("errors"):
                            with st.expander("⚠️ Подробности ошибок"):
                                for error in details["errors"]:
                                    st.warning(error)
                    st.rerun()
                else:
                    st.error(result["message"])
    
    # Загрузка и отображение пользователей
    users_df = load_users()
    
    if users_df.empty:
        st.markdown("""
        <div class="metric-card" style="text-align: center; padding: 3rem;">
            <h3 style="color: var(--text-secondary);">👤 Нет участников в системе</h3>
            <p style="color: var(--text-secondary);">Отправьте ссылку активации участникам команды!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Фильтруем только активированных участников
        activated_users = users_df[users_df['is_verified'] == 1]
        
        if activated_users.empty:
            st.markdown("""
            <div class="metric-card" style="text-align: center; padding: 3rem;">
                <h3 style="color: var(--text-secondary);">👤 Нет активированных участников</h3>
                <p style="color: var(--text-secondary);">Участники должны перейти по ссылке активации</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="color: var(--text-primary); margin: 0;">Активированных участников: <span style="color: var(--primary-color);">{len(activated_users)}</span></h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Отображение карточек пользователей
            for idx, user in activated_users.iterrows():
                # Формируем отображаемое имя
                if user['full_name']:
                    display_name = user['full_name']
                    avatar_text = user['full_name'][0].upper()
                elif user['username']:
                    display_name = f"@{user['username']}"
                    avatar_text = user['username'][0].upper()
                else:
                    display_name = f"ID:{user['user_id']}"
                    avatar_text = "U"
                
                # Статусы
                activity_status = "active" if user['is_active'] else "inactive"
                response_status = "✅ Ответил" if user['has_responded_today'] else "⏳ Ожидание"
                
                # Создаем карточку пользователя
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                    
                    with col1:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; padding: 1rem 0;">
                            <div class="user-avatar">{avatar_text}</div>
                            <div>
                                <h4 style="margin: 0; color: var(--text-primary);">{display_name}</h4>
                                {f'<p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">@{user["username"]}</p>' if user['username'] and user['full_name'] else ''}
                                <p style="margin: 0; color: var(--text-secondary); font-size: 0.8rem;">ID: {user['user_id']}</p>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        if user['created_at']:
                            created_date = pd.to_datetime(user['created_at']).strftime('%d.%m.%Y')
                            # Статус активности пользователя
                            if user['is_active']:
                                status_text = "✅ Активен"
                                status_class = "status-active"
                            else:
                                status_text = "❌ Деактивирован"
                                status_class = "status-inactive"
                            
                            st.markdown(f"""
                            <div style="padding: 1rem 0;">
                                <span class="status-badge {status_class}">{status_text}</span>
                                <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary); font-size: 0.8rem;">
                                    Присоединился: {created_date}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    with col3:
                        status_class = "status-active" if user['has_responded_today'] else "status-pending"
                        st.markdown(f"""
                        <div style="padding: 1rem 0;">
                            <span class="status-badge {status_class}">{response_status}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if user['last_response']:
                            with st.expander("📝 Последний ответ"):
                                st.text(user['last_response'][:200] + "..." if len(user['last_response']) > 200 else user['last_response'])
                    
                    with col4:
                        # Кнопки управления
                        col4a, col4b, col4c = st.columns(3)
                        
                        with col4a:
                            current_status = user['is_active']
                            new_status = not current_status
                            # Иконка показывает ТЕКУЩИЙ статус пользователя
                            action_text = "✅" if current_status else "❌"
                            action_help = f"Текущий статус: {'Активен' if current_status else 'Деактивирован'}. Нажмите чтобы {'деактивировать' if current_status else 'активировать'}"
                            if st.button(action_text, key=f"toggle_{user['id']}", help=action_help):
                                if update_user_status(user['id'], new_status):
                                    status_message = "активирован" if new_status else "деактивирован"
                                    success_placeholder = st.success(f"✅ Пользователь {status_message}!")
                                    # Задержка для показа уведомления
                                    time.sleep(1)
                                    success_placeholder.empty()
                                    st.rerun()
                                else:
                                    error_placeholder = st.error("❌ Ошибка обновления статуса")
                                    time.sleep(1)
                                    error_placeholder.empty()
                        
                        with col4b:
                            if st.button("💬", key=f"test_{user['id']}", help="Отправить тестовое сообщение"):
                                try:
                                    response = requests.post(f"http://localhost:8000/users/test-message/{user['user_id']}", timeout=10)
                                    if response.status_code == 200:
                                        result = response.json()
                                        if result.get("success"):
                                            success_placeholder = st.success("💬 Тестовое сообщение отправлено!")
                                            time.sleep(2)
                                            success_placeholder.empty()
                                        else:
                                            error_placeholder = st.error(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
                                            time.sleep(3)
                                            error_placeholder.empty()
                                    else:
                                        error_placeholder = st.error("❌ Ошибка API")
                                        time.sleep(2)
                                        error_placeholder.empty()
                                except Exception as e:
                                    error_placeholder = st.error(f"❌ Ошибка: {e}")
                                    time.sleep(2)
                                    error_placeholder.empty()
                        
                        with col4c:
                            if st.button("🗑️", key=f"delete_{user['id']}", help="Удалить участника из системы"):
                                if delete_user(user['id']):
                                    success_placeholder = st.success("🗑️ Участник удален из системы!")
                                    time.sleep(2)
                                    success_placeholder.empty()
                                    st.rerun()
                                else:
                                    error_placeholder = st.error("❌ Ошибка удаления участника")
                                    time.sleep(2)
                                    error_placeholder.empty()
                    
                    st.markdown("---")

with tab2:
    st.markdown("### 📊 Аналитика и статистика команды")
    
    users_df = load_users()
    if not users_df.empty:
        # Метрики в красивых карточках
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_users = len(users_df)
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: var(--primary-color); margin: 0; font-size: 2rem;">{total_users}</h3>
                <p style="color: var(--text-secondary); margin: 0.5rem 0 0 0;">Всего записей</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            activated_users = len(users_df[users_df['is_verified'] == 1])
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: var(--success-color); margin: 0; font-size: 2rem;">{activated_users}</h3>
                <p style="color: var(--text-secondary); margin: 0.5rem 0 0 0;">Активированных</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            active_users = len(users_df[(users_df['is_active'] == 1) & (users_df['is_verified'] == 1)])
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: var(--warning-color); margin: 0; font-size: 2rem;">{active_users}</h3>
                <p style="color: var(--text-secondary); margin: 0.5rem 0 0 0;">Активных</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            responded_today = len(users_df[users_df['has_responded_today'] == 1])
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: var(--secondary-color); margin: 0; font-size: 2rem;">{responded_today}</h3>
                <p style="color: var(--text-secondary); margin: 0.5rem 0 0 0;">Ответили сегодня</p>
            </div>
            """, unsafe_allow_html=True)
        
        # График активаций по дням
        if 'created_at' in users_df.columns and len(users_df) > 0:
            users_df['created_at'] = pd.to_datetime(users_df['created_at'])
            daily_activations = users_df[users_df['is_verified'] == 1].groupby(users_df['created_at'].dt.date).size().reset_index()
            daily_activations.columns = ['date', 'count']
            
            if len(daily_activations) > 0:
                st.markdown("### 📈 Динамика активаций")
                
                # Создаем красивый график с Plotly
                fig = px.line(daily_activations, x='date', y='count', 
                             title='Активации участников по дням',
                             markers=True)
                
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    title_font_size=20,
                    title_x=0.5
                )
                
                fig.update_traces(
                    line=dict(color='#667eea', width=3),
                    marker=dict(color='#667eea', size=8)
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # Статистика ответов с прогресс-баром
        if activated_users > 0:
            st.markdown("### 📝 Статистика ответов сегодня")
            response_rate = (responded_today / activated_users) * 100 if activated_users > 0 else 0
            
            # Красивый прогресс-бар
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="color: var(--text-primary); margin-bottom: 1rem;">Процент ответивших: {response_rate:.1f}%</h4>
                <div style="background: var(--surface-color); border-radius: 10px; height: 20px; overflow: hidden;">
                    <div style="background: var(--primary-gradient); height: 100%; width: {response_rate}%; border-radius: 10px; transition: width 0.5s ease;"></div>
                </div>
                <p style="color: var(--text-secondary); margin-top: 0.5rem; font-size: 0.9rem;">
                    {responded_today} из {activated_users} участников ответили
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Круговая диаграмма
            labels = ['Ответили', 'Не ответили']
            values = [responded_today, activated_users - responded_today]
            colors = ['#4ade80', '#f87171']
            
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3)])
            fig.update_traces(
                hoverinfo="label+percent+value",
                textinfo="label+percent",
                textfont_size=12,
                marker=dict(colors=colors, line=dict(color='#000000', width=2))
            )
            fig.update_layout(
                title_text="Распределение ответов сегодня",
                title_x=0.5,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='white'
            )
            
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown("### 🔧 Диагностика и управление системой")
    
    # Информация о планировщике
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h4 style="color: var(--text-primary); margin-top: 0;">📅 Статус планировщика</h4>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Обновить статус", use_container_width=True):
            st.rerun()
        
        try:
            response = requests.get("http://localhost:8000/users/scheduler/info", timeout=10)
            if response.status_code == 200:
                scheduler_info = response.json()
                
                if scheduler_info.get("running"):
                    st.markdown('<span class="status-badge status-active">✅ Планировщик работает</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="status-badge status-inactive">❌ Планировщик остановлен</span>', unsafe_allow_html=True)
                
                st.markdown(f"**Активных задач:** {scheduler_info.get('jobs_count', 0)}")
                
                if scheduler_info.get("next_morning_questions"):
                    st.markdown(f"**Следующая рассылка:** {scheduler_info['next_morning_questions']}")
                else:
                    st.warning("⚠️ Задача вечерней рассылки не найдена")
                
                if scheduler_info.get("jobs"):
                    with st.expander("📋 Активные задачи"):
                        for job in scheduler_info["jobs"]:
                            st.markdown(f"**{job['id']}** ({job['name']})")
                            if job['next_run_time']:
                                st.caption(f"Следующий запуск: {job['next_run_time']}")
                            st.caption(f"Расписание: {job['trigger']}")
                            st.divider()
            else:
                st.error("❌ Не удалось получить статус планировщика")
        except Exception as e:
            st.error(f"❌ Ошибка подключения к API: {e}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4 style="color: var(--text-primary); margin-top: 0;">🤖 Telegram Бот</h4>
        """, unsafe_allow_html=True)
        
        # Получаем активированного пользователя для тестирования
        users_df = load_users()
        activated_users = users_df[users_df['is_verified'] == 1]
        
        if not activated_users.empty:
            test_user = activated_users.iloc[0]
            user_display = test_user['full_name'] or f"@{test_user['username']}" if test_user['username'] else f"ID:{test_user['user_id']}"
            
            st.markdown(f"**Тестовый пользователь:** {user_display}")
            
            if st.button("💬 Отправить тестовое сообщение", use_container_width=True):
                try:
                    response = requests.post(
                        f"http://localhost:8000/users/test-message/{test_user['user_id']}", 
                        timeout=10
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            success_placeholder = st.success("💬 Тестовое сообщение успешно отправлено!")
                            time.sleep(2)
                            success_placeholder.empty()
                        else:
                            error_placeholder = st.error(f"❌ Ошибка отправки: {result.get('error')}")
                            time.sleep(3)
                            error_placeholder.empty()
                    else:
                        error_placeholder = st.error("❌ Ошибка API сервера")
                        time.sleep(2)
                        error_placeholder.empty()
                except Exception as e:
                    error_placeholder = st.error(f"❌ Ошибка подключения: {e}")
                    time.sleep(2)
                    error_placeholder.empty()
        else:
            st.info("👤 Нет активированных пользователей для тестирования")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Ручные действия
    st.markdown("""
    <div class="metric-card">
        <h4 style="color: var(--text-primary); margin-top: 0;">🔄 Ручные действия</h4>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("📢 Отправить сообщения СЕЙЧАС", type="secondary", use_container_width=True):
        with st.spinner("Отправка повторных сообщений..."):
            try:
                response = requests.post("http://localhost:8000/users/send-repeat-questions", timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    success_count = result.get('success_count', 0)
                    total_count = result.get('total_count', 0)
                    
                    if success_count > 0:
                        success_placeholder = st.success(f"✅ Отправлено {success_count}/{total_count} сообщений")
                        time.sleep(3)
                        success_placeholder.empty()
                    else:
                        warning_placeholder = st.warning("⚠️ Сообщения не отправлены (нет активных участников)")
                        time.sleep(3)
                        warning_placeholder.empty()
                    
                    if result.get("errors"):
                        with st.expander("⚠️ Ошибки отправки"):
                            for error in result["errors"]:
                                st.warning(error)
                else:
                    error_placeholder = st.error("❌ Ошибка API сервера")
                    time.sleep(2)
                    error_placeholder.empty()
            except Exception as e:
                error_placeholder = st.error(f"❌ Ошибка подключения: {e}")
                time.sleep(2)
                error_placeholder.empty()

# Боковая панель с информацией
with st.sidebar:
    st.markdown("""
    <div class="sidebar-content">
        <h3 style="color: var(--text-primary);">ℹ️ Информация</h3>
        
        <h4 style="color: var(--primary-color);">🔗 Ссылка активации</h4>
        <div style="background: var(--surface-color); padding: 1rem; border-radius: 8px; font-family: monospace; font-size: 0.8rem; word-break: break-all; margin-bottom: 1rem;">
            https://t.me/aidailytasksBot?start=group_activation
        </div>
        
        <h4 style="color: var(--primary-color);">📋 Принцип работы</h4>
        <div style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6;">
            <strong>🏢 Для администратора:</strong><br>
            • Отправьте ссылку активации участникам<br>
            • Следите за активациями в админ панели<br>
            • Получайте ежедневные сводки планов<br><br>
            
            <strong>👥 Для участников:</strong><br>
            • Переходят по ссылке от администратора<br>
            • Нажимают /start в боте<br>
            • Автоматически активируются<br><br>
            
            <strong>⏰ Ежедневный процесс:</strong><br>
            • 17:30 - бот отправляет вопросы<br>
            • 18:30 - генерация сводки
        </div>
        
        <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
            <h4 style="color: var(--primary-color);">🕐 Время сервера</h4>
            <p style="color: var(--text-primary); font-family: monospace;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            
            <h4 style="color: var(--primary-color);">🔧 Статус системы</h4>
            <p style="color: var(--success-color);">База данных: {'✅ Подключена' if DB_PATH.exists() else '❌ Не найдена'}</p>
            <p style="color: var(--text-secondary); font-size: 0.8rem;">Бот: @aidailytasksBot</p>
        </div>
    </div>
    """, unsafe_allow_html=True)