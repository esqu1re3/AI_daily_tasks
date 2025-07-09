# app/models/message.py
from app.core.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")
