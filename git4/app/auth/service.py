from sqlalchemy.orm import Session
from app.models import User, UserSession, PasswordResetToken
from app.auth.utils import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
import hashlib
import secrets
import os
from datetime import datetime, timedelta, timezone


class AuthService:

    # ==================== Регистрация и логин ====================

    @staticmethod
    def register(db: Session, email: str, password: str, first_name: str = None, last_name: str = None) -> User:
        """Регистрация нового пользователя"""
        # Проверка на существование
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("User with this email already exists")

        # Хеширование пароля (соль генерируется автоматически внутри hash_password)
        hashed = hash_password(password)

        user = User(
            email=email,
            password_hash=hashed,
            first_name=first_name,
            last_name=last_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, email: str, password: str, user_agent: str = None, ip_address: str = None):
        """Аутентификация и создание сессии"""
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if not user or not user.password_hash:
            raise ValueError("Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        # Генерация токенов
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # Хешируем refresh_token для хранения в БД
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Сохраняем сессию
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(session)
        db.commit()

        return user, access_token, refresh_token

    # ==================== Управление сессиями ====================

    @staticmethod
    def refresh(db: Session, refresh_token: str, user_agent: str = None, ip_address: str = None):
        """Обновление токенов"""
        payload = decode_token(refresh_token, "refresh")
        if not payload:
            raise ValueError("Invalid refresh token")

        user_id = int(payload.get("sub"))
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Проверяем, существует ли сессия и не отозвана ли
        session = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.refresh_token_hash == refresh_token_hash,
            UserSession.is_revoked == False,
            UserSession.expires_at > datetime.now(timezone.utc)
        ).first()

        if not session:
            raise ValueError("Invalid or expired refresh token")

        # Обновляем сессию (создаём новую, старую отзываем)
        session.is_revoked = True

        # Создаём новые токены
        new_access = create_access_token({"sub": str(user_id)})
        new_refresh = create_refresh_token({"sub": str(user_id)})

        new_refresh_hash = hashlib.sha256(new_refresh.encode()).hexdigest()

        new_session = UserSession(
            user_id=user_id,
            refresh_token_hash=new_refresh_hash,
            user_agent=user_agent or session.user_agent,
            ip_address=ip_address or session.ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(new_session)
        db.commit()

        return new_access, new_refresh

    @staticmethod
    def logout(db: Session, user_id: int, refresh_token: str):
        """Завершение текущей сессии"""
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        session = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.refresh_token_hash == refresh_token_hash,
            UserSession.is_revoked == False
        ).first()

        if session:
            session.is_revoked = True
            db.commit()

    @staticmethod
    def logout_all(db: Session, user_id: int):
        """Завершение всех сессий пользователя"""
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False
        ).update({"is_revoked": True})
        db.commit()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Получение пользователя по ID"""
        return db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()

    # ==================== Сброс пароля ====================

    @staticmethod
    def create_password_reset_token(db: Session, email: str) -> str:
        """Создаёт токен для сброса пароля"""
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if not user:
            # Не раскрываем, существует ли пользователь (безопасность)
            return None

        # Генерируем случайный токен
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Удаляем старые неиспользованные истекшие токены
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at < datetime.now(timezone.utc)
        ).delete()

        # Создаём новый токен
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        db.add(reset_token)
        db.commit()

        return raw_token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        """Сбрасывает пароль по токену"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not reset_token:
            raise ValueError("Invalid or expired token")

        user = reset_token.user
        if not user:
            raise ValueError("User not found")

        # Обновляем пароль
        user.password_hash = hash_password(new_password)
        reset_token.is_used = True

        # Отзываем все сессии пользователя (безопасность)
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_revoked == False
        ).update({"is_revoked": True})

        db.commit()
        return True