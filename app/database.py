import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings


log = logging.getLogger("uvicorn.error")
FALLBACK_URL = "sqlite:////tmp/fitness.db"


def make_engine(url):
    if url.startswith("sqlite"):
        args = {"check_same_thread": False}
    else:
        args = {"connect_timeout": 3}
    return create_engine(url, pool_pre_ping=True, connect_args=args)


engine = make_engine(settings.database_url)
if not settings.database_url.startswith("sqlite"):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as error:
        log.warning("Database unavailable (%s), falling back to SQLite", error)
        engine = make_engine(FALLBACK_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()