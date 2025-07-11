# Pydantic-схемы для UserResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserResponseBase(BaseModel):
    response_text: str
    telegram_user_id: str
    telegram_username: Optional[str] = None
    full_name: Optional[str] = None

class UserResponseCreate(UserResponseBase):
    user_id: int

class UserResponseResponse(UserResponseBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserResponseListItem(BaseModel):
    """Сокращенная схема для списков (без полного текста)"""
    id: int
    user_id: int
    response_text_preview: str  # Первые 100 символов
    created_at: datetime
    telegram_username: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True 