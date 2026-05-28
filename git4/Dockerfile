FROM python:3.11-slim

WORKDIR /app

# Устанавливаем netcat для проверки готовности PostgreSQL
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения (папка app и остальные файлы)
COPY . .

# Копируем скрипт входа и делаем его исполняемым
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Команда по умолчанию (будет переопределена в entrypoint)
ENTRYPOINT ["/entrypoint.sh"]