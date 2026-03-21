from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from skyhigh.config import get_settings

_settings = get_settings()

_is_sqlite = _settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {}
_pool_kw: dict = {}
if _is_sqlite:
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    _pool_kw = {"pool_size": 5, "max_overflow": 10}

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=not _is_sqlite,
    **_pool_kw,
    **_engine_kwargs,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
