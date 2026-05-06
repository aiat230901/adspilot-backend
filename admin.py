"""Admin endpoints — chỉ admin user mới gọi được. Cấp API key với quota tuỳ ý."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User, ApiKey
from app.models.schemas import AdminCreateApiKey
from app.auth import require_admin, generate_api_key

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id, "email": u.email, "name": u.name,
            "provider": u.provider, "is_admin": u.is_admin,
            "shops_count": len(u.shops),
            "has_bot": bool(u.bot_config),
            "api_key": {
                "key": u.api_key.key,
                "quota": u.api_key.quota_monthly,
                "used": u.api_key.used_this_month,
                "active": u.api_key.is_active,
            } if u.api_key else None,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/apikey/create")
def create_apikey(
    payload: AdminCreateApiKey,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.user_email).first()
    if not user:
        raise HTTPException(404, "User không tồn tại")

    if user.api_key:
        user.api_key.quota_monthly = payload.quota_monthly
        user.api_key.is_active = True
        user.api_key.notes = payload.notes
        db.commit()
        return {"key": user.api_key.key, "updated": True}

    new_key = ApiKey(
        user_id=user.id,
        key=generate_api_key(),
        quota_monthly=payload.quota_monthly,
        notes=payload.notes,
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    logger.info(f"Admin {admin.email} cấp key cho {user.email}: quota={payload.quota_monthly}")
    return {"key": new_key.key, "created": True}


@router.post("/apikey/{key}/revoke")
def revoke_apikey(key: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    api_key = db.query(ApiKey).filter(ApiKey.key == key).first()
    if not api_key:
        raise HTTPException(404, "Key không tồn tại")
    api_key.is_active = False
    db.commit()
    return {"ok": True, "revoked": key}


@router.post("/apikey/{key}/quota")
def update_quota(
    key: str, payload: dict,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    api_key = db.query(ApiKey).filter(ApiKey.key == key).first()
    if not api_key:
        raise HTTPException(404, "Key không tồn tại")
    api_key.quota_monthly = int(payload.get("quota_monthly", 1000))
    db.commit()
    return {"ok": True, "new_quota": api_key.quota_monthly}


@router.get("/stats")
def admin_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.db import ReportLog
    from sqlalchemy import func

    total_users = db.query(func.count(User.id)).scalar()
    total_shops = db.query(func.count()).select_from(
        db.query(User).join(User.shops).subquery()
    ).scalar()
    total_reports = db.query(func.count(ReportLog.id)).scalar()
    total_tokens = db.query(func.sum(ReportLog.tokens_used)).scalar() or 0

    return {
        "total_users": total_users,
        "total_shops": total_shops,
        "total_reports": total_reports,
        "total_tokens_used": total_tokens,
    }
