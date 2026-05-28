from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ==================== Регистрация и логин ====================

class UserRegister(BaseModel):
    """Схема для регистрации"""
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserLogin(BaseModel):
    """Схема для логина"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Ответ с информацией о пользователе (без敏感ных данных)"""
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Ответ после успешной аутентификации"""
    user: UserResponse
    message: str


class WhoAmIResponse(BaseModel):
    """Ответ для /whoami"""
    user: Optional[UserResponse]
    authenticated: bool = True


# ==================== Сброс пароля ====================

class ForgotPasswordRequest(BaseModel):
    """Запрос на сброс пароля"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Запрос на установку нового пароля"""
    token: str
    new_password: str = Field(..., min_length=6)


class ResetPasswordResponse(BaseModel):
    """Ответ на сброс пароля"""
    message: str