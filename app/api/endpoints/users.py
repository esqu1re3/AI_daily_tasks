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
    """Получает username Telegram бота из API.
    
    Подключается к Telegram Bot API для получения информации о боте,
    включая его username для формирования ссылок активации.
    
    Returns:
        str: Username бота без символа @ или 'your_bot' при ошибке.
    
    Raises:
        Exception: При ошибках подключения к Telegram API (обрабатывается внутри).
    
    Examples:
        >>> username = get_bot_username()
        >>> print(f"Bot username: @{username}")
        Bot username: @aidailytasksBot
    """
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
    """Создает нового пользователя в системе.
    
    Создает запись пользователя в базе данных. В обычном режиме работы
    пользователи создаются автоматически при активации через ссылку.
    Этот эндпоинт предназначен для административного управления.
    
    Args:
        user (UserCreate): Данные для создания пользователя.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        UserResponse: Созданный пользователь с присвоенным ID.
    
    Raises:
        HTTPException: 500 при ошибках базы данных.
    
    Examples:
        >>> # POST /users
        >>> {
        ...   "username": "john_doe",
        ...   "full_name": "John Doe"
        ... }
        >>> # Response: UserResponse with id and other fields
    """
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
    """Получает список пользователей с пагинацией.
    
    Возвращает список всех пользователей системы с поддержкой пагинации
    для эффективной работы с большими наборами данных.
    
    Args:
        skip (int): Количество записей для пропуска (offset). По умолчанию 0.
        limit (int): Максимальное количество записей для возврата. По умолчанию 100.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        List[UserResponse]: Список пользователей с их данными.
    
    Raises:
        HTTPException: 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users?skip=0&limit=10
        >>> # Response: [UserResponse, UserResponse, ...]
        
        >>> # GET /users?skip=10&limit=5
        >>> # Получить пользователей с 11 по 15
    """
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """Получает пользователя по его ID.
    
    Возвращает детальную информацию о конкретном пользователе
    по его уникальному идентификатору в базе данных.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя в базе данных.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        UserResponse: Данные пользователя.
    
    Raises:
        HTTPException: 404 если пользователь не найден, 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users/123
        >>> # Response: UserResponse with id=123
    """
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
    """Получает пользователя по username.
    
    Ищет пользователя в системе по его Telegram username.
    Полезно для поиска пользователей по их публичным именам.
    
    Args:
        username (str): Telegram username пользователя без символа @.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        UserResponse: Данные найденного пользователя.
    
    Raises:
        HTTPException: 404 если пользователь не найден, 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users/by-username/john_doe
        >>> # Response: UserResponse for user with username 'john_doe'
    """
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
    """Обновляет данные пользователя.
    
    Позволяет изменить информацию о пользователе, включая статусы активности,
    активации и принадлежности к команде. Проверяет уникальность username.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя в базе данных.
        user (UserUpdate): Новые данные для обновления (только измененные поля).
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        UserResponse: Обновленные данные пользователя.
    
    Raises:
        HTTPException: 
            - 404 если пользователь не найден
            - 400 если username уже занят другим пользователем
            - 500 при ошибках базы данных
    
    Examples:
        >>> # PUT /users/123
        >>> {
        ...   "is_active": false,
        ...   "full_name": "John Updated Doe"
        ... }
        >>> # Response: UserResponse with updated fields
    """
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
    """Удаляет пользователя из системы.
    
    Полностью удаляет пользователя и всю связанную с ним информацию
    из базы данных. Операция необратима.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя в базе данных.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        None: HTTP 204 No Content при успешном удалении.
    
    Raises:
        HTTPException: 404 если пользователь не найден, 500 при ошибках базы данных.
    
    Examples:
        >>> # DELETE /users/123
        >>> # Response: HTTP 204 No Content
    """
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
    """Получает информацию о Telegram боте.
    
    Возвращает публичную информацию о боте, включая его username,
    который используется для формирования ссылок активации.
    
    Returns:
        dict: Словарь с информацией о боте, включая поле 'bot_username'.
    
    Raises:
        HTTPException: 500 при ошибках подключения к Telegram API.
    
    Examples:
        >>> # GET /users/bot/info
        >>> # Response: {"bot_username": "aidailytasksBot"}
    """
    try:
        bot_username = get_bot_username()
        return {"bot_username": bot_username}
    except Exception as e:
        logger.error(f"Error getting bot info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")