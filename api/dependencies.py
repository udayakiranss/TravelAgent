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

# Mapping of provider to expected API key environment variable name
PROVIDER_API_KEY_NAMES = {
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together": "TOGETHER_API_KEY",
}

# Default models per provider
PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "google_genai": "gemini-2.0-flash",
    "anthropic": "claude-3-5-sonnet-latest",
    "groq": "llama-3.1-70b-versatile",
    "mistralai": "mistral-large-latest",
}


def get_llm_provider_name() -> str:
    """Get the configured LLM provider name."""
    return os.getenv('LLM_PROVIDER', 'openai')


def get_expected_api_key_name() -> str:
    """Get the expected API key environment variable name for current provider."""
    provider = get_llm_provider_name()
    return PROVIDER_API_KEY_NAMES.get(provider, f"{provider.upper()}_API_KEY")


def get_default_model() -> str:
    """Get the default model for the current provider."""
    provider = get_llm_provider_name()
    return PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o")


@lru_cache()
def get_llm_provider() -> Optional[LLMProvider]:
    """
    Get cached LLM provider instance.
    Lets LangChain handle API key detection automatically.
    Returns None if initialization fails (typically due to missing API key).
    """
    provider = get_llm_provider_name()
    model = os.getenv('LLM_MODEL', get_default_model())
    
    try:
        llm = create_llm_provider(
            model_name=model,
            model_provider=provider,
            temperature=float(os.getenv('LLM_TEMPERATURE', '0'))
        )
        return llm
    except Exception as e:
        # Log with provider-specific API key name for clarity
        api_key_name = get_expected_api_key_name()
        from utils.logger import get_logger
        logger = get_logger()
        logger.warning(f"LLM initialization failed for {provider}/{model}: {e}. "
                      f"Ensure {api_key_name} is set.")
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

