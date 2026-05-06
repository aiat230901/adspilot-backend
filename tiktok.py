"""TikTok Ads API service"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.crypto import decrypt
from app.models.db import TikTokShop

logger = logging.getLogger(__name__)
TIKTOK_API = "https://business-api.tiktok.com/open_api/v1.3"


def get_date_range(period: str) -> tuple[str, str]:
    today = datetime.now()
    fmt = lambda d: d.strftime("%Y-%m-%d")
    mapping = {
        "hom_nay":   (today, today),
        "hom_qua":   (today - timedelta(1), today - timedelta(1)),
        "7_ngay":    (today - timedelta(6), today),
        "30_ngay":   (today - timedelta(29), today),
        "tuan_nay":  (today - timedelta(today.weekday()), today),
        "thang_nay": (today.replace(day=1), today),
    }
    start, end = mapping.get(period, (today, today))
    return fmt(start), fmt(end)


def period_label(period: str) -> str:
    return {
        "hom_nay":   "Hôm nay",
        "hom_qua":   "Hôm qua",
        "7_ngay":    "7 ngày qua",
        "30_ngay":   "30 ngày qua",
        "tuan_nay":  "Tuần này",
        "thang_nay": "Tháng này",
    }.get(period, "Hôm nay")


async def fetch_shop_report(
    shop: TikTokShop,
    start_date: str,
    end_date: str,
) -> dict:
    """Gọi TikTok API kéo metrics cho 1 shop"""
    token = decrypt(shop.access_token)
    if not token:
        raise ValueError(f"Shop {shop.name}: không có access token")

    url = f"{TIKTOK_API}/report/integrated/get/"
    headers = {
        "Access-Token": token,
        "Content-Type": "application/json",
    }
    payload = {
        "advertiser_id": shop.advertiser_id,
        "report_type": "BASIC",
        "dimensions": ["advertiser_id"],
        "metrics": [
            "spend", "impressions", "clicks",
            "ctr", "cpc",
            "conversion", "roas",
        ],
        "start_date": start_date,
        "end_date": end_date,
        "page_size": 1,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, headers=headers, json=payload)
        data = res.json()

    if data.get("code") != 0:
        raise ValueError(f"TikTok [{data.get('code')}]: {data.get('message')}")

    rows = data.get("data", {}).get("list", [])
    if not rows:
        return _empty_metrics()

    m = rows[0].get("metrics", {})
    return {
        "spend":       float(m.get("spend", 0)),
        "impressions": int(m.get("impressions", 0)),
        "clicks":      int(m.get("clicks", 0)),
        "ctr":         float(m.get("ctr", 0)),
        "cpc":         float(m.get("cpc", 0)),
        "conversions": int(m.get("conversion", 0)),
        "roas":        float(m.get("roas", 0)),
    }


def _empty_metrics() -> dict:
    return {
        "spend": 0, "impressions": 0, "clicks": 0,
        "ctr": 0, "cpc": 0, "conversions": 0, "roas": 0,
    }


async def fetch_user_shops(
    shops: list[TikTokShop],
    period: str,
) -> tuple[list[dict], str, str]:
    """Lấy báo cáo cho tất cả shop của 1 user"""
    start, end = get_date_range(period)
    results = []

    for shop in shops:
        if not shop.is_active:
            continue
        try:
            metrics = await fetch_shop_report(shop, start, end)
            results.append({
                "shop_id":   shop.id,
                "shop_name": shop.name,
                **metrics,
            })
            logger.info(f"✅ {shop.name}: spend={metrics['spend']:,.0f}")
        except Exception as e:
            logger.error(f"❌ {shop.name}: {e}")
            results.append({
                "shop_id": shop.id,
                "shop_name": shop.name,
                "error": str(e),
                **_empty_metrics(),
            })

    return results, start, end
