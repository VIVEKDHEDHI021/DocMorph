"""Database connection and session management for DocMorph.

Configures connection pooling, SQLite thread safety, and auto-initialization.
Supports SQLite for local dev/testing and PostgreSQL for production deployments.
"""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.user import User

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "connect_args": connect_args,
    "echo": False,
}

# Apply connection pooling for non-SQLite databases (PostgreSQL/Supabase)
if not is_sqlite:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initializes tables and seeds default dev user if not existing."""
    Base.metadata.create_all(bind=engine)

    # In development mode, ensure a default local test user exists
    if settings.DEV_AUTH_MODE:
        with SessionLocal() as db:
            dev_email = "student@docmorph.dev"
            existing = db.query(User).filter(User.email == dev_email).first()
            if not existing:
                dev_user = User(
                    id="dev-user-00000000-0000-0000-0000-000000000001",
                    email=dev_email,
                    hashed_password=get_password_hash("DocMorph2026!"),
                    full_name="DocMorph Student",
                    is_active=True,
                    is_superuser=False,
                )
                db.add(dev_user)
                db.commit()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
