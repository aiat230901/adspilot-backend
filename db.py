"""
Database models — SQLAlchemy
Mỗi user có:
- 1 ApiKey (do admin cấp, có quota)
- 1 BotConfig (Telegram bot riêng)
- N TikTokShop (nhiều shop)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    name          = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)              # null khi login bằng OAuth
    provider      = Column(String(50), default="email")             # email, google, telegram
    provider_id   = Column(String(255), nullable=True)              # Google sub / Telegram user_id
    avatar_url    = Column(String(500), nullable=True)
    is_admin      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_key      = relationship("ApiKey",     back_populates="user", uselist=False, cascade="all, delete-orphan")
    bot_config   = relationship("BotConfig",  back_populates="user", uselist=False, cascade="all, delete-orphan")
    shops        = relationship("TikTokShop", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    """Admin cấp API key cho từng user kèm quota. Backend dùng OpenAI key chung."""
    __tablename__ = "api_keys"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    key           = Column(String(64), unique=True, index=True, nullable=False)  # ap_xxx
    quota_monthly = Column(Integer, default=1000)
    used_this_month = Column(Integer, default=0)
    last_reset_at = Column(DateTime, default=datetime.utcnow)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    notes         = Column(Text, nullable=True)

    user = relationship("User", back_populates="api_key")


class BotConfig(Base):
    """Mỗi user có 1 bot Telegram riêng — token + chat_id"""
    __tablename__ = "bot_configs"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    bot_token     = Column(String(255), nullable=False)            # 110xxx:AAFxxx
    bot_username  = Column(String(255), nullable=True)             # @ShopABot
    chat_id       = Column(String(50), nullable=False)             # 123456789
    webhook_url   = Column(String(500), nullable=True)
    is_active     = Column(Boolean, default=True)
    last_used_at  = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bot_config")


class TikTokShop(Base):
    __tablename__ = "tiktok_shops"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name          = Column(String(255), nullable=False)
    advertiser_id = Column(String(64), nullable=False)
    access_token  = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    is_active     = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="shops")


class ReportLog(Base):
    """Lịch sử báo cáo - dùng cho phân tích & tránh trùng quota"""
    __tablename__ = "report_logs"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    command      = Column(String(100))         # /baocao, /sosanh, ...
    period       = Column(String(50))          # hom_nay, 7_ngay, ...
    tokens_used  = Column(Integer, default=0)
    duration_ms  = Column(Integer, default=0)
    success      = Column(Boolean, default=True)
    error_msg    = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
