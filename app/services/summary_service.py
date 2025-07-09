# Генерация AI-сводки по данным
from sqlalchemy.orm import Session
from app.models.report import Report
from app.models.user import User
from datetime import date

def generate_daily_summary(db: Session, summary_date: date = None):
    """Генерация дневной сводки по отчетам сотрудников"""
    if not summary_date:
        summary_date = date.today()
    
    # Получаем отчеты за указанную дату
    reports = db.query(Report).filter(
        db.func.date(Report.created_at) == summary_date
    ).all()
    
    # Получаем список всех пользователей
    users = db.query(User).all()
    
    # Формируем сводку
    summary = {
        "date": summary_date.isoformat(),
        "total_reports": len(reports),
        "users": []
    }
    
    for user in users:
        user_reports = [r for r in reports if r.user_id == user.id]
        summary["users"].append({
            "user_id": user.id,
            "user_name": user.name,
            "morning_reports": len([r for r in user_reports if r.type == "morning"]),
            "evening_reports": len([r for r in user_reports if r.type == "evening"]),
            "completed_tasks": sum(1 for r in user_reports if "выполнено" in r.content.lower())
        })
    
    return summary