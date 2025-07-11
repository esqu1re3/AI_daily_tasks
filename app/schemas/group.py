from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GroupBase(BaseModel):
    """Базовая схема группы"""
    name: str = Field(..., min_length=1, max_length=100, description="Название группы")
    description: Optional[str] = Field(None, description="Описание группы")
    morning_hour: int = Field(9, ge=0, le=23, description="Час отправки утренних сообщений (0-23)")
    morning_minute: int = Field(30, ge=0, le=59, description="Минута отправки утренних сообщений (0-59)")
    timezone: str = Field("Asia/Bishkek", description="Временная зона группы")


class GroupCreate(GroupBase):
    """Схема для создания группы"""
    admin_id: str = Field(..., description="Telegram User ID администратора")
    admin_username: Optional[str] = Field(None, description="Telegram username администратора")
    admin_full_name: Optional[str] = Field(None, description="Полное имя администратора")


class GroupUpdate(BaseModel):
    """Схема для обновления группы"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Название группы")
    description: Optional[str] = Field(None, description="Описание группы")
    morning_hour: Optional[int] = Field(None, ge=0, le=23, description="Час отправки утренних сообщений")
    morning_minute: Optional[int] = Field(None, ge=0, le=59, description="Минута отправки утренних сообщений")
    timezone: Optional[str] = Field(None, description="Временная зона группы")
    is_active: Optional[bool] = Field(None, description="Активность группы")


class GroupResponse(GroupBase):
    """Схема ответа с информацией о группе"""
    id: int
    admin_id: str
    admin_username: Optional[str]
    admin_full_name: Optional[str]
    activation_token: str
    is_active: bool
    created_at: datetime
    members_count: Optional[int] = Field(None, description="Количество участников")

    class Config:
        from_attributes = True


class GroupActivation(BaseModel):
    """Схема для активации участника в группе"""
    activation_token: str = Field(..., description="Токен активации группы")


class GroupStats(BaseModel):
    """Статистика группы"""
    group_id: int
    group_name: str
    total_members: int
    active_members: int
    responses_today: int
    response_rate: float = Field(description="Процент ответивших участников")


# Простая схема участника для избежания circular imports
class GroupMember(BaseModel):
    """Схема участника группы"""
    id: int
    user_id: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GroupWithMembers(GroupResponse):
    """Схема группы с участниками"""
    members: List[GroupMember] = Field(default_factory=list, description="Участники группы") 