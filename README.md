# REST API Lab (FastAPI + PostgreSQL + Docker)

## Лабораторные работы №2, №3, №4

### Краткое описание проекта
Проект реализует REST API для управления сущностью `Item` с полным CRUD, мягким удалением, пагинацией, а также полноценную систему аутентификации и авторизации (JWT, OAuth2 Yandex, сброс пароля). API полностью документировано с помощью OpenAPI (Swagger).

### Технологии
- **FastAPI** — веб-фреймворк
- **PostgreSQL 16** — база данных
- **SQLAlchemy ORM** — работа с БД
- **Alembic** — миграции
- **JWT (python-jose)** — токены доступа
- **bcrypt** — хеширование паролей
- **Docker & Docker Compose** — контейнеризация

---

## Инструкция по запуску

### Требования
- Установленный Docker Desktop

### Запуск

1. Клонируйте репозиторий:
    ```bash
    git clone <ссылка на репозиторий>
    cd <папка проекта>
2. Создайте файл .env на основе .env.example:

    ```bash
    cp .env.example .env
3. Запустите приложение:
    ```bash
    docker-compose up --build
4. API будет доступно:
   - Swagger UI (документация): http://localhost:8000/api/docs
   - Health check: http://localhost:8000/health
   - ReDoc: http://localhost:8000/api/redocs

## Режимы запуска
    - ENV_MODE=development — документация доступна (по умолчанию)
    - ENV_MODE=production — документация скрыта (404)

## Пример файла переменных окружения (.env.example)

  ```ini
# Режим запуска
ENV_MODE=development

# База данных
DB_USER=student
DB_PASSWORD=student_secure_password
DB_NAME=wp_labs
DB_HOST=postgres
DB_PORT=5432
PORT=8000

# JWT настройки
JWT_ACCESS_SECRET=super_secret_access_key_change_in_prod
JWT_REFRESH_SECRET=super_secret_refresh_key_change_in_prod
JWT_ACCESS_EXPIRATION_MINUTES=15
JWT_REFRESH_EXPIRATION_DAYS=7

# OAuth Yandex
YANDEX_CLIENT_ID=your_client_id_here
YANDEX_CLIENT_SECRET=your_client_secret_here
YANDEX_CALLBACK_URL=http://localhost:8000/auth/oauth/yandex/callback
```

## Описание API

### Эндпоинты аутентификации (`/auth`)

| Метод   | URL                              | Описание                                      | Доступ         |
|---------|----------------------------------|-----------------------------------------------|----------------|
| POST    | `/auth/register`                 | Регистрация нового пользователя               |    Public      |
| POST    | `/auth/login`                    | Вход, установка cookies с токенами            |    Public      |
| POST    | `/auth/refresh`                  | Обновление пары токенов                       |    Private     |
| GET     | `/auth/whoami`                   | Проверка авторизации и получение данных       |    Private     |
| POST    | `/auth/logout`                   | Завершение текущей сессии                     |    Private     |
| POST    | `/auth/logout-all`               | Завершение всех сессий пользователя           |    Private     |
| POST    | `/auth/forgot-password`          | Запрос на сброс пароля                        |    Public      |
| POST    | `/auth/reset-password`           | Установка нового пароля по токену             |    Public      |
| GET     | `/auth/oauth/yandex`             | Инициация входа через Yandex ID               |    Public      |
| GET     | `/auth/oauth/yandex/callback`    | Обработка ответа от Yandex                    |    Public      |

## Эндпоинты ресурса `Item` (`/items`)

| Метод   | URL             | Описание                                    | Доступ    |
|---------|-----------------|---------------------------------------------|-----------|
| GET     | `/items/`       | Список с пагинацией (только свои записи)    | Private   |
| POST    | `/items/`       | Создание нового item                        | Private   |
| GET     | `/items/{id}`   | Получение одного item                       | Private   |
| PUT     | `/items/{id}`   | Полное обновление                           | Private   |
| PATCH   | `/items/{id}`   | Частичное обновление                        | Private   |
| DELETE  | `/items/{id}`   | Мягкое удаление                             | Private   |

## Health check

| Метод | URL        | Описание                            | Доступ  |
|-------|------------|-------------------------------------|---------|
| GET   | `/health`  | Проверка работоспособности сервиса  | Public  |

## Пример запроса:

```http
GET /items/?page=2&limit=5
```

## Пример ответа:
```json
{
  "data": [
    {
      "id": 1,
      "name": "Ноутбук",
      "description": "Игровой ноутбук",
      "status": "active",
      "user_id": 1,
      "created_at": "2026-05-27T10:00:00Z",
      "updated_at": "2026-05-27T10:00:00Z"
    }
  ],
  "meta": {
    "total": 25,
    "page": 2,
    "limit": 5,
    "total_pages": 5
  }
}
```
## Документация API (Swagger)
### Доступ
- Документация доступна по адресу: http://localhost:8000/api/docs
- Только в режиме разработки (ENV_MODE=development)

### Возможности Swagger UI
- ✅ Интерактивное тестирование всех эндпоинтов
- ✅ Авторизация через кнопку Authorize
- ✅ Поддержка HttpOnly cookies (после логина)
- ✅ Поддержка Bearer токенов
- ✅ Примеры запросов и ответов
- ✅ Описание всех схем данных

### Тестирование защищённых эндпоинтов
1. Выполните POST /auth/register — создайте пользователя
2. Выполните POST /auth/login — войдите в систему
3. Теперь все защищённые эндпоинты (/items/*, /auth/logout и т.д.) доступны для тестирования

## Миграции базы данных
Миграции применяются автоматически при запуске контейнера (entrypoint.sh).
Для ручного управления:
```bash
# Применить все миграции
docker exec -it wp_labs_app alembic upgrade head

# Создать новую миграцию
docker exec -it wp_labs_app alembic revision --autogenerate -m "описание изменений"
```

## Настройка OAuth (Yandex ID)
1. Зарегистрируйте приложение на https://oauth.yandex.ru/
2. Укажите Callback URI: http://localhost:8000/auth/oauth/yandex/callback
3. Добавьте в .env полученные YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET
4. Перезапустите контейнеры

## Безопасность
- Хеширование паролей: bcrypt с уникальной солью для каждого пользователя
- Токены: Access (15 мин) и Refresh (7 дней) в HttpOnly cookies
- Хранение Refresh токенов: в БД в хешированном виде
- Защита от CSRF: проверка параметра state в OAuth
- Изоляция данных: пользователи видят только свои items

## Остановка и очистка
```bash
# Остановить контейнеры
docker-compose down

# Остановить и удалить все данные (включая volume БД)
docker-compose down -v
