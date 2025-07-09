# Модель отчёта сотрудника (утренний и вечерний)

#model_config = ConfigDict(from_attributes=True)
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)  # morning / evening
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
