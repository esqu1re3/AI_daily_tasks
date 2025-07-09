# CRUD-доступ к сотрудникам
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создание нового пользователя"""
    try:
        # Проверка на существующего пользователя
        db_user = db.query(User).filter(User.telegram_id == user.telegram_id).first()
        if db_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        new_user = User(
            name=user.name,
            telegram_id=user.telegram_id
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

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Обновление данных пользователя"""
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.name is not None:
            db_user.name = user.name
        if user.telegram_id is not None:
            db_user.telegram_id = user.telegram_id
            
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