"""
Database connection and session management for SQLite.
"""
from sqlmodel import SQLModel, create_engine, Session  
from contextlib import contextmanager
from pathlib import Path

# Import models to register them with SQLModel metadata
from .models import Itinerary, ChatHistory

# Database file location (in project root)
DATABASE_DIR = Path(__file__).parent.parent
DATABASE_FILE = DATABASE_DIR / "itineraries.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# SQLite connection args for thread safety
connect_args = {"check_same_thread": False}

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args=connect_args
)


def create_db_and_tables():
    """Create all database tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency injection for FastAPI routes.
    Yields a database session that auto-commits on success.
    """
    with Session(engine) as session:
        yield session


@contextmanager
def get_session_context():
    """
    Context manager for use outside of FastAPI (e.g., CLI, tests).
    
    Usage:
        with get_session_context() as session:
            session.add(itinerary)
            session.commit()
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def drop_all_tables():
    """Drop all tables (use only for testing)."""
    SQLModel.metadata.drop_all(engine)


def reset_database():
    """Drop and recreate all tables (use only for testing)."""
    drop_all_tables()
    create_db_and_tables()
