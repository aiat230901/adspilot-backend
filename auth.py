"""Auth endpoints — signup, login, OAuth Google, Telegram login widget"""

import os
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User
from app.models.schemas import (
    UserCreate, UserLogin, OAuthLogin, TelegramLogin,
    UserOut, TokenResponse,
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, verify_telegram_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _has_setup(user: User) -> bool:
    return bool(user.bot_config and user.api_key and len(user.shops) > 0)


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name,
        avatar_url=user.avatar_url, is_admin=user.is_admin,
        has_setup=_has_setup(user),
    )


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(400, "Email đã được đăng ký")

    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        provider="email",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_user_to_out(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu sai")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_user_to_out(user))


@router.post("/google", response_model=TokenResponse)
async def google_login(payload: OAuthLogin, db: Session = Depends(get_db)):
    """Verify Google ID token, create/get user, return JWT"""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": payload.provider_token},
        )
        if r.status_code != 200:
            raise HTTPException(401, "Google token không hợp lệ")
        info = r.json()

    google_id = info.get("sub")
    email = info.get("email")
    name = info.get("name", email.split("@")[0])
    picture = info.get("picture")

    if not email:
        raise HTTPException(400, "Không lấy được email từ Google")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email, name=name, avatar_url=picture,
            provider="google", provider_id=google_id, password_hash=None,
        )
        db.add(user)
    else:
        user.provider = "google"
        user.provider_id = google_id
        if picture:
            user.avatar_url = picture

    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_user_to_out(user))


@router.post("/telegram", response_model=TokenResponse)
def telegram_login(payload: TelegramLogin, db: Session = Depends(get_db)):
    """Verify Telegram Login Widget signature, create/get user"""
    bot_token = os.getenv("TELEGRAM_LOGIN_BOT_TOKEN")
    if not bot_token:
        raise HTTPException(500, "Server chưa cấu hình Telegram Login")

    data = payload.model_dump(exclude_none=True)
    if not verify_telegram_login(data.copy(), bot_token):
        raise HTTPException(401, "Telegram signature không hợp lệ")

    tg_id = str(payload.id)
    email_synthetic = f"tg_{tg_id}@telegram.local"
    name = (payload.first_name + (" " + payload.last_name if payload.last_name else "")).strip()

    user = db.query(User).filter(
        User.provider == "telegram", User.provider_id == tg_id
    ).first()

    if not user:
        user = User(
            email=email_synthetic, name=name, avatar_url=payload.photo_url,
            provider="telegram", provider_id=tg_id, password_hash=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_user_to_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return _user_to_out(current)
