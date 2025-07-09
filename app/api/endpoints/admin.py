# Сводка, экспорт, статистика
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import date
import pandas as pd
import os
from app.schemas.report import ReportResponseSchema
from app.services.summary_service import generate_daily_summary
from app.core.database import get_db
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportResponseSchema
from app.services.summary_service import generate_daily_summary

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.get("/reports/", response_model=List[ReportResponseSchema])
def get_all_reports(
    start_date: date = None,
    end_date: date = None,
    user_id: int = None,
    db: Session = Depends(get_db)
):
    """Получение всех отчетов с возможностью фильтрации"""
    query = db.query(Report)
    
    if start_date:
        query = query.filter(Report.created_at >= start_date)
    if end_date:
        query = query.filter(Report.created_at <= end_date)
    if user_id:
        query = query.filter(Report.user_id == user_id)
    
    return query.order_by(Report.created_at.desc()).all()

@router.get("/export/csv")
def export_reports_csv(
    start_date: date = None,
    end_date: date = None,
    db: Session = Depends(get_db)
):
    """Экспорт отчетов в CSV"""
    reports = get_all_reports(start_date, end_date, None, db)
    
    df = pd.DataFrame([{
        "id": r.id,
        "user_id": r.user_id,
        "type": r.type,
        "content": r.content,
        "created_at": r.created_at
    } for r in reports])
    
    os.makedirs("data/exported", exist_ok=True)
    filepath = "data/exported/reports_export.csv"
    df.to_csv(filepath, index=False)
    
    return FileResponse(
        filepath,
        media_type="text/csv",
        filename=f"reports_{date.today()}.csv"
    )

@router.get("/summary/daily")
def get_daily_summary(
    summary_date: date = date.today(),
    db: Session = Depends(get_db)
):
    """Генерация дневной сводки по всем сотрудникам"""
    try:
        summary = generate_daily_summary(db, summary_date)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/", response_model=List[dict])
def get_all_users(db: Session = Depends(get_db)):
    """Получение списка всех сотрудников"""
    users = db.query(User).all()
    return [{
        "id": u.id,
        "name": u.name,
        "telegram_id": u.telegram_id
    } for u in users]

@router.get("/stats/")
def get_stats_report(
    start_date: date = None,
    end_date: date = None,
    db: Session = Depends(get_db)
):
    """Статистика по активности сотрудников"""
    query = db.query(
        User.name,
        Report.type,
        db.func.count(Report.id).label("count")
    ).join(Report).group_by(User.name, Report.type)
    
    if start_date:
        query = query.filter(Report.created_at >= start_date)
    if end_date:
        query = query.filter(Report.created_at <= end_date)
    
    stats = query.all()
    
    return {
        "period": f"{start_date} - {end_date}" if start_date and end_date else "all time",
        "stats": [{
            "user": s.name,
            "report_type": s.type,
            "count": s.count
        } for s in stats]
    }