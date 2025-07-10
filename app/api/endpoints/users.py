# CRUD-доступ к сотрудникам
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
from app.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

def get_bot_username():
    """Получение username бота из API"""
    try:
        import telebot
        bot = telebot.TeleBot(settings.TG_BOT_TOKEN)
        bot_info = bot.get_me()
        return bot_info.username
    except Exception as e:
        logger.error(f"Ошибка получения username бота: {e}")
        return "your_bot"  # fallback

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создание нового пользователя (пользователи создаются автоматически при активации)"""
    try:
        # Пользователи создаются автоматически при активации
        # Этот эндпоинт оставлен для совместимости
        
        new_user = User(
            username=user.username,
            full_name=user.full_name,
            is_verified=False,  # новые пользователи не активированы
            is_group_member=True,  # по умолчанию участники команды
            activation_token=None
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получение списка пользователей с пагинацией"""
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """Получение пользователя по ID"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/by-username/{username}", response_model=UserResponse)
def read_user_by_username(username: str, db: Session = Depends(get_db)):
    """Получение пользователя по username"""
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        logger.error(f"Error fetching user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Обновление данных пользователя"""
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.username is not None:
            # Проверяем уникальность username
            existing_user = db.query(User).filter(
                User.username == user.username, 
                User.id != user_id
            ).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="Username already taken")
            db_user.username = user.username
            
        if user.full_name is not None:
            db_user.full_name = user.full_name
            
        if user.is_active is not None:
            db_user.is_active = user.is_active
            
        if user.is_verified is not None:
            db_user.is_verified = user.is_verified
            
        if user.is_group_member is not None:
            db_user.is_group_member = user.is_group_member
            
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Удаление пользователя"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.delete(user)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/bot/info")
def get_bot_info():
    """Получение информации о боте"""
    try:
        bot_username = get_bot_username()
        return {"bot_username": bot_username}
    except Exception as e:
        logger.error(f"Error getting bot info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")