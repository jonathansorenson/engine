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
    from sqlalchemy import text, inspect
    try:
        insp = inspect(engine)

        # Heal partial `feedback` migration: if the table was created on a prior boot
        # but its secondary indexes didn't finish (CREATE INDEX IF NOT EXISTS is idempotent).
        if "feedback" in insp.get_table_names():
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feedback_fund_id ON feedback (fund_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feedback_deal_id ON feedback (deal_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feedback_submitted_at ON feedback (submitted_at)"))

        # Drop orphan indexes that were superseded by auto-generated ones (ix_<plural>_col)
        # from BaseModel's and explicit index=True columns. Idempotent; safe on fresh DBs.
        for orphan in ("ix_deal_fund_id", "ix_chat_deal_id", "ix_chat_fund_id"):
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"DROP INDEX IF EXISTS {orphan}"))
            except Exception as e:
                # Never block boot on cleanup
                print(f"[Startup] Orphan index cleanup for {orphan} skipped: {e}")

        if "deals" in insp.get_table_names():
            existing_cols = {c["name"] for c in insp.get_columns("deals")}
            with engine.begin() as conn:
                if "version" not in existing_cols:
                    conn.execute(text("ALTER TABLE deals ADD COLUMN version VARCHAR(10) DEFAULT '1'"))
                    print("Migrated: added 'version' column to deals")
                if "v2_state" not in existing_cols:
                    if "sqlite" in settings.database_url:
                        conn.execute(text("ALTER TABLE deals ADD COLUMN v2_state JSON"))
                    else:
                        conn.execute(text("ALTER TABLE deals ADD COLUMN v2_state JSONB"))
                    print("Migrated: added 'v2_state' column to deals")

        # Migrate users table: add subscription columns
        if "users" in insp.get_table_names():
            user_cols = {c["name"] for c in insp.get_columns("users")}
            with engine.begin() as conn:
                for col_name, col_def in [
                    ("company_name", "VARCHAR(255)"),
                    ("subscription_tier", "VARCHAR(50)"),
                    ("stripe_customer_id", "VARCHAR(255)"),
                    ("stripe_subscription_id", "VARCHAR(255)"),
                    ("subscription_status", "VARCHAR(50)"),
                    ("user_preferences", "JSONB" if "sqlite" not in settings.database_url else "JSON"),
                    ("first_deal_at", "TIMESTAMP" if "sqlite" not in settings.database_url else "DATETIME"),
                    ("feedback_email_sent_at", "TIMESTAMP" if "sqlite" not in settings.database_url else "DATETIME"),
                ]:
                    if col_name not in user_cols:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                        print(f"Migrated: added '{col_name}' column to users")

                # Set existing users (no stripe_customer_id) to admin tier
                conn.execute(text(
                    "UPDATE users SET subscription_tier = 'admin' "
                    "WHERE stripe_customer_id IS NULL AND subscription_tier IS NULL"
                ))
    except Exception as e:
        print(f"Migration check warning: {e}")
