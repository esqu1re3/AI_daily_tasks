from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from app.core.database import get_db
from app.models.user import User
from app.models.group import Group
from app.models.user_response import UserResponse
from app.schemas.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupWithMembers, 
    GroupActivation, GroupStats
)

router = APIRouter()


# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===
def parse_days_of_week(group):
    """Преобразует поле days_of_week группы из строки в список целых чисел.
    
    Выполняет следующие действия:
    1. Проверяет наличие атрибута days_of_week у объекта group
    2. Если days_of_week — строка, преобразует её в список целых чисел (например, '0,1,2,3,4' → [0,1,2,3,4])
    3. Возвращает модифицированный объект group
    
    Args:
        group: Объект группы (SQLAlchemy или Pydantic), у которого есть поле days_of_week
    
    Returns:
        group: Тот же объект, но с days_of_week в виде списка int, если было преобразование
    
    Examples:
        >>> group.days_of_week = '0,1,2,3,4'
        >>> group = parse_days_of_week(group)
        >>> print(group.days_of_week)
        [0, 1, 2, 3, 4]
    """
    if hasattr(group, 'days_of_week') and group.days_of_week:
        if isinstance(group.days_of_week, str):
            group.days_of_week = [int(x) for x in group.days_of_week.split(',') if x.strip().isdigit()]
    return group


@router.get("/", response_model=List[GroupResponse])
async def get_groups(
    skip: int = Query(0, ge=0, description="Количество групп для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество групп"),
    active_only: bool = Query(True, description="Показывать только активные группы"),
    db: Session = Depends(get_db)
):
    """Получить список всех групп.
    
    Возвращает список групп с поддержкой пагинации и фильтрации.
    Для каждой группы добавляется количество активированных участников.
    
    Args:
        skip (int): Количество групп для пропуска (offset). По умолчанию 0.
        limit (int): Максимальное количество групп для возврата. По умолчанию 100.
        active_only (bool): Фильтровать только активные группы. По умолчанию True.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        List[GroupResponse]: Список групп с дополнительным полем members_count.
    
    Raises:
        HTTPException: 500 при ошибках базы данных.
    
    Examples:
        >>> # GET /api/groups?active_only=true&skip=0&limit=10
        >>> # Response: [GroupResponse, ...]
    """
    query = db.query(Group)
    
    if active_only:
        query = query.filter(Group.is_active == True)
    
    groups = query.offset(skip).limit(limit).all()
    
    # Добавляем количество участников для каждой группы
    for group in groups:
        group.members_count = db.query(User).filter(
            User.group_id == group.id,
            User.is_verified == True
        ).count()
        parse_days_of_week(group)
    
    return groups


