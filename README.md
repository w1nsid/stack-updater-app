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

The database file `app.db` will be created automatically on first run.

## Running Tests

Install dev dependencies and run the test suite:

```bash
uv sync --all-extras
uv run pytest
```

Run with coverage report:

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Run linting:

```bash
uv run ruff check app/ tests/
```

## Using Docker Compose (Recommended)

The easiest way to run the application is with Docker Compose:

1. **Copy the example environment file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your settings:**

   ```bash
   # Required
   PORTAINER_URL=https://your-portainer.example.com
   PORTAINER_API_KEY=ptr_your_api_key_here
   
   # Optional - adjust as needed
   REFRESH_INTERVAL=30
   VERIFY_SSL=true
   ```

3. **Start the application:**

   ```bash
   docker-compose up -d
   ```

4. **Access the dashboard:**

   Open `http://localhost:8080` in your browser.

5. **View logs:**

   ```bash
   docker-compose logs -f stack-updater
   ```

6. **Stop the application:**

   ```bash
   docker-compose down
   ```

The application will:
- Build the Docker image from the Dockerfile
- Load environment variables from `.env`
- Persist the SQLite database in `./data/` directory
- Automatically restart if it crashes
- Include health checks to monitor status

## Using Docker (Manual)

To build and run the application as a Docker container manually:

```bash
docker build -t stack-updater .
docker run -d -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --name stack-updater \
  stack-updater
```

Then visit `http://localhost:8080` in your browser.

Notes:
- The Dockerfile uses `ghcr.io/astral-sh/uv:python3.11-alpine` as base image.
- Dependencies are resolved from `pyproject.toml` with `uv.lock` and installed via `uv sync --frozen`.
- Container listens on 0.0.0.0:8080 internally; host binding is managed by `-p 8080:8080`.
- Database is persisted in the `./data` volume mount.

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

Configuration is done via environment variables (see `.env` file):

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORTAINER_URL` | `http://localhost:9000` | Base URL for Portainer API |
| `PORTAINER_API_KEY` | - | API key with stack read/webhook permissions |
| `DATABASE_URL` | `sqlite:///./app.db` | SQLAlchemy database connection string |
| `REFRESH_INTERVAL` | `30` | Seconds between background staleness checks |
| `VERIFY_SSL` | `true` | Verify SSL certificates for Portainer API |
| `CF_ACCESS_CLIENT_ID` | - | Cloudflare Access service token client ID (optional) |
| `CF_ACCESS_CLIENT_SECRET` | - | Cloudflare Access service token secret (optional) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | `app.log` | Log file path |
| `LOG_MAX_BYTES` | `1048576` | Max log file size before rotation (1MB) |
| `LOG_BACKUP_COUNT` | `3` | Number of rotated log files to keep |



## Dashboard UI

The dashboard features a modern, responsive design:

- Automatic dark/light theme based on system preference, with manual toggle
- Lucide SVG icon set for buttons and status badges
- Animated processing badge (pulse + spinner)
- Stats cards showing Updated/Outdated/Errors/Total counts
- CSS variables for easy theming in `app/static/style.css`

### Status Badge Legend

| Status | Visual |
|--------|--------|
| Updated | Green badge with check icon |
| Outdated | Yellow badge with warning triangle |
| Error | Red badge with X icon |
| Processing | Blue badge with spinning loader |
| Unknown / Skipped | Gray badge with help icon |

## Realtime Updates (WebSocket)

The app pushes stack changes over a WebSocket at `/ws`.

Events:
- `{"type":"stack","payload":{...}}` – single stack changed
- `{"type":"staleness","payload":[...]}` – periodic staleness evaluation

## Sorting & Filtering

- Click table headers to sort (toggles asc/desc)
- Search box for case-insensitive name filtering
- Status dropdown filters by status class

## Accessibility

- Focus-visible outlines for interactive elements
- Buttons have `aria-label` attributes
- Live region announces updates
- Table rows focusable via `tabindex="0"`

## Contributing

Contributions are welcome! Feel free to open issues or submit pull
requests if you spot bugs or have improvements to suggest.