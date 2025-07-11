import logging
import time
import threading
from telebot import TeleBot, types
from telebot.handler_backends import ContinueHandling
from app.config import settings
from app.services.gemini_service import GeminiService
from app.services.bot_service import BotService

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Класс Telegram бота для системы AI Daily Tasks.
    
    Управляет взаимодействием с Telegram API, обработкой команд и сообщений.
    Интегрируется с BotService для бизнес-логики.
    
    Attributes:
        bot: Экземпляр TeleBot для работы с Telegram API.
        gemini_service: Экземпляр GeminiService для AI-функций.
        bot_service: Экземпляр BotService для обработки логики.
    
    Examples:
        >>> bot_instance = TelegramBot()
        >>> bot_instance.run()
        # Бот запущен и готов принимать сообщения
    """
    def __init__(self):
        self.bot = TeleBot(settings.TG_BOT_TOKEN, threaded=True)
        self.gemini_service = GeminiService()
        self.bot_service = BotService(self.gemini_service)
        self._setup_handlers()

    def _setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            try:
                user = message.from_user
                chat_type = message.chat.type
                logger.info(f"Start command from user {user.id} (@{user.username}) in {chat_type}")
                
                # Обрабатываем только личные сообщения
                if chat_type == 'private':
                    self.bot_service.handle_user_message_sync(message, self.bot)
                
            except Exception as e:
                logger.error(f"Error in start command: {e}")
                if message.chat.type == 'private':
                    self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке команды")

        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            """Обработчик команды /help"""
            try:
                chat_type = message.chat.type
                if chat_type == 'private':
                    help_text = (
                        "🤖 *Бот для сбора вечерних планов команды*\n\n"
                        "📋 *Основные функции:*\n"
                        "• Сбор планов от участников команды\n"
                        "• Автоматическая генерация сводки\n"
                        "• Ежедневные вечерние опросы\n\n"
                        "🔗 *Как начать:*\n"
                        "1. Перейдите по ссылке активации от администратора\n"
                        "2. Отвечайте на вечерние сообщения бота\n"
                        "3. Получите доступ к системе планирования\n\n"
                        "⏰ *Время опросов:* 17:30 (UTC+6)\n"
                        "📝 *Формат ответа:* свободный текст с планами на день\n\n"
                        "🔄 *Команды:*\n"
                        "• /change - изменить сегодняшний план\n"
                        "• /help - показать эту справку"
                    )
                    self.bot.send_message(message.chat.id, help_text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Error in help command: {e}")

        @self.bot.message_handler(commands=['admin'])
        def handle_admin(message):
            """Обработчик команды /admin для активации администраторов"""
            try:
                self.bot_service.handle_admin_command(message, self.bot)
            except Exception as e:
                logger.error(f"Error in admin command: {e}")
                if message.chat.type == 'private':
                    self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке команды")

        @self.bot.message_handler(commands=['change'])
        def handle_change(message):
            """Обработчик команды /change для редактирования плана"""
            try:
                user = message.from_user
                chat_type = message.chat.type
                logger.info(f"Change command from user {user.id} (@{user.username}) in {chat_type}")
                
                # Обрабатываем только личные сообщения
                if chat_type == 'private':
                    self.bot_service.handle_change_command(message, self.bot)
                
            except Exception as e:
                logger.error(f"Error in change command: {e}")
                if message.chat.type == 'private':
                    self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке команды")

        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def handle_text_message(message):
            """Обработчик текстовых сообщений"""
            try:
                # Обрабатываем только личные сообщения
                if message.chat.type == 'private':
                    self.bot_service.handle_user_message_sync(message, self.bot)
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                if message.chat.type == 'private':
                    self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке сообщения")

    def run(self):
        """Запуск бота в режиме polling.
        
        Запускает бесконечный цикл обработки сообщений с обработкой ошибок
        и автоматическим перезапуском при сбоях.
        
        Note:
            Работает в non-stop режиме с таймаутами для стабильности.
            При ошибках перезапускается через 5 секунд.
        """
        logger.info("Starting Telegram bot in polling mode...")
        
        try:
            # Запускаем бота в бесконечном цикле
            self.bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                none_stop=True,
                interval=1
            )
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            # Повторный запуск через 5 секунд в случае ошибки
            time.sleep(5)
            self.run()
        finally:
            logger.info("Bot polling stopped")

    def stop(self):
        """Остановка бота"""
        try:
            self.bot.stop_polling()
            logger.info("Bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

    def send_message(self, chat_id, text, **kwargs):
        """Отправка сообщения"""
        try:
            return self.bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None