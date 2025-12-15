from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .api.routes import router as api_router
from .db import Base, engine
from .logging_setup import setup_logging

STATIC_DIR = Path("app/static")


def static_url(filename: str) -> str:
    """Generate a cache-busted static URL using file modification time."""
    filepath = STATIC_DIR / filename
    try:
        mtime = int(os.path.getmtime(filepath))
        return f"/static/{filename}?v={mtime}"
    except OSError:
        return f"/static/{filename}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Cache control for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        # Cache control for static JS/CSS files during development
        if request.url.path.startswith("/static/") and request.url.path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    setup_logging()
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown (cleanup can go here if needed)


app = FastAPI(
    title="Stack Updater App",
    lifespan=lifespan,
    docs_url=None if os.getenv("DISABLE_DOCS", "").lower() in ("1", "true") else "/docs",
    redoc_url=None if os.getenv("DISABLE_DOCS", "").lower() in ("1", "true") else "/redoc",
)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)

# Trusted hosts (configure via ALLOWED_HOSTS env var, comma-separated)
allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
if allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
# Register the static_url function as a global for all templates
templates.env.globals["static_url"] = static_url


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
