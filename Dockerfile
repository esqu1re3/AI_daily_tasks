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

# Запускаем систему через run_all.py
CMD ["python", "run_all.py"] 