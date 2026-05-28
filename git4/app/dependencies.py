from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.utils import decode_token
from app.auth.service import AuthService

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Dependency для получения текущего авторизованного пользователя"""
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_token(access_token, "access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = int(payload.get("sub"))
    user = AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user