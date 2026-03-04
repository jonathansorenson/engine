"""Database configuration and session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.base import Base


# Create engine with support for both SQLite and PostgreSQL
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.env == "development"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and run lightweight migrations."""
    Base.metadata.create_all(bind=engine)

    # Auto-migrate: add V2 columns if missing (SQLAlchemy create_all won't alter existing tables)
    if "sqlite" in settings.database_url:
        from sqlalchemy import text, inspect
        insp = inspect(engine)
        if "deals" in insp.get_table_names():
            existing_cols = {c["name"] for c in insp.get_columns("deals")}
            with engine.begin() as conn:
                if "version" not in existing_cols:
                    conn.execute(text("ALTER TABLE deals ADD COLUMN version VARCHAR(10) DEFAULT '1'"))
                    print("Migrated: added 'version' column to deals")
                if "v2_state" not in existing_cols:
                    conn.execute(text("ALTER TABLE deals ADD COLUMN v2_state JSON"))
                    print("Migrated: added 'v2_state' column to deals")
