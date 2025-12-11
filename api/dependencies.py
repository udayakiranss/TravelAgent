"""
FastAPI dependencies for dependency injection.
Provides shared resources like database sessions, LLM provider, context, and orchestrator.
"""
import os
from typing import Generator, Optional
from functools import lru_cache
from uuid import uuid4

from fastapi import Request, Depends
from sqlmodel import Session

from database.connection import engine, create_db_and_tables
from agents.orchestration import Orchestrator
from agents.planning import TravelPlanner
from agents.core import create_llm_provider, LLMProvider
from api.context import TravelContext
from api.config import SelectionCriteria, DEFAULT_SELECTION_CRITERIA
from api.services import (
    ItineraryService,
    PreferenceService,
    SearchService,
    HealthService,
    ConversationService,
    PlanningService,
)


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
# Context Dependencies
# =============================================================================

def get_context(
    request: Request,
    db: Session = Depends(get_db),
    llm: Optional[LLMProvider] = Depends(get_llm),
) -> TravelContext:
    """
    Create a TravelContext for the current request.
    
    Request-scoped fields are initialized here.
    Conversation-scoped fields (itinerary, chat_history) are loaded by routes as needed.
    
    Note: Request ID is set by RequestIDMiddleware (main_web.py), not here.
    
    Args:
        request: FastAPI Request object
        db: Database session
        llm: LLM provider (may be None)
    
    Returns:
        Initialized TravelContext
    """
    # Get request ID from header (already set by middleware, but also stored in context)
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    
    return TravelContext(
        session=db,
        llm=llm,
        request_id=request_id,
        traveler_id="",  # Set by route from request body
        criteria=DEFAULT_SELECTION_CRITERIA,  # May be overridden by route
    )


# =============================================================================
# Orchestrator Dependencies
# =============================================================================

# Cached orchestrator instance (shared across requests for agent reuse)
_orchestrator_instance: Optional[Orchestrator] = None


def get_orchestrator(
    llm: Optional[LLMProvider] = Depends(get_llm),
) -> Orchestrator:
    """
    Get or create an Orchestrator instance.
    
    The Orchestrator is cached because agents are stateless.
    Database operations use the session from TravelContext.
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator(llm=llm, memory=None)
    
    return _orchestrator_instance


# =============================================================================
# Planner Dependencies
# =============================================================================

# Cached planner instance (shared across requests)
_planner_instance: Optional[TravelPlanner] = None


def get_planner(
    llm: Optional[LLMProvider] = Depends(get_llm),
) -> TravelPlanner:
    """
    Get or create a TravelPlanner instance.
    
    The Planner is cached because it's stateless.
    It handles NL parsing → ExecutionPlan creation.
    """
    global _planner_instance
    
    if _planner_instance is None:
        _planner_instance = TravelPlanner(llm=llm)
    
    return _planner_instance


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

def startup_event():
    """Run on application startup."""
    global _planner_instance

    global _orchestrator_instance
    
    # Create database tables
    create_db_and_tables()
    
    # Pre-warm LLM provider cache
    llm = get_llm_provider()
    
    # Pre-initialize orchestrator with agents (P2: avoid per-request init)
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator(llm=llm, memory=None)


def shutdown_event():
    """Run on application shutdown."""
    global _orchestrator_instance
    
    # Clear LLM provider cache
    get_llm_provider.cache_clear()
    
    # Clear orchestrator instance
    _orchestrator_instance = None


# =============================================================================
# Service Dependencies
# =============================================================================

def get_itinerary_service(
    db: Session = Depends(get_db),
) -> ItineraryService:
    """
    Get ItineraryService instance for the current request.
    
    Args:
        db: Database session
    
    Returns:
        ItineraryService instance
    """
    return ItineraryService(db)


def get_preference_service(
    db: Session = Depends(get_db),
) -> PreferenceService:
    """
    Get PreferenceService instance for the current request.
    
    Args:
        db: Database session
    
    Returns:
        PreferenceService instance
    """
    return PreferenceService(db)


def get_search_service() -> SearchService:
    """
    Get SearchService instance.
    
    SearchService is stateless, so a single instance can be reused.
    
    Returns:
        SearchService instance
    """
    return SearchService()


def get_health_service(
    db: Session = Depends(get_db),
    llm: Optional[LLMProvider] = Depends(get_llm),
) -> HealthService:
    """
    Get HealthService instance for the current request.
    
    Args:
        db: Database session
        llm: Optional LLM provider
    
    Returns:
        HealthService instance
    """
    return HealthService(db, llm)


def get_conversation_service(
    db: Session = Depends(get_db),
) -> ConversationService:
    """
    Get ConversationService instance for the current request.
    
    Args:
        db: Database session
    
    Returns:
        ConversationService instance
    """
    return ConversationService(db)


def get_planning_service(
    planner: TravelPlanner = Depends(get_planner),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> PlanningService:
    """
    Get PlanningService instance for the current request.
    
    Args:
        planner: TravelPlanner instance
        orchestrator: Orchestrator instance
    
    Returns:
        PlanningService instance
    """
    return PlanningService(planner, orchestrator)

