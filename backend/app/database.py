"""Database connection (SQLite by default; any SQLAlchemy URL works via DATABASE_URL)."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        is_sqlite = parsed.get_backend_name() == "sqlite"
        if is_sqlite and parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)  # create data/ folder
        self.engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})
        self._session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()
