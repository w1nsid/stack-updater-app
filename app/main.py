from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.routes import router as api_router
from .db import Base, engine
from .logging_setup import setup_logging
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
