FROM python:3.12-slim

# Создаём непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 sagauser

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Каталог БД (монтируется томом) и права пользователя
RUN mkdir -p /app/db /app/assets && chown -R sagauser:sagauser /app

USER sagauser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]