@router.get("/{group_id}", response_model=GroupWithMembers)
async def get_group(group_id: int, db: Session = Depends(get_db)):
    """Получить информацию о конкретной группе с участниками"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    
    # Получаем участников группы
    members = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True,
        User.is_group_member == True
    ).all()
    
    group.members_count = len(members)
    group.members = members
    parse_days_of_week(group)
    
    return group


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    """Создать новую группу.
    
    Создает новую группу с указанными параметрами, генерирует токен активации
    и создает pending-запись для администратора.
    После создания перезапускает планировщик для добавления расписания группы.
    
    Args:
        group_data (GroupCreate): Данные для создания группы.
        db (Session): Сессия базы данных (внедряется автоматически).
    
    Returns:
        GroupResponse: Созданная группа с members_count=0.
    
    Raises:
        HTTPException: 400 если название группы не уникально или username админа пустой.
    
    Examples:
        >>> # POST /api/groups
        >>> {"name": "Team A", "admin_username": "admin1"}
        >>> # Response: GroupResponse with id and activation_token
    """
    
    # Проверяем, что admin_username указан и не пустой
    if not group_data.admin_username or not group_data.admin_username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо указать username администратора"
        )
    
    # Очищаем username от символа @, если он присутствует
    clean_username = group_data.admin_username.strip().lstrip('@')
    if not clean_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username администратора не может быть пустым"
        )
    
    # Проверяем уникальность названия группы
    existing_group = db.query(Group).filter(Group.name == group_data.name).first()
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Группа с таким названием уже существует"
        )
    
    # Создаем новую группу
    group_dict = group_data.model_dump()
    group_dict['admin_username'] = clean_username  # Используем очищенный username
    # days_of_week: преобразуем в строку для хранения
    if 'days_of_week' in group_dict and group_dict['days_of_week']:
        group_dict['days_of_week'] = ','.join(str(d) for d in group_dict['days_of_week'])
    else:
        group_dict['days_of_week'] = '0,1,2,3,4'
    new_group = Group(**group_dict)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    # Создаём pending запись для админа
    existing_admin = db.query(User).filter(User.username == clean_username).first()
    if existing_admin:
        if existing_admin.group_id != new_group.id:
            existing_admin.group_id = new_group.id
        existing_admin.is_group_member = False
        existing_admin.is_active = True
        existing_admin.is_verified = False
    else:
        new_admin = User(
            username=clean_username,
            group_id=new_group.id,
            is_verified=False,
            is_active=True,
            is_group_member=False
        )
        db.add(new_admin)
    db.commit()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Created/Updated pending admin @{clean_username} for group '{new_group.name}'")

    new_group.members_count = 0
    parse_days_of_week(new_group)

    # Restart scheduler to add the new group's schedule
    from app.services.scheduler import start_scheduler
    start_scheduler()

    return new_group


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int, 
    group_data: GroupUpdate, 
    db: Session = Depends(get_db)
):
    """Обновить информацию о группе"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    
    # Сохраняем старый admin_username для последующей обработки
    old_admin_username = group.admin_username
    
    # Проверяем уникальность названия (если меняется)
    if group_data.name and group_data.name != group.name:
        existing_group = db.query(Group).filter(
            Group.name == group_data.name,
            Group.id != group_id
        ).first()
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Группа с таким названием уже существует"
            )
    
    # Обрабатываем admin_username (если меняется)
    admin_changed = False
    if group_data.admin_username:
        clean_username = group_data.admin_username.strip().lstrip('@')
        if not clean_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username администратора не может быть пустым"
            )
        
        # Проверяем, изменился ли администратор
        if clean_username != old_admin_username:
            admin_changed = True
            
            # Ищем нового администратора в базе
            new_admin = db.query(User).filter(User.username == clean_username).first()
            
            if new_admin:
                # Если новый админ найден, добавляем его в группу
                if new_admin.group_id != group_id:
                    # Убираем из старой группы (если был в другой)
                    if new_admin.group_id:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Пользователь @{clean_username} перемещен из группы {new_admin.group_id} в группу {group_id}")
                    
                    new_admin.group_id = group_id
                    new_admin.is_verified = True  # Убеждаемся что админ активирован
                    new_admin.is_active = True   # Убеждаемся что админ активен
                    new_admin.is_group_member = True
            else:
                # Если новый админ не найден, создаем запись
                new_admin = User(
                    username=clean_username,
                    group_id=group_id,
                    is_verified=False,  # Будет активирован при первом входе в бот
                    is_active=True,
                    is_group_member=False
                )
                db.add(new_admin)
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Создана запись для нового администратора @{clean_username} группы '{group.name}'")
        
        group.admin_username = clean_username
    
    # Обновляем остальные поля группы
    update_data = group_data.model_dump(exclude_unset=True, exclude={'admin_username'})
    # days_of_week поддержка
    if 'days_of_week' in update_data and update_data['days_of_week'] is not None:
        update_data['days_of_week'] = ','.join(str(d) for d in update_data['days_of_week'])
    for field, value in update_data.items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    
    # Добавляем количество участников
    group.members_count = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True,
        User.is_group_member == True
    ).count()
    
    # Логируем изменение администратора
    if admin_changed:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Администратор группы '{group.name}' изменен с @{old_admin_username} на @{group.admin_username}")
    
    parse_days_of_week(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Удаляет группу и все связанные с ней данные.
    
    Выполняет следующие действия:
    1. Находит группу по group_id
    2. Каскадно удаляет всех пользователей этой группы и их ответы
    3. Удаляет саму группу
    
    Args:
        group_id (int): Идентификатор группы для удаления
        db (Session): Сессия базы данных
    
    Returns:
        None
    
    Raises:
        HTTPException: 404 если группа не найдена
    
    Examples:
        >>> # DELETE /api/groups/1
        >>> # Response: HTTP 204 No Content
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    # Каскадно удаляем всех пользователей этой группы и их ответы
    users = db.query(User).filter(User.group_id == group_id).all()
    for user in users:
        # Удаляем все ответы пользователя
        db.query(UserResponse).filter(UserResponse.user_id == user.id).delete()
        db.delete(user)
    # Удаляем саму группу
    db.delete(group)
    db.commit()


@router.post("/{group_id}/regenerate-token", response_model=GroupResponse)
async def regenerate_activation_token(group_id: int, db: Session = Depends(get_db)):
    """Перегенерирует токен активации для группы.
    
    Выполняет следующие действия:
    1. Находит группу по group_id
    2. Генерирует новый уникальный токен активации
    3. Сохраняет изменения в базе данных
    4. Возвращает обновлённую информацию о группе
    
    Args:
        group_id (int): Идентификатор группы
        db (Session): Сессия базы данных
    
    Returns:
        GroupResponse: Группа с новым токеном активации
    
    Raises:
        HTTPException: 404 если группа не найдена
    
    Examples:
        >>> # POST /api/groups/1/regenerate-token
        >>> # Response: GroupResponse с новым activation_token
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    # Генерируем новый токен
    group.activation_token = Group.generate_activation_token()
    db.commit()
    db.refresh(group)
    group.members_count = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True
    ).count()
    parse_days_of_week(group)
    return group


@router.get("/{group_id}/stats", response_model=GroupStats)
async def get_group_stats(
    group_id: int, 
    target_date: Optional[date] = Query(None, description="Дата для статистики (по умолчанию сегодня)"),
    db: Session = Depends(get_db)
):
    """Получает статистику по группе за выбранную дату.
    
    Выполняет следующие действия:
    1. Находит группу по group_id
    2. Считает общее количество участников, активных участников и количество ответов за дату
    3. Вычисляет процент ответивших
    4. Возвращает агрегированную статистику
    
    Args:
        group_id (int): Идентификатор группы
        target_date (date, optional): Дата для статистики (по умолчанию сегодня)
        db (Session): Сессия базы данных
    
    Returns:
        GroupStats: Статистика по группе
    
    Raises:
        HTTPException: 404 если группа не найдена
    
    Examples:
        >>> # GET /api/groups/1/stats?target_date=2024-07-10
        >>> # Response: GroupStats
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    if not target_date:
        target_date = date.today()
    # Общее количество участников
    total_members = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True,
        User.is_group_member == True
    ).count()
    # Активные участники (ответившие хотя бы раз)
    active_members = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True,
        User.is_group_member == True,
        User.responses.any()
    ).count()
    # Ответы за указанную дату
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    responses_today = db.query(UserResponse).join(User).filter(
        User.group_id == group_id,
        User.is_group_member == True,
        UserResponse.created_at >= start_datetime,
        UserResponse.created_at <= end_datetime
    ).count()
    # Вычисляем процент ответивших
    response_rate = (responses_today / total_members * 100) if total_members > 0 else 0
    return GroupStats(
        group_id=group_id,
        group_name=group.name,
        total_members=total_members,
        active_members=active_members,
        responses_today=responses_today,
        response_rate=round(response_rate, 2)
    )


