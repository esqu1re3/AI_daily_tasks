from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
from app.core.database import get_db
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate,ReportRead, ReportUpdate#ReportResponseSchem
from app.services.gemini_service import GeminiService

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    responses={404: {"description": "Not found"}},
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Временная заглушка ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Тут должна быть проверка токена через JWT и получение пользователя из базы
    return {"user_id": 1}

# --- Хелпер ---
async def check_report_ownership(
    report_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or report.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this report"
        )
    return report

# --- Эндпоинты API ---
@router.post("/", response_model=ReportRead)
async def create_report(
    report_data: ReportCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание нового ежедневного отчета"""
    db_report = Report(
        user_id=current_user["user_id"],
        **report_data.dict()
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@router.get("/", response_model=List[ReportRead])
async def get_user_reports(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение отчетов пользователя с фильтрацией по датам"""
    query = db.query(Report).filter(Report.user_id == current_user["user_id"])
    if start_date:
        query = query.filter(Report.date >= start_date)
    if end_date:
        query = query.filter(Report.date <= end_date)
    return query.order_by(Report.date.desc()).all()

@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение конкретного отчета"""
    report = await check_report_ownership(report_id, current_user["user_id"], db)
    return report

@router.put("/{report_id}", response_model=ReportRead)
async def update_report(
    report_id: int,
    report_data: ReportUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление отчета"""
    report = await check_report_ownership(report_id, current_user["user_id"], db)
    for field, value in report_data.dict(exclude_unset=True).items():
        setattr(report, field, value)
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление отчета"""
    report = await check_report_ownership(report_id, current_user["user_id"], db)
    db.delete(report)
    db.commit()

router = APIRouter(prefix="/api/ai", tags=["AI"])

@router.get("/ask")
async def ask_gemini(prompt: str):
    """Эндпоинт для запросов к Gemini"""
    service = GeminiService()
    response = service.generate_text(prompt)
    return {"response": response}