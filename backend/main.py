# ── main.py ───────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from config import settings
from database import Base, engine
from routers import auth as auth_router
from routers import investments as inv_router
from routers import partners as partner_router
from routers import ledger as ledger_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Use ASCII-only output to avoid Windows console encoding failures.
    print(f"Database ready -> {settings.DATABASE_URL}")
    print("Tables: users, refresh_tokens, partners, investments, investment_partners, return_events")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "**Verdant** — Investment & Accounting Platform API\n\n"
        "### Quick start\n"
        "1. `POST /api/v1/auth/register` — create account\n"
        "2. `POST /api/v1/auth/login` — get tokens\n"
        "3. Set `Authorization: Bearer <access_token>` on every request\n\n"
        "### Modules\n"
        "| Prefix | Description |\n"
        "|---|---|\n"
        "| `/auth` | Registration, login, token refresh, sessions |\n"
        "| `/investments` | Investment CRUD, partner allocation, received updates |\n"
        "| `/partners` | Partner profiles, directory stats |\n"
        "| `/ledger` | Read-only audit trail, P&L dashboard |\n"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(auth_router.router,    prefix=PREFIX)
app.include_router(inv_router.router,     prefix=PREFIX)
app.include_router(partner_router.router, prefix=PREFIX)
app.include_router(ledger_router.router,  prefix=PREFIX)

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], include_in_schema=False)
def health():
    return {"status": "ok", "version": settings.APP_VERSION}

@app.exception_handler(404)
async def not_found(_req, _exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found."})

# ── Serve frontend (local build) ────────────────────────────────────────────
# The frontend is plain HTML + a shared `api.js`. Each page uses
# `<script src="api.js"></script>`, so we must expose `/api.js` and the
# top-level HTML files.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _frontend_file(filename: str) -> FileResponse:
    return FileResponse(_FRONTEND_DIR / filename)


@app.get("/", include_in_schema=False)
def serve_root():
    return RedirectResponse(url="/index.html")


@app.get("/index.html", include_in_schema=False)
def serve_index():
    return _frontend_file("index.html")


@app.get("/auth.html", include_in_schema=False)
def serve_auth():
    return _frontend_file("auth.html")


@app.get("/dashboard.html", include_in_schema=False)
def serve_dashboard():
    return _frontend_file("dashboard.html")


@app.get("/partners.html", include_in_schema=False)
def serve_partners():
    return _frontend_file("partners.html")


@app.get("/ledger.html", include_in_schema=False)
def serve_ledger():
    return _frontend_file("ledger.html")


@app.get("/api.js", include_in_schema=False)
def serve_api_js():
    return _frontend_file("api.js")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
