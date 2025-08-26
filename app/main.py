"""
Stack Updater Web Application
---------------------------------

This FastAPI application provides a lightweight dashboard for managing Portainer
stack webhooks. Users can add stacks with a name, description and webhook URL,
trigger updates on demand, and optionally configure an automatic update
interval. A background thread periodically checks each configured stack and
fires the webhook when the interval has elapsed since the last update.

The UI is intentionally simple: a dashboard lists all stacks and their
attributes, including a status indicator that reflects whether the stack is
considered up‑to‑date. Forms are provided for adding and editing stacks, and
actions such as deleting and updating a stack are performed via POST requests
for safety.

Database storage relies on SQLite. Whenever the application starts it will
initialise the database schema if it does not already exist. Stack records
contain the following fields:

- ``id``: primary key, auto‑incrementing integer
- ``name``: display name for the stack
- ``description``: free‑form description
- ``webhook``: URL for the Portainer stack webhook
- ``last_update``: ISO formatted timestamp of the last successful update
- ``interval_minutes``: number of minutes between automatic updates (nullable)
- ``auto_enabled``: boolean flag indicating whether auto updates are enabled

The scheduler runs in a daemon thread, scanning the database every minute and
triggering updates when necessary. This avoids a hard dependency on third‑party
scheduling libraries which may not be available in minimal environments.

To run the application locally use the command:

```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

This will serve the dashboard at ``http://localhost:8080``.

"""

import datetime
import sqlite3
import threading
import time
from pathlib import Path

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# Determine the base directory for templates and static files relative to this file
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "database.db"


def init_db() -> None:
    """Initialise the SQLite database schema if it does not already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                webhook TEXT NOT NULL,
                last_update TEXT,
                interval_minutes INTEGER,
                auto_enabled INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def update_stack_now(stack_id: int) -> bool:
    """Trigger the webhook for a single stack and record the update time.

    Args:
        stack_id: Primary key of the stack to update.
    Returns:
        True if the HTTP request succeeded; False otherwise.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT webhook FROM stacks WHERE id=?", (stack_id,))
        row = cursor.fetchone()
        if not row:
            return False
        webhook_url = row[0]
        try:
            # Fire the webhook; exceptions are logged but do not crash the thread
            requests.post(webhook_url, timeout=10)
            now_iso = datetime.datetime.utcnow().isoformat()
            cursor.execute(
                "UPDATE stacks SET last_update=? WHERE id=?", (now_iso, stack_id)
            )
            conn.commit()
            return True
        except Exception as exc:
            print(f"[Scheduler] Failed to update stack {stack_id}: {exc}")
            return False


def scheduler_loop() -> None:
    """Background loop that checks each stack and triggers updates when due.

    This function runs indefinitely in a daemon thread. Every minute it
    retrieves all stacks from the database and evaluates whether each one
    requires an automatic update. A stack is due for an update if auto
    updates are enabled, an interval is defined, and either the stack has
    never been updated or the time since the last update exceeds the
    interval. After scanning all stacks the loop sleeps for 60 seconds.
    """
    while True:
        now = datetime.datetime.utcnow()
        # Fetch all stacks outside of the update loop to minimise the time
        # holding the database connection open
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, last_update, interval_minutes, auto_enabled FROM stacks"
            )
            rows = cursor.fetchall()

        for stack_id, last_update_str, interval_minutes, auto_enabled in rows:
            if not auto_enabled or not interval_minutes:
                continue
            # Convert stored ISO timestamp to datetime if present
            last_update = (
                datetime.datetime.fromisoformat(last_update_str)
                if last_update_str
                else None
            )
            # Determine if an update is required
            if last_update is None:
                # Never updated: trigger immediately
                update_stack_now(stack_id)
            else:
                elapsed_minutes = (now - last_update).total_seconds() / 60.0
                if elapsed_minutes >= interval_minutes:
                    update_stack_now(stack_id)
        # Sleep before next scan
        time.sleep(60)


# Initialize database schema
init_db()

# Launch scheduler thread as a daemon
_scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
_scheduler_thread.start()


