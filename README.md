# AdsPilot Backend — FastAPI

Backend Python cho AdsPilot SaaS: TikTok Ads × Telegram × AI

## Kiến trúc

```
adspilot-backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # SQLAlchemy engine + session
│   ├── auth.py              # JWT, hash, OAuth verify
│   ├── crypto.py            # Mã hoá token nhạy cảm
│   ├── models/
│   │   ├── db.py            # SQLAlchemy models
│   │   └── schemas.py       # Pydantic schemas
│   ├── api/
│   │   ├── auth.py          # Signup, login, OAuth, Telegram
│   │   ├── setup.py         # Bot config, shops, API key
│   │   ├── reports.py       # Tạo báo cáo (TikTok + GPT)
│   │   └── admin.py         # Admin: cấp/revoke API key
│   └── services/
│       ├── tiktok.py        # Gọi TikTok Ads API
│       └── gpt.py           # GPT analysis + quota check
├── requirements.txt
├── .env.example
└── README.md
```

## Setup local (5 phút)

### 1. Cài Python 3.10+ và dependencies
```bash
cd adspilot-backend
pip install -r requirements.txt
```

### 2. Tạo file `.env` từ `.env.example`
```bash
cp .env.example .env
```

Sửa các biến quan trọng:
```bash
# Tạo encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy output, paste vào .env: ENCRYPTION_KEY=...

# OpenAI key (lấy từ platform.openai.com):
OPENAI_API_KEY=sk-proj-xxxxxxxxxx

# Admin account (tự đặt):
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=your-strong-password
```

### 3. Chạy server
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Mở docs
Vào http://localhost:8000/docs — Swagger UI tự động, có thể test mọi endpoint.

## Endpoints

### Auth (không cần login)
- `POST /auth/signup` — Tạo tài khoản email/password
- `POST /auth/login` — Login email/password → JWT
- `POST /auth/google` — Login bằng Google ID Token
- `POST /auth/telegram` — Login bằng Telegram Login Widget
- `GET /auth/me` — Thông tin user hiện tại

### Setup (cần JWT)
- `GET/POST/DELETE /bot` — Telegram bot config
- `GET/POST /shops`, `PUT/DELETE /shops/{id}` — TikTok shops CRUD
- `GET /apikey` — Xem API key + quota
- `POST /apikey/redeem` — Nhập key admin cấp

### Reports (cần JWT + API key)
- `POST /reports/generate` — Lấy báo cáo (kéo TikTok, GPT phân tích)
- `GET /reports/history` — Lịch sử báo cáo

### Admin (cần JWT admin)
- `GET /admin/users` — List tất cả user
- `POST /admin/apikey/create` — Cấp API key cho user
- `POST /admin/apikey/{key}/revoke` — Vô hiệu hoá key
- `POST /admin/apikey/{key}/quota` — Cập nhật quota
- `GET /admin/stats` — Thống kê hệ thống

## Frontend kết nối

Sửa biến `API_BASE_URL` trong frontend HTML:
```javascript
const API_BASE_URL = "http://localhost:8000";
// hoặc production: "https://api.adspilot.com"
```

Lưu JWT vào localStorage sau khi login:
```javascript
localStorage.setItem('adspilot_token', data.access_token);
```

Mọi request gửi kèm header:
```javascript
headers: { "Authorization": "Bearer " + token }
```

## Deploy production

### Option 1: Railway.app (dễ nhất, miễn phí)
1. Push code lên GitHub repo private
2. railway.app → New Project → Deploy from GitHub
3. Add Variables (lấy từ .env)
4. Railway tự detect FastAPI và deploy
5. Add PostgreSQL database (Railway có sẵn): đổi DATABASE_URL=postgresql://...

### Option 2: VPS (Hetzner, DigitalOcean)
```bash
# Trên server
git clone your-repo
cd adspilot-backend
pip install -r requirements.txt
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
# Dùng nginx reverse proxy + Let's Encrypt SSL
```

### Khuyến nghị production:
- ✅ Đổi DATABASE_URL sang **PostgreSQL** (SQLite chỉ cho dev)
- ✅ Đặt CORS_ORIGINS đúng domain frontend của bạn
- ✅ Đặt JWT_SECRET là chuỗi ngẫu nhiên dài (`openssl rand -hex 32`)
- ✅ Đặt ENCRYPTION_KEY ổn định (đừng đổi sau khi đã có data)
- ✅ Bật HTTPS

## Test API

Có thể test bằng:
1. **Swagger UI**: http://localhost:8000/docs (dễ nhất)
2. **curl**:
```bash
# Signup
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"123456","name":"User A"}'

# Login → lấy token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"123456"}' | jq -r .access_token)

# Tạo shop
curl -X POST http://localhost:8000/shops \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Brand A","advertiser_id":"7xxx","access_token":"yyy"}'
```

3. **Postman**: Import http://localhost:8000/openapi.json

## Quy trình admin cấp API key

1. User signup tài khoản mới → chưa có API key
2. User báo email cho admin
3. Admin gọi `POST /admin/apikey/create`:
   ```json
   { "user_email": "user@email.com", "quota_monthly": 500 }
   ```
4. Backend trả về key dạng `ap_xxxxxxxxxxxxxxxxxxxxxxxx`
5. Admin gửi key cho user
6. User vào web app → tab "API Key" → paste key → click Lưu
7. Frontend gọi `POST /apikey/redeem` để link key với account
8. User dùng được tính năng GPT phân tích

## Bảo mật

✅ JWT có expire 30 ngày  
✅ Password hash bằng bcrypt  
✅ TikTok access_token + Telegram bot_token mã hoá Fernet trước khi lưu DB  
✅ Admin endpoints check role server-side  
✅ Quota tracking để chống abuse OpenAI cost  
✅ Foreign key cascade delete (xoá user → xoá hết data)  

## Bước tiếp theo

Backend đã sẵn sàng. Tiếp theo có thể:
1. **Build Telegram bot** (multi-tenant) — đọc bot tokens từ DB, lắng nghe lệnh, gọi `/reports/generate`
2. **Kết nối frontend HTML** — thay localStorage mock bằng fetch tới các endpoint này
3. **Trang admin** — UI cho admin cấp/quản lý API key
