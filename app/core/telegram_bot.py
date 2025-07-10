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
                logger.info(f"Start command from user {user.id} (@{user.username})")
                
                # Вызываем логику верификации из BotService
                self.bot_service.handle_user_message_sync(message, self.bot)
                
            except Exception as e:
                logger.error(f"Error in start command: {e}")
                self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке команды")

        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def handle_text_message(message):
            """Обработчик текстовых сообщений"""
            try:
                # Передаем обработку в BotService
                self.bot_service.handle_user_message_sync(message, self.bot)
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                self.bot.reply_to(message, "⚠️ Произошла ошибка при обработке сообщения")

    def run(self):
        """Запуск бота в режиме polling"""
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

    def send_message(self, chat_id, text):
        """Отправка сообщения"""
        try:
            return self.bot.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None