@router.post("/join", response_model=dict)
async def join_group_by_token(
    activation_data: GroupActivation,
    user_id: str = Query(..., description="Telegram User ID пользователя"),
    db: Session = Depends(get_db)
):
    """Позволяет пользователю присоединиться к группе по токену активации.
    
    Выполняет следующие действия:
    1. Находит группу по токену активации
    2. Находит пользователя по user_id
    3. Проверяет, не состоит ли пользователь уже в группе
    4. Добавляет пользователя в группу
    5. Возвращает результат операции
    
    Args:
        activation_data (GroupActivation): Данные с токеном активации
        user_id (str): Telegram User ID пользователя
        db (Session): Сессия базы данных
    
    Returns:
        dict: Информация о результате присоединения
    
    Raises:
        HTTPException: 404 если группа или пользователь не найдены
    
    Examples:
        >>> # POST /api/groups/join
        >>> {"activation_token": "..."}, user_id=123456789
        >>> # Response: {"message": "Вы успешно присоединились...", ...}
    """
    # Находим группу по токену
    group = db.query(Group).filter(
        Group.activation_token == activation_data.activation_token,
        Group.is_active == True
    ).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Недействительный токен активации или группа неактивна"
        )
    # Находим пользователя
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    # Проверяем, не состоит ли уже в группе
    if user.group_id == group.id:
        return {"message": f"Вы уже являетесь участником группы '{group.name}'"}
    # Добавляем пользователя в группу
    user.group_id = group.id
    db.commit()
    return {
        "message": f"Вы успешно присоединились к группе '{group.name}'",
        "group_id": group.id,
        "group_name": group.name
    }


