from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.controllers import router as items_router
from app.auth.router import router as auth_router
import os

# Создаём приложение
app = FastAPI(
    title="REST API Lab",
    description="""## REST API для управления сущностью Item
### Возможности:
- **CRUD операции** с мягким удалением
- **Пагинация** списка элементов
- **Аутентификация и авторизация** (JWT, HttpOnly cookies)
- **OAuth 2.0** (вход через Yandex ID)
- **Сброс пароля** через email (токен в логах)

### Технологии:
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
""",
    version="4.0.0",
    contact={
        "name": "Мамонов А.А.",
        "url": "https://vk.com/d_jaker_b",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/api/docs" if os.getenv("ENV_MODE", "development") != "production" else None,
    redoc_url="/api/redoc" if os.getenv("ENV_MODE", "development") != "production" else None,
    openapi_url="/api/openapi.json" if os.getenv("ENV_MODE", "development") != "production" else None,
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(items_router)
app.include_router(auth_router)

# Простой health-check
@app.get("/health", tags=["Health"])
def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}

# Кастомизация OpenAPI для добавления схемы безопасности и замков
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Добавляем контактную информацию в схему OpenAPI
    if "info" in openapi_schema:
        openapi_schema["info"]["contact"] = {
            "name": "Мамонов А.А.",
            "url": "https://vk.com/d_jaker_b",
        }
    
    # Добавляем схему безопасности
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "cookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "Авторизация через HttpOnly cookie. После входа через `/auth/login` токен устанавливается автоматически."
        },
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Альтернативный способ: введите JWT токен в формате `Bearer <token>`"
        }
    }
    
    # Список путей, которые требуют авторизации
    protected_paths = [
        "/items",
        "/auth/logout",
        "/auth/logout-all",
        "/auth/refresh",
        "/auth/whoami",
    ]
    
    # Добавляем security к защищённым путям
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            # Проверяем, защищён ли путь
            is_protected = False
            for protected in protected_paths:
                if path.startswith(protected):
                    is_protected = True
                    break
            
            if is_protected:
                openapi_schema["paths"][path][method]["security"] = [{"cookieAuth": [], "bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Для запуска через python -m app.main (опционально)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)