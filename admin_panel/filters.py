import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import os
import streamlit as st
from typing import Tuple, Optional, List  # Добавляем недостающие импорты

def load_data() -> pd.DataFrame:
    """Загрузка данных из SQLite с обработкой ошибок"""
    try:
        BASE_DIR = Path(__file__).resolve().parent.parent
        DB_PATH = BASE_DIR / "data" / "reports_backup.sqlite"
        
        if not DB_PATH.exists():
            st.error("Файл базы данных не найден!")
            return pd.DataFrame()
            
        conn = sqlite3.connect(str(DB_PATH))  # Явное преобразование Path в строку
        users = pd.read_sql("SELECT * FROM users", conn)
        reports = pd.read_sql("SELECT * FROM reports", conn)
        return reports.merge(users, left_on="user_id", right_on="id")
    except sqlite3.Error as e:
        st.error(f"Ошибка SQLite: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Неожиданная ошибка: {str(e)}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals():
            conn.close()

def apply_filters(
    df: pd.DataFrame,
    date_col: str = "created_at",
    user_col: str = "name",
    content_col: str = "content"
) -> Tuple[pd.DataFrame, Optional[date], Optional[str], Optional[str]]:
    """Применяет фильтры через Streamlit интерфейс"""
    st.sidebar.header("🔎 Фильтры")
    
    # Фильтр по дате
    selected_date = st.sidebar.date_input(
        "Выберите дату",
        value=None
    )
    
    # Фильтр по сотруднику
    unique_users = ["Все"] + sorted(df[user_col].dropna().unique().tolist())
    selected_user = st.sidebar.selectbox(
        "Сотрудник",
        unique_users
    )
    
    # Фильтр по ключевым словам
    keyword = st.sidebar.text_input("Поиск по ключевым словам")
    
    # Применяем фильтры
    filtered_df = df.copy()
    
    if selected_date:
        filtered_df[date_col] = pd.to_datetime(filtered_df[date_col]).dt.date
        filtered_df = filtered_df[filtered_df[date_col] == selected_date]
    
    if selected_user != "Все":
        filtered_df = filtered_df[filtered_df[user_col] == selected_user]
    
    if keyword:
        filtered_df = filtered_df[
            filtered_df[content_col].str.contains(keyword, case=False, na=False)
        ]
    
    return filtered_df, selected_date, selected_user, keyword

def display_filter_stats(
    df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    selected_date: Optional[date],
    selected_user: Optional[str],
    keyword: Optional[str]
) -> None:
    """Показывает статистику фильтрации"""
    stats = []
    if selected_date:
        stats.append(f"📅 Дата: {selected_date}")
    if selected_user and selected_user != "Все":
        stats.append(f"👤 Сотрудник: {selected_user}")
    if keyword:
        stats.append(f"🔍 Ключевое слово: '{keyword}'")
    
    if stats:
        st.info(
            f"Найдено записей: {len(filtered_df)} из {len(df)}. Фильтры: {', '.join(stats)}"
        )

def get_report_types_filter(df: pd.DataFrame) -> List[str]:
    """Возвращает типы отчетов для фильтра"""
    types = df["type"].dropna().unique().tolist()
    return ["Все"] + sorted(types)

def apply_report_type_filter(
    df: pd.DataFrame,
    report_types: List[str],
    selected_type: str = "Все"
) -> pd.DataFrame:
    """Фильтрует по типу отчета"""
    if selected_type == "Все":
        return df
    return df[df["type"] == selected_type.lower()]