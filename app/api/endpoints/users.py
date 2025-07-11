# CRUD-доступ к сотрудникам
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
import logging
from app.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.user_response import UserResponse
from app.schemas.user import UserCreate, UserResponse as UserSchema, UserUpdate
from app.schemas.user_response import UserResponseResponse, UserResponseListItem

router = APIRouter(
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

@router.post("/", response_model=UserSchema, status_code=201)
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

@router.get("/", response_model=List[UserSchema])
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

@router.get("/{user_id}", response_model=UserSchema)
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

@router.get("/by-username/{username}", response_model=UserSchema)
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

@router.put("/{user_id}", response_model=UserSchema)
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

@router.post("/send-repeat-questions", status_code=200)
def send_repeat_questions_to_all():
    """Отправляет повторные сообщения всем активным участникам команды.
    
    Эндпоинт вызывается из админ панели при нажатии кнопки "Сбросить ответы дня".
    Отправляет повторное напоминание о необходимости отправить отчет.
    
    Returns:
        dict: Результат отправки с количеством успешных сообщений и ошибками.
    
    Raises:
        HTTPException: 500 при ошибках отправки сообщений.
    
    Examples:
        >>> # POST /users/send-repeat-questions
        >>> # Response: {"success_count": 3, "total_count": 3, "errors": []}
    """
    try:
        from app.services.scheduler import send_repeat_questions
        
        result = send_repeat_questions()
        
        logger.info(f"Повторная рассылка через API: отправлено {result['success_count']}/{result['total_count']} сообщений")
        
        return {
            "message": "Повторная рассылка выполнена",
            "success_count": result['success_count'],
            "total_count": result['total_count'],
            "errors": result['errors']
        }
        
    except Exception as e:
        logger.error(f"Ошибка API отправки повторных сообщений: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки сообщений: {str(e)}")

@router.post("/test-message/{user_id}", status_code=200)
def send_test_message_to_user(user_id: str, message: str = "🔔 Тестовое сообщение от администратора"):
    """Отправляет тестовое сообщение конкретному пользователю.
    
    Эндпоинт для диагностики работы Telegram бота.
    Позволяет проверить связь с пользователем и корректность настроек.
    
    Args:
        user_id (str): Telegram User ID получателя.
        message (str): Текст сообщения для отправки.
    
    Returns:
        dict: Результат отправки с информацией об успехе или ошибке.
    
    Raises:
        HTTPException: 500 при ошибках отправки сообщения.
    
    Examples:
        >>> # POST /users/test-message/123456789
        >>> # Response: {"success": true, "message": "Сообщение отправлено", "error": null}
    """
    try:
        from app.services.scheduler import send_test_message
        
        result = send_test_message(user_id, message)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Тестовое сообщение отправлено пользователю {user_id}",
                "error": None
            }
        else:
            return {
                "success": False,
                "message": f"Не удалось отправить сообщение пользователю {user_id}",
                "error": result["error"]
            }
        
    except Exception as e:
        logger.error(f"Ошибка API тестирования сообщений: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки тестового сообщения: {str(e)}")

@router.get("/scheduler/info", status_code=200)
def get_scheduler_status():
    """Получает информацию о статусе планировщика и активных задачах.
    
    Эндпоинт для диагностики работы планировщика.
    Возвращает информацию о статусе, количестве задач и времени следующей рассылки.
    
    Returns:
        dict: Информация о планировщике с активными задачами и их расписанием.
    
    Raises:
        HTTPException: 500 при ошибках получения информации о планировщике.
    
    Examples:
        >>> # GET /users/scheduler/info
        >>> # Response: {"running": true, "jobs_count": 1, "next_morning_questions": "2025-01-15 12:47:00 Asia/Bishkek"}
    """
    try:
        from app.services.scheduler import get_scheduler_info
        
        info = get_scheduler_info()
        
        logger.info(f"Информация о планировщике запрошена: {info['running']}, задач: {info['jobs_count']}")
        
        return info
        
    except Exception as e:
        logger.error(f"Ошибка API получения информации о планировщике: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации о планировщике: {str(e)}")


