# Pydantic-схемы для User
from pydantic import BaseModel

class UserBase(BaseModel):
    name: str
    telegram_id: str

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: str | None = None
    telegram_id: str | None = None

class UserResponse(UserBase):
    id: int
    
    class Config:
        from_attributes = True