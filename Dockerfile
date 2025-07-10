# Dockerfile для AI Daily Tasks
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порты
EXPOSE 8000 8501

# Инициализируем базу данных при первом запуске
RUN python migrations/init_users.py

# Создаем скрипт запуска для Docker
RUN echo '#!/bin/bash\n\
echo "🚀 Запуск AI Daily Tasks в Docker..."\n\
echo "🎛️ Запуск админ панели..."\n\
streamlit run admin_panel/dashboard.py --server.address 0.0.0.0 --server.port 8501 &\n\
echo "🤖 Запуск основного приложения..."\n\
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &\n\
echo "✅ Система запущена!"\n\
echo "🌐 Админ панель: http://localhost:8501"\n\
echo "🌐 API: http://localhost:8000"\n\
wait\n' > /app/start.sh && chmod +x /app/start.sh

# Запускаем систему через Docker скрипт
CMD ["/app/start.sh"] 