app = FastAPI(title="Stack Updater")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files (CSS, JS, images)
app.mount(
    "/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static"
)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard showing all stacks and their status."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, webhook, last_update, interval_minutes, auto_enabled FROM stacks"
        )
        rows = cursor.fetchall()

    stacks = []
    now = datetime.datetime.utcnow()
    for (
        stack_id,
        name,
        description,
        webhook,
        last_update,
        interval_minutes,
        auto_enabled,
    ) in rows:
        # Derive status indicator for display
        if last_update is None:
            status = "Never updated"
        else:
            last_dt = datetime.datetime.fromisoformat(last_update)
            if interval_minutes:
                elapsed = (now - last_dt).total_seconds() / 60.0
                status = "Up to date" if elapsed < interval_minutes else "Needs update"
            else:
                status = "Updated"
        stacks.append(
            {
                "id": stack_id,
                "name": name,
                "description": description,
                "webhook": webhook,
                "last_update": last_update,
                "interval": interval_minutes,
                "auto_enabled": bool(auto_enabled),
                "status": status,
            }
        )

    return templates.TemplateResponse(
        "index.html", {"request": request, "stacks": stacks}
    )


@app.get("/add", response_class=HTMLResponse)
async def add_form(request: Request) -> HTMLResponse:
    """Display the form for adding a new stack."""
    return templates.TemplateResponse(
        "add_edit.html", {"request": request, "stack": None}
    )


@app.post("/add")
async def add_stack(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    webhook: str = Form(...),
    auto_enabled: str = Form(None),
    interval_hours: str = Form(""),
) -> RedirectResponse:
    """Handle submission of a new stack."""
    # Determine auto update flag from checkbox (value will be "on" if checked)
    auto_flag = 1 if auto_enabled == "on" else 0
    interval_minutes: int | None = None
    if interval_hours:
        try:
            interval = float(interval_hours)
            if interval > 0:
                interval_minutes = int(interval * 60)
        except ValueError:
            interval_minutes = None
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO stacks (name, description, webhook, last_update, interval_minutes, auto_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, description, webhook, None, interval_minutes, auto_flag),
        )
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/edit/{stack_id}", response_class=HTMLResponse)
async def edit_form(request: Request, stack_id: int) -> HTMLResponse:
    """Display the edit form for an existing stack."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, webhook, last_update, interval_minutes, auto_enabled FROM stacks WHERE id=?",
            (stack_id,),
        )
        row = cursor.fetchone()
    if not row:
        return RedirectResponse(url="/", status_code=303)
    (
        sid,
        name,
        description,
        webhook,
        last_update,
        interval_minutes,
        auto_enabled,
    ) = row
    # Convert minutes to hours for form display (float)
    interval_hours: float | None = None
    if interval_minutes:
        interval_hours = round(interval_minutes / 60.0, 3)
    stack = {
        "id": sid,
        "name": name,
        "description": description,
        "webhook": webhook,
        "last_update": last_update,
        "interval_hours": interval_hours,
        "auto_enabled": bool(auto_enabled),
    }
    return templates.TemplateResponse(
        "add_edit.html", {"request": request, "stack": stack}
    )


@app.post("/edit/{stack_id}")
async def edit_stack(
    request: Request,
    stack_id: int,
    name: str = Form(...),
    description: str = Form(""),
    webhook: str = Form(...),
    auto_enabled: str = Form(None),
    interval_hours: str = Form(""),
) -> RedirectResponse:
    """Process edits to an existing stack."""
    auto_flag = 1 if auto_enabled == "on" else 0
    interval_minutes: int | None = None
    if interval_hours:
        try:
            interval = float(interval_hours)
            if interval > 0:
                interval_minutes = int(interval * 60)
        except ValueError:
            interval_minutes = None
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE stacks
            SET name=?, description=?, webhook=?, interval_minutes=?, auto_enabled=?
            WHERE id=?
            """,
            (name, description, webhook, interval_minutes, auto_flag, stack_id),
        )
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/delete/{stack_id}")
async def delete_stack(stack_id: int) -> RedirectResponse:
    """Delete a stack permanently."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM stacks WHERE id=?", (stack_id,))
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/update/{stack_id}")
async def manual_update(stack_id: int) -> RedirectResponse:
    """Trigger a manual update of a stack via its webhook."""
    update_stack_now(stack_id)
    return RedirectResponse(url="/", status_code=303)