@router.post("/scheduler/restart", status_code=200)
def restart_scheduler():
    """Перезапускает планировщик для применения изменений в расписании.
    
    Эндпоинт для перезапуска планировщика из админ панели.
    Полезен после изменения расписания групп для немедленного применения изменений.
    
    Returns:
        dict: Результат перезапуска планировщика.
    
    Raises:
        HTTPException: 500 при ошибках перезапуска планировщика.
    
    Examples:
        >>> # POST /users/scheduler/restart
        >>> # Response: {"success": true, "message": "Планировщик перезапущен", "jobs_count": 3}
    """
    try:
        from app.services.scheduler import start_scheduler, get_scheduler_info
        
        logger.info("Запуск перезапуска планировщика через API")
        
        # Перезапускаем планировщик
        start_scheduler()
        
        # Получаем обновленную информацию
        info = get_scheduler_info()
        
        logger.info(f"Планировщик перезапущен через API, задач: {info['jobs_count']}")
        
        return {
            "success": True,
            "message": "Планировщик успешно перезапущен",
            "jobs_count": info['jobs_count'],
            "running": info['running']
        }
        
    except Exception as e:
        logger.error(f"Ошибка API перезапуска планировщика: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка перезапуска планировщика: {str(e)}")

@router.get("/{user_id}/responses", response_model=List[UserResponseListItem])
def get_user_responses(
    user_id: int, 
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество записей"),
    db: Session = Depends(get_db)
):
    """Получает историю ответов конкретного пользователя с пагинацией.
    
    Возвращает список всех ответов пользователя в обратном хронологическом порядке
    (сначала новые). Поддерживает пагинацию для эффективной работы с большими объемами данных.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя в базе данных.
        skip (int): Количество записей для пропуска (offset). По умолчанию 0.
        limit (int): Максимальное количество записей для возврата. По умолчанию 20, максимум 100.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        List[UserResponseListItem]: Список ответов пользователя с сокращенной информацией.
    
    Raises:
        HTTPException: 404 если пользователь не найден, 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users/123/responses?skip=0&limit=10
        >>> # Response: [UserResponseListItem, UserResponseListItem, ...]
    """
    try:
        # Проверяем существование пользователя
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем ответы пользователя с пагинацией
        responses = db.query(UserResponse).filter(
            UserResponse.user_id == user_id
        ).order_by(desc(UserResponse.created_at)).offset(skip).limit(limit).all()
        
        # Преобразуем в сокращенный формат для списка
        result = []
        for response in responses:
            preview_text = response.response_text[:100] + "..." if len(response.response_text) > 100 else response.response_text
            
            result.append(UserResponseListItem(
                id=response.id,
                user_id=response.user_id,
                response_text_preview=preview_text,
                created_at=response.created_at,
                telegram_username=response.telegram_username,
                full_name=response.full_name
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка получения истории ответов пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{user_id}/responses/{response_id}", response_model=UserResponseResponse)
def get_user_response_detail(
    user_id: int, 
    response_id: int,
    db: Session = Depends(get_db)
):
    """Получает полную информацию о конкретном ответе пользователя.
    
    Возвращает детальную информацию об одном ответе, включая полный текст ответа
    и все метаданные на момент отправки.
    
    Args:
        user_id (int): Уникальный идентификатор пользователя в базе данных.
        response_id (int): Уникальный идентификатор ответа.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        UserResponseResponse: Полная информация об ответе пользователя.
    
    Raises:
        HTTPException: 404 если пользователь или ответ не найден, 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users/123/responses/456
        >>> # Response: UserResponseResponse with full details
    """
    try:
        # Проверяем существование пользователя
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем конкретный ответ
        response = db.query(UserResponse).filter(
            UserResponse.id == response_id,
            UserResponse.user_id == user_id
        ).first()
        
        if not response:
            raise HTTPException(status_code=404, detail="Response not found")
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка получения ответа {response_id} пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/responses/recent", response_model=List[UserResponseListItem])
def get_recent_responses(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество записей"),
    db: Session = Depends(get_db)
):
    """Получает последние ответы всех пользователей.
    
    Возвращает список недавних ответов всех активированных пользователей
    в обратном хронологическом порядке для мониторинга активности команды.
    
    Args:
        skip (int): Количество записей для пропуска (offset). По умолчанию 0.
        limit (int): Максимальное количество записей для возврата. По умолчанию 20, максимум 100.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        List[UserResponseListItem]: Список последних ответов всех пользователей.
    
    Raises:
        HTTPException: 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /users/responses/recent?limit=10
        >>> # Response: [UserResponseListItem, UserResponseListItem, ...]
    """
    try:
        # Получаем последние ответы от всех пользователей
        responses = db.query(UserResponse).join(User).filter(
            User.is_verified == True  # Только от активированных пользователей
        ).order_by(desc(UserResponse.created_at)).offset(skip).limit(limit).all()
        
        # Преобразуем в сокращенный формат для списка
        result = []
        for response in responses:
            preview_text = response.response_text[:100] + "..." if len(response.response_text) > 100 else response.response_text
            
            result.append(UserResponseListItem(
                id=response.id,
                user_id=response.user_id,
                response_text_preview=preview_text,
                created_at=response.created_at,
                telegram_username=response.telegram_username,
                full_name=response.full_name
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка получения последних ответов: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")