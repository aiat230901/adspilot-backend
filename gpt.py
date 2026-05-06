"""GPT service - phân tích báo cáo, dùng OpenAI key của backend, quota theo ApiKey của user"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models.db import ApiKey, User, ReportLog

logger = logging.getLogger(__name__)
OPENAI_API = "https://api.openai.com/v1/chat/completions"


class QuotaExceeded(Exception):
    pass


def check_and_consume_quota(db: Session, user: User, increment: int = 1) -> ApiKey:
    """Kiểm tra quota của user, tăng counter, raise nếu vượt"""
    api_key = db.query(ApiKey).filter(ApiKey.user_id == user.id).first()
    if not api_key:
        raise QuotaExceeded("Bạn chưa có API key. Liên hệ admin để được cấp.")
    if not api_key.is_active:
        raise QuotaExceeded("API key đã bị vô hiệu hoá.")

    now = datetime.utcnow()
    if (now - api_key.last_reset_at).days >= 30:
        api_key.used_this_month = 0
        api_key.last_reset_at = now

    if api_key.used_this_month + increment > api_key.quota_monthly:
        raise QuotaExceeded(
            f"Hết quota tháng này ({api_key.used_this_month}/{api_key.quota_monthly}). Liên hệ admin."
        )

    api_key.used_this_month += increment
    db.commit()
    return api_key


async def analyze_report(results: list[dict], period_label: str) -> tuple[str, int]:
    """Gửi data sang GPT, trả về (analysis_text, tokens_used)"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ("_(Chưa cài OpenAI key trong backend)_", 0)

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    summary = [
        {
            "tài_khoản": r["shop_name"],
            "chi_tiêu_VND": round(r["spend"]),
            "impressions": r["impressions"],
            "CTR_%": round(r["ctr"], 2),
            "CPC_VND": round(r["cpc"]),
            "ROAS": round(r["roas"], 2),
            "conversions": r["conversions"],
        }
        for r in results
    ]

    prompt = f"""Bạn là chuyên gia TikTok Ads. Phân tích NGẮN GỌN dữ liệu {period_label} bằng tiếng Việt (tối đa 200 từ):

{json.dumps(summary, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Tổng quan (1-2 câu)
2. Shop tốt nhất / tệ nhất + lý do
3. Vấn đề cần khắc phục (ROAS thấp, CTR thấp...)
4. 1 hành động ưu tiên ngay

Dùng emoji, không dùng markdown heading."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(OPENAI_API, headers=headers, json=payload)
            data = res.json()
            res.raise_for_status()
        text = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return (text, tokens)
    except Exception as e:
        logger.error(f"GPT error: {e}")
        return (f"_(Lỗi GPT: {e})_", 0)


def log_report(db: Session, user: User, command: str, period: str,
               tokens: int, duration_ms: int, success: bool, error_msg: str = None):
    log = ReportLog(
        user_id=user.id,
        command=command,
        period=period,
        tokens_used=tokens,
        duration_ms=duration_ms,
        success=success,
        error_msg=error_msg,
    )
    db.add(log)
    db.commit()
