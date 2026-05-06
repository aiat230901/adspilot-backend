"""Reports endpoint — gọi TikTok + GPT, có check quota"""

import time
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User
from app.models.schemas import ReportRequest, ReportResponse, ReportData
from app.auth import get_current_user
from app.services import tiktok, gpt as gpt_service

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    payload: ReportRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started = time.time()
    period = payload.period
    period_lbl = tiktok.period_label(period)

    shops = current.shops
    if payload.shop_ids:
        shops = [s for s in shops if s.id in payload.shop_ids]

    if not shops:
        raise HTTPException(400, "Bạn chưa thêm shop nào")

    try:
        gpt_service.check_and_consume_quota(db, current, increment=1)
    except gpt_service.QuotaExceeded as e:
        raise HTTPException(429, str(e))

    try:
        results, _, _ = await tiktok.fetch_user_shops(shops, period)
    except Exception as e:
        logger.error(f"TikTok fetch error: {e}")
        gpt_service.log_report(
            db, current, "report", period, 0,
            int((time.time()-started)*1000), False, str(e),
        )
        raise HTTPException(500, f"Lỗi lấy dữ liệu TikTok: {e}")

    analysis, tokens = await gpt_service.analyze_report(results, period_lbl)

    gpt_service.log_report(
        db, current, "report", period, tokens,
        int((time.time()-started)*1000), True,
    )

    shop_data = [ReportData(**r) for r in results]
    return ReportResponse(
        period=period,
        period_label=period_lbl,
        fetched_at=datetime.utcnow(),
        shops=shop_data,
        analysis=analysis,
        tokens_used=tokens,
    )


@router.get("/history")
def get_history(
    limit: int = 20,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.db import ReportLog
    logs = (db.query(ReportLog)
              .filter(ReportLog.user_id == current.id)
              .order_by(ReportLog.created_at.desc())
              .limit(limit).all())
    return [
        {
            "id": l.id,
            "command": l.command,
            "period": l.period,
            "tokens_used": l.tokens_used,
            "duration_ms": l.duration_ms,
            "success": l.success,
            "error_msg": l.error_msg,
            "created_at": l.created_at,
        }
        for l in logs
    ]
