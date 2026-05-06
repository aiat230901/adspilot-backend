"""Database engine + session"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./adspilot.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Tạo tất cả bảng nếu chưa có"""
    Base.metadata.create_all(bind=engine)
