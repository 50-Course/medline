import os
import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Medline"
    PROJECT_SUMMARY: str = "The Unified product aggregator for everything Healthcare - from the best expositions, to catalogues and what's new"
    DATABASE_URL: str = Field(default="sqlite:///medline_dev.db")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8"
    )


settings = Settings()  # type: ignore
