"""Setup endpoints - bot config, shops CRUD, api key view/update"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.models.db import User, BotConfig, TikTokShop, ApiKey
from app.models.schemas import (
    BotConfigIn, BotConfigOut, ShopIn, ShopOut, ApiKeyOut,
)
from app.auth import get_current_user
from app.crypto import encrypt, decrypt

router = APIRouter(tags=["setup"])
logger = logging.getLogger(__name__)


# ─── BOT CONFIG ───────────────────────────────────────────
@router.get("/bot", response_model=BotConfigOut | None)
def get_bot(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bc = current.bot_config
    if not bc:
        return None
    return BotConfigOut(
        bot_token=decrypt(bc.bot_token),
        bot_username=bc.bot_username,
        chat_id=bc.chat_id,
        is_active=bc.is_active,
    )


@router.post("/bot", response_model=BotConfigOut)
async def set_bot(payload: BotConfigIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot_username = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.telegram.org/bot{payload.bot_token}/getMe")
            data = r.json()
            if data.get("ok"):
                bot_username = "@" + data["result"]["username"]
            else:
                raise HTTPException(400, f"Bot token không hợp lệ: {data.get('description')}")
    except httpx.RequestError as e:
        raise HTTPException(500, f"Không gọi được Telegram API: {e}")

    bc = current.bot_config
    if not bc:
        bc = BotConfig(user_id=current.id)
        db.add(bc)

    bc.bot_token    = encrypt(payload.bot_token)
    bc.chat_id      = payload.chat_id
    bc.bot_username = bot_username
    bc.is_active    = True
    db.commit()
    db.refresh(bc)

    # Auto-register webhook để bot worker nhận update
    try:
        from bot.webhook_manager import register_webhook
        await register_webhook(payload.bot_token)
    except ImportError:
        logger.warning("bot.webhook_manager not found, skip webhook register")
    except Exception as e:
        logger.error(f"Webhook register failed: {e}")

    return BotConfigOut(
        bot_token=payload.bot_token,
        bot_username=bot_username,
        chat_id=payload.chat_id,
        is_active=True,
    )


@router.delete("/bot", status_code=204)
def delete_bot(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bc = current.bot_config
    if bc:
        db.delete(bc)
        db.commit()


# ─── SHOPS ───────────────────────────────────────────────
@router.get("/shops", response_model=list[ShopOut])
def list_shops(current: User = Depends(get_current_user)):
    return current.shops


@router.post("/shops", response_model=ShopOut)
def create_shop(payload: ShopIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shop = TikTokShop(
        user_id=current.id,
        name=payload.name,
        advertiser_id=payload.advertiser_id,
        access_token=encrypt(payload.access_token),
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.put("/shops/{shop_id}", response_model=ShopOut)
def update_shop(shop_id: int, payload: ShopIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shop = db.query(TikTokShop).filter(
        TikTokShop.id == shop_id,
        TikTokShop.user_id == current.id,
    ).first()
    if not shop:
        raise HTTPException(404, "Shop không tồn tại")

    shop.name = payload.name
    shop.advertiser_id = payload.advertiser_id
    shop.access_token = encrypt(payload.access_token)
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/shops/{shop_id}", status_code=204)
def delete_shop(shop_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shop = db.query(TikTokShop).filter(
        TikTokShop.id == shop_id,
        TikTokShop.user_id == current.id,
    ).first()
    if not shop:
        raise HTTPException(404, "Shop không tồn tại")
    db.delete(shop)
    db.commit()


# ─── API KEY ─────────────────────────────────────────────
@router.get("/apikey", response_model=ApiKeyOut | None)
def get_apikey(current: User = Depends(get_current_user)):
    if not current.api_key:
        return None
    return current.api_key


@router.post("/apikey/redeem")
def redeem_apikey(payload: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """User nhập key admin cấp → link với account"""
    key = payload.get("key", "").strip()
    if not key:
        raise HTTPException(400, "Thiếu key")

    api_key = db.query(ApiKey).filter(ApiKey.key == key).first()
    if not api_key:
        raise HTTPException(404, "API key không tồn tại")
    if not api_key.is_active:
        raise HTTPException(400, "API key đã bị vô hiệu hoá")
    if api_key.user_id and api_key.user_id != current.id:
        raise HTTPException(400, "API key đã được sử dụng bởi user khác")

    api_key.user_id = current.id
    db.commit()
    return {"ok": True, "quota_monthly": api_key.quota_monthly}
