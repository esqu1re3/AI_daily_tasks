#!/bin/bash

# Скрипт для быстрого запуска AI Daily Tasks в Docker

set -e

echo "🤖 AI Daily Tasks - Docker deployment"
echo "====================================="

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и повторите попытку."
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose и повторите попытку."
    exit 1
fi

# Проверяем наличие файла .env
if [ ! -f ".env" ]; then
    echo "📝 Файл .env не найден. Создаем из примера..."
    if [ -f "docker.env.example" ]; then
        cp docker.env.example .env
        echo "✅ Файл .env создан из примера"
        echo "⚠️  ВАЖНО: Отредактируйте файл .env и укажите свои реальные значения:"
        echo "   - GEMINI_API_KEY"
        echo "   - TG_BOT_TOKEN" 
        echo "   - ADMIN_ID"
        echo ""
        read -p "Нажмите Enter после редактирования .env файла..."
    else
        echo "❌ Файл docker.env.example не найден. Создайте файл .env вручную."
        exit 1
    fi
fi

# Создаем директорию для данных
mkdir -p ./data

echo "🔨 Сборка и запуск контейнера..."
docker-compose up --build -d

echo ""
echo "✅ Система запущена!"
echo ""
echo "🌐 Доступные сервисы:"
echo "   - Админ панель: http://localhost:8501"
echo "   - API: http://localhost:8000"
echo "   - API документация: http://localhost:8000/docs"
echo ""
echo "📊 Полезные команды:"
echo "   docker-compose logs -f          # Просмотр логов"
echo "   docker-compose down             # Остановка системы"
echo "   docker-compose restart          # Перезапуск"
echo ""
echo "📖 Подробная документация: DOCKER_README.md" 
