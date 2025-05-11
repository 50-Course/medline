import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str
    PROJECT_SUMMARY: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8"
    )


settings = Settings()  # type: ignore
