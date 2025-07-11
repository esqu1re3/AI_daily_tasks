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


@router.get("/", response_model=List[GroupResponse])
async def get_groups(
    skip: int = Query(0, ge=0, description="Количество групп для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество групп"),
    active_only: bool = Query(True, description="Показывать только активные группы"),
    db: Session = Depends(get_db)
):
    """Получить список всех групп"""
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
    
    return group


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    """Создать новую группу"""
    
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
    
    new_group = Group(**group_dict)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    new_group.members_count = 0

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
    
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Удалить группу (деактивировать)"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )
    
    # Деактивируем группу вместо удаления
    group.is_active = False
    
    # Убираем пользователей из группы
    db.query(User).filter(User.group_id == group_id).update({"group_id": None})
    
    db.commit()


@router.post("/{group_id}/regenerate-token", response_model=GroupResponse)
async def regenerate_activation_token(group_id: int, db: Session = Depends(get_db)):
    """Перегенерировать токен активации группы"""
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
    
    return group


@router.get("/{group_id}/stats", response_model=GroupStats)
async def get_group_stats(
    group_id: int, 
    target_date: Optional[date] = Query(None, description="Дата для статистики (по умолчанию сегодня)"),
    db: Session = Depends(get_db)
):
    """Получить статистику группы"""
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
    """Присоединиться к группе по токену активации"""
    
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
    db: Session = Depends(get_db)
):
    """Обновить расписание рассылки для группы"""
    
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
    
    return group 