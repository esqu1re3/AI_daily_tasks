import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Настройки страницы
st.set_page_config(
    page_title="AI Daily Tasks — Админка",
    page_icon="📊",
    layout="wide"
)

# Загрузка данных (замените на реальные данные)
@st.cache_data
def load_data():
    # Пример данных о сотрудниках
    users = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "name": ["Иван Петров", "Мария Сидорова", "Алексей Иванов", "Елена Смирнова"],
        "department": ["Разработка", "Аналитика", "Маркетинг", "Разработка"],
        "position": ["Team Lead", "Data Analyst", "Marketing Manager", "Backend Developer"]
    })
    
    # Пример данных о задачах
    tasks = pd.DataFrame({
        "id": range(1, 21),
        "user_id": np.random.choice([1, 2, 3, 4], 20),
        "date": [datetime.now() - timedelta(days=x) for x in range(20)],
        "task": ["Разработка фичи"]*5 + ["Анализ данных"]*5 + ["Маркетинг"]*5 + ["Тестирование"]*5,
        "status": np.random.choice(["Завершено", "В работе", "На проверке"], 20),
        "hours": np.random.randint(1, 9, 20)
    })
    
    # Объединяем данные
    data = pd.merge(tasks, users, left_on="user_id", right_on="id")
    return data

# Загрузка данных
df = load_data()

# ======================
# БОКОВАЯ ПАНЕЛЬ (SIDEBAR)
# ======================
with st.sidebar:
    st.image("https://via.placeholder.com/150x50?text=AI+Daily+Tasks", width=150)
    st.header("🔎 Фильтры")
    
    # Фильтр по дате
    date_range = st.date_input(
        "Диапазон дат",
        value=[datetime.now() - timedelta(days=7), datetime.now()],
        max_value=datetime.now()
    )
    
    # Фильтр по сотрудникам
    selected_users = st.multiselect(
        "Сотрудники",
        options=df["name"].unique(),
        default=df["name"].unique()[0]
    )
    
    # Фильтр по отделам
    selected_departments = st.multiselect(
        "Отделы",
        options=df["department"].unique(),
        default=df["department"].unique()
    )
    
    # Фильтр по статусам задач
    selected_statuses = st.multiselect(
        "Статусы задач",
        options=df["status"].unique(),
        default=df["status"].unique()
    )
    
    st.divider()
    
    # Кнопки управления
    if st.button("Применить фильтры", type="primary"):
        st.rerun()
    
    if st.button("Сбросить фильтры"):
        selected_users = df["name"].unique()
        selected_departments = df["department"].unique()
        selected_statuses = df["status"].unique()
        st.rerun()

# ======================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ======================
st.title("📊 AI Daily Tasks — Админка")
st.caption("Панель управления ежедневными отчетами сотрудников")

# Применение фильтров
filtered_df = df.copy()
if len(date_range) == 2:
    filtered_df = filtered_df[
        (filtered_df["date"].dt.date >= date_range[0]) & 
        (filtered_df["date"].dt.date <= date_range[1])
    ]
if selected_users:
    filtered_df = filtered_df[filtered_df["name"].isin(selected_users)]
if selected_departments:
    filtered_df = filtered_df[filtered_df["department"].isin(selected_departments)]
if selected_statuses:
    filtered_df = filtered_df[filtered_df["status"].isin(selected_statuses)]

# Вкладки для разных представлений
tab1, tab2, tab3 = st.tabs(["📋 Таблица задач", "📈 Статистика", "👥 Сотрудники"])

with tab1:
    # Отображение отфильтрованных данных
    st.subheader("Ежедневные задачи")
    st.dataframe(
        filtered_df[["date", "name", "department", "task", "status", "hours"]],
        column_config={
            "date": "Дата",
            "name": "Сотрудник",
            "department": "Отдел",
            "task": "Задача",
            "status": "Статус",
            "hours": "Часы"
        },
        hide_index=True,
        use_container_width=True
    )

with tab2:
    # Визуализация статистики
    st.subheader("Статистика по задачам")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Всего задач", filtered_df.shape[0])
        st.bar_chart(
            filtered_df.groupby("date")["id"].count(),
            color="#FF4B4B"
        )
    
    with col2:
        st.metric("Общее время", f"{filtered_df['hours'].sum()} ч")
        st.bar_chart(
            filtered_df.groupby("department")["hours"].sum(),
            color="#1A73E8"
        )

with tab3:
    # Информация о сотрудниках
    st.subheader("Сотрудники")
    
    employees_stats = filtered_df.groupby(["name", "department"]).agg(
        tasks_count=("id", "count"),
        total_hours=("hours", "sum")
    ).reset_index()
    
    st.dataframe(
        employees_stats,
        column_config={
            "name": "Сотрудник",
            "department": "Отдел",
            "tasks_count": "Кол-во задач",
            "total_hours": "Всего часов"
        },
        hide_index=True,
        use_container_width=True
    )

# Скачивание данных
st.sidebar.divider()
st.sidebar.download_button(
    label="📥 Экспорт данных",
    data=filtered_df.to_csv(index=False).encode('utf-8'),
    file_name=f"tasks_report_{datetime.now().date()}.csv",
    mime="text/csv"
)