@router.put("/{group_id}/schedule", response_model=GroupResponse)
async def update_group_schedule(
    group_id: int,
    morning_hour: int = Query(..., ge=0, le=23, description="Час отправки вечерних сообщений (0-23)"),
    morning_minute: int = Query(..., ge=0, le=59, description="Минута отправки вечерних сообщений (0-59)"),
    timezone: str = Query("Asia/Bishkek", description="Временная зона группы"),
    days_of_week: Optional[str] = Query(None, description="Дни недели для рассылки (например, '0,1,2,3,4')"),
    db: Session = Depends(get_db)
):
    """Обновляет расписание рассылки для группы.
    
    Выполняет следующие действия:
    1. Находит группу по group_id
    2. Обновляет параметры расписания (время, дни недели, временную зону)
    3. Сохраняет изменения в базе данных
    4. Перезапускает планировщик для применения изменений
    5. Возвращает обновлённую информацию о группе
    
    Args:
        group_id (int): Идентификатор группы
        morning_hour (int): Час рассылки
        morning_minute (int): Минута рассылки
        timezone (str): Временная зона
        days_of_week (str, optional): Дни недели для рассылки
        db (Session): Сессия базы данных
    
    Returns:
        GroupResponse: Группа с обновлённым расписанием
    
    Raises:
        HTTPException: 404 если группа не найдена
    
    Examples:
        >>> # PUT /api/groups/1/schedule?morning_hour=10&morning_minute=0&timezone=Asia/Bishkek&days_of_week=0,1,2,3,4
        >>> # Response: GroupResponse
    Note:
        После изменения расписания планировщик автоматически перезапускается для применения новых настроек.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    # Обновляем расписание группы
    group.morning_hour = morning_hour
    group.morning_minute = morning_minute
    group.timezone = timezone
    if days_of_week is not None:
        group.days_of_week = days_of_week
    db.commit()
    db.refresh(group)
    # Перезапускаем планировщик для применения изменений
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()  # Это пересоздаст все задачи с новым расписанием
    except Exception as e:
        # Логируем ошибку, но не прерываем операцию
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка перезапуска планировщика после изменения расписания группы {group_id}: {e}")
    # Добавляем количество участников
    group.members_count = db.query(User).filter(
        User.group_id == group_id,
        User.is_verified == True
    ).count()
    parse_days_of_week(group)
    return group 