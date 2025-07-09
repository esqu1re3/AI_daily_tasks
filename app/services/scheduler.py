# Планировщик задач (утренний и вечерний опрос)
# ✅ services/scheduler.py
import asyncio
import telebot
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.report import Report

logger = logging.getLogger(__name__)

# Создаем экземпляр бота
bot = telebot.TeleBot(settings.TG_BOT_TOKEN)
scheduler = BackgroundScheduler()

# ID администратора - получаем из настроек
try:
    ADMIN_ID = int(settings.ADMIN_ID) if settings.ADMIN_ID else None
except (ValueError, TypeError):
    ADMIN_ID = None

# --- Синхронные рассылки (telebot не требует async) ---
def send_morning_message():
    """Утренняя рассылка"""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        for user in users:
            try:
                bot.send_message(
                    chat_id=int(user.telegram_id), 
                    text="🌅 Доброе утро! Что планируешь сегодня?"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки утреннего сообщения пользователю {user.telegram_id}: {e}")
    finally:
        db.close()

def send_evening_message():
    """Вечерняя рассылка"""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        for user in users:
            try:
                bot.send_message(
                    chat_id=int(user.telegram_id), 
                    text="🌙 Вечер добрый! Что удалось выполнить?"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки вечернего сообщения пользователю {user.telegram_id}: {e}")
    finally:
        db.close()
    
    # После вечерней рассылки отправляем сводку админу
    send_summary_to_admin()

# --- Выжимка для администратора ---
def send_summary_to_admin():
    """Отправка ежедневной сводки администратору"""
    if not ADMIN_ID:
        logger.warning("ADMIN_ID не настроен, сводка не будет отправлена")
        return
        
    db = SessionLocal()
    try:
        today = datetime.today().date()
        users = db.query(User).filter(User.is_active == True).all()

        text = f"📊 Ежедневный отчёт за {today}:\n\n"
        
        for user in users:
            morning_reports = db.query(Report).filter(
                Report.user_id == user.id,
                Report.type == "morning",
                Report.created_at >= datetime.combine(today, datetime.min.time())
            ).all()

            evening_reports = db.query(Report).filter(
                Report.user_id == user.id,
                Report.type == "evening",
                Report.created_at >= datetime.combine(today, datetime.min.time())
            ).all()

            text += f"👤 {user.username or user.full_name}:\n"
            text += f"🌅 Утро:\n"
            if morning_reports:
                text += "\n".join(f" - {r.content}" for r in morning_reports) + "\n"
            else:
                text += " - Нет ответа\n"
                
            text += f"🌙 Вечер:\n"
            if evening_reports:
                text += "\n".join(f" - {r.content}" for r in evening_reports) + "\n"
            else:
                text += " - Нет ответа\n"
            text += "\n"

        # Отправляем сводку администратору
        try:
            # Разбиваем длинные сообщения на части (лимит Telegram ~4096 символов)
            if len(text) > 4000:
                # Разбиваем по пользователям
                parts = text.split("👤 ")
                header = parts[0]
                bot.send_message(chat_id=ADMIN_ID, text=header)
                
                for part in parts[1:]:
                    if part.strip():
                        bot.send_message(chat_id=ADMIN_ID, text=f"👤 {part}")
            else:
                bot.send_message(chat_id=ADMIN_ID, text=text)
        except Exception as e:
            logger.error(f"Ошибка отправки сводки админу: {e}")
            
    finally:
        db.close()

# --- Запуск планировщика ---
def start_scheduler():
    """Запуск планировщика задач"""
    try:
        # Утренняя рассылка в 9:00
        scheduler.add_job(
            send_morning_message, 
            'cron', 
            hour=9, 
            minute=0,
            id='morning_message'
        )
        
        # Вечерняя рассылка в 18:00
        scheduler.add_job(
            send_evening_message, 
            'cron', 
            hour=18, 
            minute=0,
            id='evening_message'
        )
        
        scheduler.start()
        logger.info("✅ Scheduler started")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска планировщика: {e}")

def stop_scheduler():
    """Остановка планировщика"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("✅ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Ошибка остановки планировщика: {e}")
