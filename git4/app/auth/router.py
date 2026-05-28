from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import service as AuthService
from app.auth import schemas
from app.auth.utils import decode_token
from app.auth.oauth import OAuthService
import secrets
import time

router = APIRouter(prefix="/auth", tags=["Auth"])

# Временное хранилище для state
state_storage = {}


def save_state(state: str):
    state_storage[state] = {"created_at": time.time()}


def get_state(state: str):
    data = state_storage.get(state)
    if data and time.time() - data["created_at"] < 600:
        return state
    return None


def delete_state(state: str):
    if state in state_storage:
        del state_storage[state]


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=15 * 60,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/"
    )


# ==================== Регистрация (PUBLIC) ====================
@router.post(
    "/register",
    status_code=201,
    response_model=schemas.AuthResponse,
    summary="Регистрация нового пользователя",
    description="Создаёт нового пользователя с указанными email, паролем и именем. Пароль хешируется перед сохранением.",
    responses={
        201: {"description": "Пользователь успешно зарегистрирован"},
        400: {"description": "Пользователь с таким email уже существует"},
        422: {"description": "Ошибка валидации (некорректный email или короткий пароль)"}
    }
)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    try:
        user = AuthService.AuthService.register(
            db,
            user_data.email,
            user_data.password,
            user_data.first_name,
            user_data.last_name
        )
        return schemas.AuthResponse(
            user=schemas.UserResponse.model_validate(user),
            message="User registered successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Логин (PUBLIC) ====================
@router.post(
    "/login",
    response_model=schemas.AuthResponse,
    summary="Вход в систему",
    description="Аутентификация пользователя по email и паролю. При успехе устанавливает HttpOnly cookies с access и refresh токенами.",
    responses={
        200: {"description": "Успешный вход, токены установлены в cookies"},
        401: {"description": "Неверный email или пароль"}
    }
)
def login(
    user_data: schemas.UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    try:
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        user, access_token, refresh_token = AuthService.AuthService.login(
            db, user_data.email, user_data.password, user_agent, ip_address
        )

        set_auth_cookies(response, access_token, refresh_token)

        return schemas.AuthResponse(
            user=schemas.UserResponse.model_validate(user),
            message="Login successful"
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ==================== Обновление токенов (PROTECTED) ====================
@router.post(
    "/refresh",
    response_model=schemas.AuthResponse,
    summary="Обновление токенов",
    description="Использует refresh token из cookies для получения новой пары access и refresh токенов. Требует авторизации.",
    responses={
        200: {"description": "Токены успешно обновлены"},
        401: {"description": "Refresh token не найден или недействителен"}
    }
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        new_access, new_refresh = AuthService.AuthService.refresh(
            db, refresh_token, user_agent, ip_address
        )

        payload = decode_token(new_access, "access")
        user_id = int(payload.get("sub"))
        user = AuthService.AuthService.get_user_by_id(db, user_id)

        set_auth_cookies(response, new_access, new_refresh)

        return schemas.AuthResponse(
            user=schemas.UserResponse.model_validate(user),
            message="Tokens refreshed"
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ==================== Проверка авторизации (PROTECTED) ====================
@router.get(
    "/whoami",
    response_model=schemas.WhoAmIResponse,
    summary="Проверка авторизации",
    description="Возвращает данные текущего авторизованного пользователя. Если пользователь не авторизован, возвращает authenticated: false.",
    responses={
        200: {"description": "Успешный ответ с данными пользователя или authenticated: false"}
    }
)
def whoami(request: Request, db: Session = Depends(get_db)):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return schemas.WhoAmIResponse(user=None, authenticated=False)

    payload = decode_token(access_token, "access")
    if not payload:
        return schemas.WhoAmIResponse(user=None, authenticated=False)

    user_id = int(payload.get("sub"))
    user = AuthService.AuthService.get_user_by_id(db, user_id)

    if not user:
        return schemas.WhoAmIResponse(user=None, authenticated=False)

    return schemas.WhoAmIResponse(
        user=schemas.UserResponse.model_validate(user),
        authenticated=True
    )


# ==================== Выход из системы (PROTECTED) ====================
@router.post(
    "/logout",
    summary="Выход из текущей сессии",
    description="Завершает текущую сессию пользователя: отзывает refresh token и удаляет cookies. Требует авторизации.",
    responses={
        200: {"description": "Успешный выход"},
        401: {"description": "Не авторизован"}
    }
)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        payload = decode_token(refresh_token, "refresh")
        if payload:
            user_id = int(payload.get("sub"))
            AuthService.AuthService.logout(db, user_id, refresh_token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return {"message": "Logged out"}


# ==================== Выход из всех сессий (PROTECTED) ====================
@router.post(
    "/logout-all",
    summary="Выход из всех сессий",
    description="Завершает все активные сессии пользователя. Полезно при смене пароля или подозрении на взлом. Требует авторизации.",
    responses={
        200: {"description": "Все сессии завершены"},
        401: {"description": "Не авторизован"}
    }
)
def logout_all(request: Request, response: Response, db: Session = Depends(get_db)):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(access_token, "access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = int(payload.get("sub"))
    AuthService.AuthService.logout_all(db, user_id)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return {"message": "All sessions terminated"}


# ==================== OAuth Yandex (PUBLIC) ====================
@router.get(
    "/oauth/yandex",
    summary="Инициация входа через Yandex ID",
    description="Перенаправляет пользователя на страницу авторизации Yandex ID.",
    responses={
        302: {"description": "Редирект на страницу авторизации Yandex"}
    }
)
async def oauth_yandex_login(response: Response):
    state = secrets.token_urlsafe(32)
    save_state(state)
    auth_url = OAuthService.get_yandex_auth_url(state)
    return Response(status_code=302, headers={"Location": auth_url})


@router.get(
    "/oauth/yandex/callback",
    summary="Callback для Yandex ID",
    description="Обрабатывает callback от Yandex после авторизации.",
    responses={
        302: {"description": "Успешная авторизация, редирект на /api/docs"},
        400: {"description": "Ошибка при обработке callback"}
    }
)
async def oauth_yandex_callback(
    request: Request,
    code: str = None,
    state: str = None,
    db: Session = Depends(get_db)
):
    saved_state = get_state(state) if state else None

    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    delete_state(state)

    if not code:
        error = request.query_params.get("error_description", "Authorization failed")
        raise HTTPException(status_code=400, detail=error)

    try:
        token_data = await OAuthService.exchange_code_for_token(code)
        access_token_yandex = token_data.get("access_token")
        user_info = await OAuthService.get_yandex_user_info(access_token_yandex)

        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        user, access_token, refresh_token = await OAuthService.login_or_create_user(
            db, user_info, user_agent, ip_address
        )

        redirect_response = Response(status_code=302, headers={"Location": "/api/docs"})

        redirect_response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=15 * 60,
            path="/"
        )
        redirect_response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )

        return redirect_response

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Сброс пароля (PUBLIC) ====================
@router.post(
    "/forgot-password",
    summary="Запрос на сброс пароля",
    description="Отправляет ссылку для сброса пароля на указанный email. Ссылка выводится в консоль (логи контейнера).",
    responses={
        200: {"description": "Запрос принят (существование email не раскрывается)"}
    }
)
def forgot_password(
    data: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    raw_token = AuthService.AuthService.create_password_reset_token(db, data.email)

    if raw_token:
        reset_link = f"http://localhost:8000/reset-password?token={raw_token}"
        print(f"Reset link: {reset_link}")
        return {"message": "If the email exists, a reset link has been sent"}
    else:
        return {"message": "If the email exists, a reset link has been sent"}


@router.post(
    "/reset-password",
    summary="Установка нового пароля",
    description="Устанавливает новый пароль для пользователя по токену из ссылки сброса пароля.",
    responses={
        200: {"description": "Пароль успешно изменён"},
        400: {"description": "Неверный или просроченный токен"}
    }
)
def reset_password(
    data: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    try:
        AuthService.AuthService.reset_password(db, data.token, data.new_password)
        return {"message": "Password has been reset successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))