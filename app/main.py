from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.routes import router as api_router
from .db import Base, engine
from .logging_setup import setup_logging
from .realtime import manager
from .tasks.background import status_refresher

app = FastAPI(title="Stack Updater App")
app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
async def _startup():
    setup_logging()
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(status_refresher())


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
