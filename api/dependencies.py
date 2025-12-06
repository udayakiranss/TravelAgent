"""
FastAPI dependencies for dependency injection.
Provides shared resources like database sessions, LLM provider, and orchestrator.
"""
import os
from typing import Generator, Optional
from functools import lru_cache

from sqlmodel import Session

from database.connection import engine, create_db_and_tables
from agents.orchestrator import Orchestrator
from agents.llm_provider import create_llm_provider, LLMProvider


# =============================================================================
# Database Dependencies
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Auto-closes the session when the request completes.
    """
    # Ensure tables exist
    create_db_and_tables()
    
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()


# =============================================================================
# LLM Provider Dependencies
# =============================================================================

@lru_cache()
def get_llm_provider() -> Optional[LLMProvider]:
    """
    Get cached LLM provider instance.
    Returns None if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return None
    
    try:
        return create_llm_provider(
            model_name=os.getenv('LLM_MODEL', 'gpt-4o'),
            model_provider=os.getenv('LLM_PROVIDER', 'openai'),
            temperature=0
        )
    except Exception:
        return None


def get_llm() -> Optional[LLMProvider]:
    """Dependency that provides an LLM provider (may be None)."""
    return get_llm_provider()


# =============================================================================
# Orchestrator Dependencies
# =============================================================================

def get_orchestrator(
    db: Session,
    llm: Optional[LLMProvider] = None
) -> Orchestrator:
    """
    Create an Orchestrator instance with database session and optional LLM.
    
    Note: Orchestrator is created per-request to ensure fresh db session.
    """
    return Orchestrator(llm=llm, memory=None)


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

def startup_event():
    """Run on application startup."""
    # Create database tables
    create_db_and_tables()
    
    # Pre-warm LLM provider cache
    get_llm_provider()


def shutdown_event():
    """Run on application shutdown."""
    # Clear LLM provider cache
    get_llm_provider.cache_clear()

