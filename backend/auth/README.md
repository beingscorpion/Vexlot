# Verdant API — Auth Module

FastAPI + SQLite backend for the Verdant investment accounting platform.

---

## Project Structure

```
verdant-api/
├── main.py                  # App factory, CORS, router registration
├── config.py                # Settings from .env via pydantic-settings
├── database.py              # SQLAlchemy engine + session + Base
├── models.py                # ORM table definitions (User, RefreshToken)
├── schemas.py               # Pydantic request/response schemas
├── security.py              # bcrypt hashing + JWT creation/decoding
├── dependencies.py          # FastAPI Depends() helpers (get_current_user)
├── services/
│   └── auth_service.py      # Business logic (register, login, refresh…)
├── routers/
│   └── auth.py              # HTTP route handlers
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
# 1. Clone / enter the project
cd verdant-api

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum, set JWT_SECRET_KEY to something random:
#   openssl rand -hex 32

# 5. Run the development server
uvicorn main:app --reload

# API docs available at:
#   http://127.0.0.1:8000/docs   (Swagger UI)
#   http://127.0.0.1:8000/redoc  (ReDoc)
```

---

## Auth Endpoints

| Method | Path | Auth required | Description |
|--------|------|:---:|-------------|
| POST | `/api/v1/auth/register` | ✗ | Create account |
| POST | `/api/v1/auth/login` | ✗ | Login → get tokens |
| POST | `/api/v1/auth/refresh` | ✗ | Rotate tokens |
| POST | `/api/v1/auth/logout` | ✔ | Revoke current device |
| POST | `/api/v1/auth/logout-all` | ✔ | Revoke all devices |
| GET  | `/api/v1/auth/me` | ✔ | Get own profile |
| PATCH | `/api/v1/auth/me` | ✔ | Update name |
| POST | `/api/v1/auth/change-password` | ✔ | Change password |
| GET  | `/api/v1/auth/sessions` | ✔ | List active sessions |
| DELETE | `/api/v1/auth/me` | ✔ | Delete account |

---

## Token Strategy

```
┌──────────┐  POST /login  ┌──────────────┐
│  Client  │ ────────────▶ │  API         │
│          │ ◀──────────── │              │
│          │  access_token │  (30 min)    │
│          │  refresh_token│  (7 days)    │
└──────────┘               └──────────────┘

Every protected request:
  Authorization: Bearer <access_token>

When access_token expires:
  POST /auth/refresh  { "refresh_token": "..." }
  → new access_token + new refresh_token (old one revoked)
```

- **Access tokens** are stateless JWTs — verified by signature only, no DB hit.
- **Refresh tokens** are opaque random strings — SHA-256 hash stored in SQLite.
- Token rotation is enforced: reusing an old refresh token revokes all sessions.

---

## Password Rules

- Minimum 8 characters
- At least one uppercase letter
- At least one digit

---

## What's next (future modules)

- `routers/investments.py` — CRUD for investment deals
- `routers/partners.py`    — partner management
- `routers/ledger.py`      — read-only audit trail
- Email verification flow
- Password reset via email token
