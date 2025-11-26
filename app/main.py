from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.routes import router as api_router
from .db import Base, engine
from .logging_setup import setup_logging
from .realtime import manager
from .tasks.background import status_refresher

STATIC_DIR = Path("app/static")


def static_url(filename: str) -> str:
    """Generate a cache-busted static URL using file modification time."""
    filepath = STATIC_DIR / filename
    try:
        mtime = int(os.path.getmtime(filepath))
        return f"/static/{filename}?v={mtime}"
    except OSError:
        return f"/static/{filename}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    setup_logging()
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(status_refresher())
    yield
    # Shutdown (cleanup can go here if needed)


app = FastAPI(title="Stack Updater App", lifespan=lifespan)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
# Register the static_url function as a global for all templates
templates.env.globals["static_url"] = static_url


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive and allow client pings
            await ws.receive_text()
    except Exception:
        pass
    finally:
        await manager.disconnect(ws)
