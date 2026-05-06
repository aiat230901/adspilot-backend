"""
AdsPilot Backend — FastAPI app
Run: uvicorn app.main:app --reload --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, SessionLocal
from app.models.db import User, ApiKey
from app.auth import hash_password, generate_api_key
from app.api import auth, setup, reports, admin

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("✅ Database đã sẵn sàng")

    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_password:
            existing = db.query(User).filter(User.email == admin_email).first()
            if not existing:
                admin_user = User(
                    email=admin_email,
                    name="Admin",
                    password_hash=hash_password(admin_password),
                    provider="email",
                    is_admin=True,
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)

                admin_key = ApiKey(
                    user_id=admin_user.id,
                    key=generate_api_key(),
                    quota_monthly=999999,
                    notes="Admin auto-generated",
                )
                db.add(admin_key)
                db.commit()
                logger.info(f"✅ Đã tạo admin: {admin_email}")
            elif not existing.is_admin:
                existing.is_admin = True
                db.commit()
                logger.info(f"✅ Đã nâng quyền admin cho: {admin_email}")
    finally:
        db.close()

    yield
    logger.info("👋 Shutdown")


app = FastAPI(
    title="AdsPilot API",
    description="Backend cho AdsPilot — TikTok Ads × Telegram × AI",
    version="1.0.0",
    lifespan=lifespan,
)


cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(setup.router, prefix="")
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "app": "AdsPilot API",
        "version": "1.0.0",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
