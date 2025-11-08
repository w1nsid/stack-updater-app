from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    portainer_url: str = os.getenv("PORTAINER_URL", "http://localhost:9000")
    portainer_api_key: str | None = os.getenv("PORTAINER_API_KEY")
    refresh_interval_seconds: int = int(os.getenv("REFRESH_INTERVAL", "30"))
    outdated_after_seconds: int = int(os.getenv("OUTDATED_AFTER_SECONDS", "86400"))
    verify_ssl: bool = os.getenv("VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    # Cloudflare Access (optional)
    cf_access_client_id: str | None = os.getenv("CF_ACCESS_CLIENT_ID")
    cf_access_client_secret: str | None = os.getenv("CF_ACCESS_CLIENT_SECRET")
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "app.log")
    log_max_bytes: int = int(os.getenv("LOG_MAX_BYTES", "1048576"))  # 1MB
    log_backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "3"))


settings = Settings()
