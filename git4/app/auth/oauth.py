import os
import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from app.models import User, UserSession
from app.auth.utils import hash_password, create_access_token, create_refresh_token
import hashlib
from datetime import datetime, timedelta, timezone

# Yandex OAuth URLs
YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_INFO_URL = "https://login.yandex.ru/info"


class OAuthService:

    @staticmethod
    def get_yandex_auth_url(state: str) -> str:
        """Формирует URL для редиректа на Yandex"""
        client_id = os.getenv("YANDEX_CLIENT_ID")
        callback_url = os.getenv("YANDEX_CALLBACK_URL")

        return (
            f"{YANDEX_AUTH_URL}?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={callback_url}&"
            f"state={state}"
        )

    @staticmethod
    async def exchange_code_for_token(code: str) -> dict:
        """Обменивает код на токен доступа Yandex"""
        client_id = os.getenv("YANDEX_CLIENT_ID")
        client_secret = os.getenv("YANDEX_CLIENT_SECRET")
        callback_url = os.getenv("YANDEX_CALLBACK_URL")

        print(f"Exchange code: client_id={client_id[:10] if client_id else 'None'}..., callback_url={callback_url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                YANDEX_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": callback_url,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            print(f"Token response status: {response.status_code}")
            print(f"Token response body: {response.text[:200] if response.text else 'empty'}")

            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to exchange code: {response.text}")

            return response.json()

    @staticmethod
    async def get_yandex_user_info(access_token: str) -> dict:
        """Получает информацию о пользователе от Yandex"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                YANDEX_USER_INFO_URL,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access_token}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")

            data = response.json()

            # Yandex может вернуть email в разных полях
            if "default_email" not in data:
                # Если нет default_email, ищем emails
                emails = data.get("emails", [])
                if emails:
                    data["default_email"] = emails[0]
                else:
                    # Заглушка – используем логин как email
                    data["default_email"] = f"{data.get('login', 'unknown')}@yandex.ru"

            return data

    @staticmethod
    async def login_or_create_user(db: Session, yandex_data: dict, user_agent: str = None, ip_address: str = None):
        """Находит или создаёт пользователя по данным от Yandex"""
        yandex_id = str(yandex_data.get("id"))
        email = yandex_data.get("default_email", "")

        # Если email пустой, используем логин
        if not email:
            login = yandex_data.get("login", "")
            email = f"{login}@yandex.ru"

        first_name = yandex_data.get("first_name", "")
        last_name = yandex_data.get("last_name", "")

        print(f"Looking for user: yandex_id={yandex_id}, email={email}")

        # Ищем пользователя по yandex_id
        user = db.query(User).filter(User.yandex_id == yandex_id, User.deleted_at.is_(None)).first()

        if not user:
            # Ищем по email
            user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
            if user:
                # Обновляем yandex_id у существующего пользователя
                print(f"Existing user found by email: {user.id}")
                user.yandex_id = yandex_id
                db.commit()
                db.refresh(user)
            else:
                # Создаём нового пользователя
                print(f"Creating new user with email: {email}")
                user = User(
                    email=email,
                    yandex_id=yandex_id,
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=None,
                    salt=None
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"New user created: {user.id}")

        # Генерируем токены
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