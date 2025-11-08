# Stack Updater Web Application

This repository contains a self‑contained Python web application and Docker
container that helps manage and trigger updates for Portainer stacks via
webhooks. The application presents a dashboard listing stacks by name and
description, alongside a simple form to add and edit stacks. Each stack has a
corresponding webhook URL which is invoked when the user clicks the update
button or when an automatic update interval elapses.

## Features

- **Dashboard:** View all configured stacks at a glance, including their
  description, last update time and a status indicator ("Up to date",
  "Needs update" or "Never updated").
- **Add/Edit Stacks:** Provide a friendly form to create new stack records or
  modify existing ones, capturing a name, description, webhook URL and
  optional automatic update interval.
- **Manual Updates:** Trigger a stack update by clicking the "Update" button.
- **Automatic Updates:** Enable auto‑updates on a per‑stack basis. The
  application runs a background thread that checks whether each stack is due
  for an update based on the configured interval.
- **Lightweight & Portable:** Built with FastAPI and SQLite for a small
  footprint. Deploy locally or as a Docker container with minimal overhead.

## Running Locally (uv + pyproject)

We use uv with `pyproject.toml` and a checked-in `uv.lock` for fast, reproducible installs.

1. Ensure Python 3.11+ is installed.
2. Install deps with uv:

   - Windows PowerShell:

     ```powershell
     ./scripts/install.ps1
     ```

   - macOS/Linux:

     ```bash
     ./scripts/install.sh
     ```

3. Run the app (bind to localhost only) with env file:

  ```bash
  uv run --env-file .env uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
  ```

4. Open `http://127.0.0.1:8080`.

The database file `database.db` will be created automatically in the `app/`
directory on first run.

## Using Docker (uv base image)

To build and run the application as a Docker container:

```bash
docker build -t stack-updater .
docker run -d -p 8080:8080 --name stack-updater stack-updater
```

Then visit `http://localhost:8080` in your browser. To persist the SQLite
database outside the container you can mount a volume:

```bash
docker run -d -p 8080:8080 \
  -v $(pwd)/data:/app/app \
  --name stack-updater stack-updater
```

Notes:
- The Dockerfile uses `ghcr.io/astral-sh/uv:python3.11-alpine` as base image.
- Dependencies are resolved from `pyproject.toml` with `uv.lock` and installed via `uv sync --frozen`.
- Container listens on 0.0.0.0:8080 internally; host binding is managed by `-p 8080:8080`.

## Portainer Stack Import

You can auto-import existing Portainer stacks (their webhook URLs) into the app.

Prerequisites (environment variables):

```bash
export PORTAINER_URL="https://portainer.example.com"
export PORTAINER_API_KEY="<your_api_key>"
```

Then click the "Import from Portainer" button on the dashboard. The app:
1. Calls `GET /api/stacks`
2. For each stack, fetches webhooks
3. Inserts any new webhook URLs not already stored

Only new entries are added; existing webhook URLs are skipped.

## Cloudflare Access (Protected Webhooks)

If your Portainer instance is behind Cloudflare Zero Trust (Access), provide the service token credentials so requests include the required headers:

In `.env`:
```bash
CF_ACCESS_CLIENT_ID=xxxxxxxxxxxxxxxxxxx
CF_ACCESS_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyy
```

When both are set the app automatically adds:
```
CF-Access-Client-ID: <id>
CF-Access-Client-Secret: <secret>
```
to Portainer API and webhook requests. Leave them blank if not needed.

## VS Code Tasks

The repo includes `.vscode/tasks.json` with convenience tasks:
- `Run app (uv)` – start server
- `Dev server (uv --reload)` – live reload
- `uv sync (.venv)` – sync dependencies

Use via Command Palette: “Tasks: Run Task”.

## Environment Variables Summary

| Variable | Purpose |
|----------|---------|
| `PORTAINER_URL` | Base URL for Portainer (required for import) |
| `PORTAINER_API_KEY` | API key with stack read/webhook permissions |
| `CF_ACCESS_CLIENT_ID` | Cloudflare Access service token client id (optional) |
| `CF_ACCESS_CLIENT_SECRET` | Cloudflare Access service token client secret (optional) |

## Security Notes

- Do not commit `.env` (already ignored); use `.env.template` for sharing keys placeholders.
- API keys should be injected via environment (e.g. systemd unit, Docker env vars).
- Webhook calls to local addresses never include Cloudflare headers.

## Configuration

- **Automatic updates:** When adding or editing a stack you can enable
  automatic updates by checking the corresponding box and specifying an
  interval in hours (e.g. 24 for daily updates). The background scheduler
  thread will call the webhook when this interval has elapsed since the last
  successful update.
- **Database path:** The SQLite database is stored at `app/database.db` by
  default. You can customise the location by editing the `DB_PATH` constant in
  `app/main.py`.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull
requests if you spot bugs or have improvements to suggest. When adding
features please ensure they remain lightweight to preserve the simple
deployment workflow.