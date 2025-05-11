from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .core.config import settings as app_settings

engine = create_engine(app_settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
