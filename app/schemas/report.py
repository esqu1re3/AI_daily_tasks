# Pydantic-схемы для Report
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
#from pydantic import BaseModel
from typing import Optional, List

class ReportBase(BaseModel):
    user_id: int
    type: str
    content: str

class ReportCreate(ReportBase):
    pass

class ReportResponseSchema(ReportBase):
    id: int
    created_at: datetime
    user_name: str | None = None  # Добавляем имя пользователя

    class Config:
        from_attributes = True

# Вложенная модель задачи
class DailyTask(BaseModel):
    task: str = Field(..., example="Разработка API для отчетов")
    hours: float = Field(..., gt=0, le=24, example=4.5)
    status: str = Field(..., example="completed")

# Модель для создания отчета
class ReportCreate(BaseModel):
    date1: date = Field(default_factory=date.today)
    tasks: List[DailyTask]
    comments: Optional[str] = None

# Модель для обновления отчета (частично)
class ReportUpdate(BaseModel):
    tasks: Optional[List[DailyTask]] = None
    comments: Optional[str] = None

# Модель для чтения отчета (ответ API)
class ReportRead(ReportCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)