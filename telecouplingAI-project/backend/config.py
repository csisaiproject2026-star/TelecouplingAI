"""
CSIS Platform — application settings.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    # --- AI ---
    GOOGLE_API_KEY: str = ""
    DEFAULT_MODEL: str = "gemini-2.5-flash"

    # --- Storage (Docker container paths) ---
    SHARED_DIR: str = "/data/outputs"
    UPLOADS_DIR: str = "/data/uploads"
    FILE_SERVER_URL: str = "http://file-server/download/"

    # --- QGIS (Linux, inside Docker; override via .env for local Windows dev) ---
    QGIS_PYTHON_PATH: str = "/usr/bin/python3"
    QGIS_MAX_CONCURRENT: int = 3

    # --- InVEST model data ---
    MODEL_DATA_PATH: str = "/data/model_data"

    # --- R scripts ---
    R_SCRIPT_DIR: str = "./r_scripts"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Session ---
    SESSION_TTL_HOURS: int = 24
    MAX_SESSIONS: int = 50
    AUTH_REQUIRED: bool = False

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = Settings()
