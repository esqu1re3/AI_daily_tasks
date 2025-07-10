# Makefile для AI Daily Tasks

.PHONY: help build up down logs restart status clean backup

# Default target
help:
	@echo "🤖 AI Daily Tasks - Docker управление"
	@echo "======================================"
	@echo ""
	@echo "Доступные команды:"
	@echo "  make build    - Сборка Docker образа"
	@echo "  make up       - Запуск системы"
	@echo "  make down     - Остановка системы"
	@echo "  make restart  - Перезапуск системы"
	@echo "  make logs     - Просмотр логов"
	@echo "  make status   - Статус контейнера"
	@echo "  make clean    - Очистка (удаление контейнера и образа)"
	@echo "  make backup   - Создание бэкапа базы данных"
	@echo ""
	@echo "🌐 После запуска доступно:"
	@echo "  Админ панель: http://localhost:8501"
	@echo "  API: http://localhost:8000"

# Сборка образа
build:
	@echo "🔨 Сборка Docker образа..."
	docker-compose build

# Запуск системы
up:
	@echo "🚀 Запуск системы..."
	docker-compose up -d
	@echo "✅ Система запущена!"
	@echo "🌐 Админ панель: http://localhost:8501"
	@echo "🌐 API: http://localhost:8000"

# Остановка системы
down:
	@echo "⏹️ Остановка системы..."
	docker-compose down
	@echo "✅ Система остановлена"

# Перезапуск системы
restart:
	@echo "🔄 Перезапуск системы..."
	docker-compose restart
	@echo "✅ Система перезапущена"

# Просмотр логов
logs:
	@echo "📋 Логи системы (Ctrl+C для выхода):"
	docker-compose logs -f

# Статус контейнера
status:
	@echo "📊 Статус контейнера:"
	docker-compose ps
	@echo ""
	@echo "📈 Использование ресурсов:"
	docker stats ai-daily-tasks --no-stream || echo "Контейнер не запущен"

# Очистка
clean:
	@echo "🧹 Очистка Docker ресурсов..."
	docker-compose down
	docker-compose rm -f
	docker rmi ai-daily-tasks_ai-daily-tasks 2>/dev/null || echo "Образ уже удален"
	@echo "✅ Очистка завершена"

# Бэкап базы данных
backup:
	@echo "💾 Создание бэкапа базы данных..."
	@if [ -f "./data/reports_backup.sqlite" ]; then \
		cp ./data/reports_backup.sqlite ./backup_$$(date +%Y%m%d_%H%M%S).sqlite && \
		echo "✅ Бэкап создан: backup_$$(date +%Y%m%d_%H%M%S).sqlite"; \
	else \
		echo "❌ База данных не найдена"; \
	fi

# Полная установка (с настройкой .env)
install:
	@echo "📦 Первоначальная настройка..."
	@if [ ! -f ".env" ]; then \
		cp docker.env.example .env && \
		echo "✅ Файл .env создан из примера"; \
		echo "⚠️  Отредактируйте .env файл и укажите свои API ключи!"; \
	else \
		echo "✅ Файл .env уже существует"; \
	fi
	@mkdir -p ./data
	@echo "✅ Директория данных создана"
	@echo "📝 Теперь запустите: make up" 