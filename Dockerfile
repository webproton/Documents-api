# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Не писать .pyc + логирование сразу в stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Рабочая директория
WORKDIR /app

# Системные зависимости (важно для psycopg2, pillow и т.д.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --no-cache-dir poetry

# Копируем только файлы зависимостей сначала (кэш Docker)
COPY pyproject.toml poetry.lock* /app/

# Отключаем создание venv внутри контейнера
RUN poetry config virtualenvs.create false

# Устанавливаем зависимости
RUN poetry install --no-interaction --no-ansi --no-root
# Копируем весь проект
COPY . /app/

# Порт Django
EXPOSE 8000

# Команда запуска (dev вариант)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]