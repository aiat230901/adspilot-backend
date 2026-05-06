"""Encrypt/decrypt sensitive tokens (TikTok access_token, bot_token) trong DB"""

import os
import base64
from cryptography.fernet import Fernet

_KEY_ENV = os.getenv("ENCRYPTION_KEY")
if _KEY_ENV:
    _key = _KEY_ENV.encode()
else:
    _key = Fernet.generate_key()
    print(f"⚠️  ENCRYPTION_KEY chưa được set, dùng key tạm: {_key.decode()}")
    print("⚠️  Đặt biến môi trường ENCRYPTION_KEY=... cho production")

_fernet = Fernet(_key)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext  # backward compatible nếu chưa mã hoá
