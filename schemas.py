"""Pydantic schemas - request/response validation"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OAuthLogin(BaseModel):
    provider: str
    provider_token: str

class TelegramLogin(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class UserOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: Optional[str] = None
    is_admin: bool
    has_setup: bool = False

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class BotConfigIn(BaseModel):
    bot_token: str = Field(..., min_length=20)
    chat_id: str = Field(..., min_length=1)

class BotConfigOut(BaseModel):
    bot_token: str
    bot_username: Optional[str] = None
    chat_id: str
    is_active: bool

    class Config:
        from_attributes = True


class ShopIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    advertiser_id: str = Field(..., min_length=1)
    access_token: str = Field(..., min_length=10)

class ShopOut(BaseModel):
    id: int
    name: str
    advertiser_id: str
    is_active: bool
    last_synced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyIn(BaseModel):
    key: str

class ApiKeyOut(BaseModel):
    key: str
    quota_monthly: int
    used_this_month: int
    is_active: bool

    class Config:
        from_attributes = True


class AdminCreateApiKey(BaseModel):
    user_email: EmailStr
    quota_monthly: int = 1000
    notes: Optional[str] = None


class ReportRequest(BaseModel):
    period: str = "hom_nay"  # hom_nay | hom_qua | 7_ngay | 30_ngay
    shop_ids: Optional[list[int]] = None

class ReportData(BaseModel):
    shop_id: int
    shop_name: str
    spend: float
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    roas: float
    conversions: int

class ReportResponse(BaseModel):
    period: str
    period_label: str
    fetched_at: datetime
    shops: list[ReportData]
    analysis: Optional[str] = None
    tokens_used: int = 0
