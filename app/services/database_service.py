# app/services/database_service.py

from app.core.database import SessionLocal
from app.models.report import Report
from datetime import datetime

def save_report(user_id, report_type, content):
    db = SessionLocal()
    report = Report(
        user_id=user_id,
        type=report_type,
        content=content,
        created_at=datetime.utcnow()
    )
    db.add(report)
    db.commit()
    db.close()
