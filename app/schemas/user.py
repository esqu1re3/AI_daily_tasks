# Pydantic-схемы для User
from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: Optional[str] = None  # @username теперь опциональный
    full_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_group_member: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    user_id: Optional[str] = None  # может быть None до активации
    is_active: bool
    is_verified: bool
    is_group_member: bool
    last_response: Optional[str] = None
    has_responded_today: bool
    activation_token: Optional[str] = None  # токен для активации
    
    class Config:
        from_attributes = True