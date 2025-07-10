# Docker развертывание AI Daily Tasks

## 🐳 Быстрый старт с Docker

### 1. Создание файла окружения

Создайте файл `.env` в корне проекта:

```bash
cp docker.env.example .env
```

Отредактируйте `.env` файл, указав свои реальные значения:

```env
GEMINI_API_KEY=your_actual_gemini_api_key
TG_BOT_TOKEN=your_actual_telegram_bot_token
ADMIN_ID=your_actual_telegram_user_id
GEMINI_MODEL=gemini-2.5-flash
```

### 2. Запуск через Docker Compose

```bash
# Сборка и запуск системы
docker-compose up --build -d

# Просмотр логов
docker-compose logs -f

# Остановка системы
docker-compose down
```

### 3. Альтернативный запуск через Docker напрямую

```bash
# Сборка образа
docker build -t ai-daily-tasks .

# Запуск контейнера
docker run -d \
  --name ai-daily-tasks \
  -p 8000:8000 \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  ai-daily-tasks
```

## 🌐 Доступ к сервисам

После запуска Docker контейнера будут доступны:

- **Админ панель**: http://localhost:8501
- **API документация**: http://localhost:8000/docs
- **Основное API**: http://localhost:8000

## 📊 Управление контейнером

```bash
# Просмотр логов
docker logs -f ai-daily-tasks

# Перезапуск контейнера
docker restart ai-daily-tasks

# Остановка контейнера
docker stop ai-daily-tasks

# Удаление контейнера
docker rm ai-daily-tasks

# Удаление образа
docker rmi ai-daily-tasks
```

## 🔧 Настройка и активация

1. **Откройте админ панель** по адресу http://localhost:8501

2. **Скопируйте ссылку активации** из админ панели:
   ```
   https://t.me/your_bot_name?start=group_activation
   ```

3. **Отправьте ссылку участникам команды** любым способом

4. **Участники переходят по ссылке** и автоматически активируются

## 📁 Структура данных

База данных сохраняется в директории `./data` на хосте, что обеспечивает персистентность данных при перезапуске контейнера.

## 🔄 Обновление системы

```bash
# Остановка системы
docker-compose down

# Получение обновлений кода
git pull

# Пересборка и запуск
docker-compose up --build -d
```

## 🐛 Решение проблем

### Контейнер не запускается

1. Проверьте файл `.env`:
   ```bash
   cat .env
   ```

2. Проверьте логи:
   ```bash
   docker-compose logs
   ```

### Порты заняты

Если порты 8000 или 8501 заняты, измените их в `docker-compose.yml`:

```yaml
ports:
  - "8080:8000"  # Изменить первый порт
  - "8502:8501"  # Изменить первый порт
```

### База данных не сохраняется

Убедитесь, что директория `./data` существует и доступна для записи:

```bash
mkdir -p ./data
chmod 755 ./data
```

## ⚡ Полезные команды

```bash
# Просмотр статуса контейнера
docker ps

# Вход в контейнер для отладки
docker exec -it ai-daily-tasks bash

# Просмотр использования ресурсов
docker stats ai-daily-tasks

# Бэкап базы данных
cp ./data/reports_backup.sqlite ./backup_$(date +%Y%m%d_%H%M%S).sqlite
```

## 🔐 Безопасность

- Никогда не коммитьте файл `.env` в Git
- Используйте Docker Secrets для продакшена
- Регулярно обновляйте базовый образ Python 
