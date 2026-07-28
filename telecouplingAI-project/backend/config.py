"""
CSIS Platform — application settings.

To change the server's public IP / hostname, set ONE variable in .env.docker:
    SERVER_BASE_URL=http://<your-ip-or-domain>
FILE_SERVER_URL is automatically derived from it.
"""
from pathlib import Path
from urllib.parse import quote_plus
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    # --- AI ---
    GOOGLE_API_KEY: str = ""
    DEFAULT_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_CONCURRENT: int = Field(default=8, ge=1)
    GEMINI_MAX_QUEUE: int = Field(default=500, ge=1)
    GEMINI_INPUT_TPM_LIMIT: int = Field(default=3_000_000, ge=0)
    GEMINI_TPM_UTILIZATION: float = Field(default=0.90, gt=0, le=1)
    GEMINI_ESTIMATED_INPUT_TOKENS: int = Field(default=45_000, ge=1)
    SSE_PING_SECONDS: int = Field(default=10, ge=1)
    RELEASE_VERSION: str = "capacity-200-v1"

    # --- Public server URL (set this when IP changes — everything else derives from it) ---
    # Example: SERVER_BASE_URL=http://34.42.83.50  or  http://yourdomain.com
    SERVER_BASE_URL: str = ""

    # --- Storage (Docker container paths) ---
    SHARED_DIR: str = "/data/outputs"
    UPLOADS_DIR: str = "/data/uploads"
    # Derived from SERVER_BASE_URL if set; falls back to docker-internal address
    FILE_SERVER_URL: str = "http://file-server/download/"

    @model_validator(mode="after")
    def derive_urls(self) -> "Settings":
        """Derive URLs from the small set of per-server settings."""
        if self.SERVER_BASE_URL:
            base = self.SERVER_BASE_URL.rstrip("/")
            self.FILE_SERVER_URL = f"{base}/download/"
        if (
            self.ERROR_REGISTRY_ENABLED
            and not self.ERROR_DATABASE_URL
            and self.POSTGRES_PASSWORD
        ):
            user = quote_plus(self.POSTGRES_USER)
            password = quote_plus(self.POSTGRES_PASSWORD)
            database = quote_plus(self.POSTGRES_DB)
            self.ERROR_DATABASE_URL = (
                f"postgresql://{user}:{password}@{self.ERROR_DB_HOST}:5432/{database}"
            )
        return self

    # --- QGIS (Linux, inside Docker; override via .env for local Windows dev) ---
    QGIS_PYTHON_PATH: str = "/opt/conda/envs/TeleCouplingAI/bin/python"
    # Directory containing the qgis Python bindings (added to PYTHONPATH for render workers)
    # /app is included so Celery prefork workers can still import the app's own modules
    QGIS_PYTHON_BINDINGS: str = "/app:/opt/conda/envs/TeleCouplingAI/share/qgis/python"
    QGIS_MAX_CONCURRENT: int = 3

    # --- InVEST model data ---
    MODEL_DATA_PATH: str = "/data/model_data"

    # --- R scripts ---
    R_SCRIPT_DIR: str = "./r_scripts"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Session ---
    SESSION_TTL_HOURS: int = 24
    SESSION_ACTIVE_LEASE_SECONDS: int = Field(default=3600, ge=60)
    MAX_SESSIONS: int = Field(default=500, ge=1)
    AUTH_REQUIRED: bool = False

    # --- Admin error registry ---
    ERROR_REGISTRY_ENABLED: bool = False
    ADMIN_ENABLED: bool = False
    ERROR_ENVIRONMENT: str = "local"
    ERROR_DATABASE_URL: str = ""
    ERROR_DB_HOST: str = "error-db"
    ERROR_DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    ERROR_DB_RETRY_SECONDS: int = Field(default=10, ge=1, le=300)
    ERROR_STREAM_KEY: str = "csis:error-events"
    ERROR_STREAM_GROUP: str = "error-registry"
    ERROR_STREAM_MAXLEN: int = Field(default=100_000, ge=1000)
    ERROR_STREAM_CLAIM_IDLE_MS: int = Field(default=60_000, ge=1000)
    ERROR_RETENTION_DAYS: int = Field(default=90, ge=1, le=3650)
    ERROR_EVIDENCE_DIR: str = "/data/error-evidence"
    ERROR_EVIDENCE_MAX_BYTES: int = Field(
        default=2 * 1024 * 1024 * 1024,
        ge=1024,
    )
    ERROR_MAX_FILE_METADATA: int = Field(default=200, ge=1, le=5000)
    ERROR_MAX_TRACEBACK_CHARS: int = Field(default=100_000, ge=1000)
    POSTGRES_DB: str = "csis_errors"
    POSTGRES_USER: str = "csis_error"
    POSTGRES_PASSWORD: str = ""
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD_HASH: str = ""
    ADMIN_COOKIE_NAME: str = "csis_admin_session"
    ADMIN_COOKIE_SECURE: bool = True
    ADMIN_SESSION_HOURS: int = Field(default=8, ge=1, le=168)
    ADMIN_LOGIN_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    ADMIN_LOGIN_WINDOW_SECONDS: int = Field(default=900, ge=60, le=86400)

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = Settings()
