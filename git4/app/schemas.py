from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ==================== Схемы для Item ====================

class ItemBase(BaseModel):
    """Базовая схема для Item"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Название предмета (обязательное поле, от 1 до 100 символов)",
        example="Ноутбук"
    )
    description: Optional[str] = Field(
        None,
        description="Описание предмета (необязательное поле)",
        example="Мощный игровой ноутбук с 32GB RAM"
    )
    status: str = Field(
        default="active",
        pattern="^(active|inactive)$",
        description="Статус предмета. Возможные значения: `active` (активный) или `inactive` (неактивный)",
        example="active"
    )


class ItemCreate(ItemBase):
    """Схема для создания нового Item (POST /items/)"""
    pass


class ItemUpdate(BaseModel):
    """Схема для частичного обновления Item (PATCH /items/{id})"""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Название предмета (от 1 до 100 символов)",
        example="Новое название"
    )
    description: Optional[str] = Field(
        None,
        description="Описание предмета",
        example="Новое описание"
    )
    status: Optional[str] = Field(
        None,
        pattern="^(active|inactive)$",
        description="Статус предмета",
        example="inactive"
    )


class ItemResponse(ItemBase):
    """Схема для ответа при получении Item (GET /items/, GET /items/{id})"""
    id: int = Field(..., description="Уникальный идентификатор предмета", example=1)
    user_id: int = Field(..., description="ID владельца предмета", example=1)
    created_at: Optional[datetime] = Field(None, description="Дата и время создания", example="2026-05-27T10:00:00Z")
    updated_at: Optional[datetime] = Field(None, description="Дата и время последнего обновления", example="2026-05-27T10:00:00Z")

    class Config:
        from_attributes = True


# ==================== Схемы для пагинации ====================

class PaginationParams(BaseModel):
    """Параметры пагинации"""
    page: int = Field(1, ge=1, description="Номер страницы (начиная с 1)", example=1)
    limit: int = Field(10, ge=1, le=100, description="Количество записей на странице (максимум 100)", example=10)


class PaginationMeta(BaseModel):
    """Мета-информация для пагинации"""
    total: int = Field(..., description="Общее количество записей", example=25)
    page: int = Field(..., description="Текущая страница", example=2)
    limit: int = Field(..., description="Количество записей на странице", example=10)
    total_pages: int = Field(..., description="Общее количество страниц", example=3)


class PaginatedResponse(BaseModel):
    """Ответ с пагинацией для списка Items"""
    data: List[ItemResponse] = Field(..., description="Массив элементов на текущей странице")
    meta: PaginationMeta = Field(..., description="Мета-информация о пагинации")


# ==================== Схемы для Auth ====================

class UserRegister(BaseModel):
    """Схема для регистрации пользователя (POST /auth/register)"""
    email: EmailStr = Field(..., description="Email пользователя (должен быть уникальным)", example="user@example.com")
    password: str = Field(
        ...,
        min_length=6,
        description="Пароль (минимум 6 символов)",
        example="securepassword123"
    )
    first_name: Optional[str] = Field(None, description="Имя пользователя", example="Иван")
    last_name: Optional[str] = Field(None, description="Фамилия пользователя", example="Петров")


class UserLogin(BaseModel):
    """Схема для входа в систему (POST /auth/login)"""
    email: EmailStr = Field(..., description="Email пользователя", example="user@example.com")
    password: str = Field(..., description="Пароль", example="securepassword123")


class UserResponse(BaseModel):
    """Ответ с информацией о пользователе (без чувствительных данных)"""
    id: int = Field(..., description="ID пользователя", example=1)
    email: str = Field(..., description="Email пользователя", example="user@example.com")
    first_name: Optional[str] = Field(None, description="Имя", example="Иван")
    last_name: Optional[str] = Field(None, description="Фамилия", example="Петров")
    created_at: Optional[datetime] = Field(None, description="Дата регистрации", example="2026-05-27T10:00:00Z")

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Ответ при успешной аутентификации (регистрация, логин, refresh)"""
    user: UserResponse = Field(..., description="Данные пользователя")
    message: str = Field(..., description="Сообщение о результате операции", example="Login successful")


class WhoAmIResponse(BaseModel):
    """Ответ для эндпоинта /whoami"""
    user: Optional[UserResponse] = Field(None, description="Данные пользователя (если авторизован)")
    authenticated: bool = Field(..., description="Флаг авторизации", example=True)


# ==================== Схемы для сброса пароля ====================

class ForgotPasswordRequest(BaseModel):
    """Запрос на сброс пароля (POST /auth/forgot-password)"""
    email: EmailStr = Field(..., description="Email пользователя", example="user@example.com")


class ResetPasswordRequest(BaseModel):
    """Запрос на установку нового пароля (POST /auth/reset-password)"""
    token: str = Field(..., description="Токен сброса пароля из email", example="abcdef123456...")
    new_password: str = Field(..., min_length=6, description="Новый пароль (минимум 6 символов)", example="newpassword123")