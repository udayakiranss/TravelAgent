"""
TravelContext - Shared context for request and conversation state.

This context object flows through Routes → Orchestrator → Agents.
Repositories only receive ctx.session (context-unaware).
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Session

from api.config import SelectionCriteria, DEFAULT_SELECTION_CRITERIA

if TYPE_CHECKING:
    from database.models import Itinerary, ChatHistory
    from agents.llm_provider import LLMProvider
    from llm import ModelInvocationStrategy


@dataclass
class TravelContext:
    """
    Mutable context shared across Orchestrator and Agents.
    
    Contains both request-scoped data (always present) and 
    conversation-scoped data (loaded when working with existing itinerary).
    """
    
    # === Request-scoped (always present) ===
    session: Session
    """Database session for this request."""
    
    model_strategy: Optional["ModelInvocationStrategy"] = None
    """Model Invocation Strategy for retrieving configured LLMs."""
    
    request_id: str = field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this request (for logging correlation)."""
    
    traveler_id: str = ""
    """Identifier of the traveler making this request."""
    
    criteria: SelectionCriteria = field(default_factory=lambda: DEFAULT_SELECTION_CRITERIA)
    """Selection criteria for choosing best options (cheapest, best_rated, first_available)."""
    
    # === Conversation-scoped (loaded when itinerary_id provided) ===
    itinerary_id: Optional[str] = None
    """ID of the itinerary being worked on (if any)."""
    
    itinerary: Optional["Itinerary"] = None
    """Current itinerary state (loaded from DB when itinerary_id provided)."""
    
    original_query: Optional[str] = None
    """Original NL query that started this conversation."""
    
    chat_history: List["ChatHistory"] = field(default_factory=list)
    """Recent chat messages for conversation context."""
    
    preference_summary: Optional[str] = None
    """Compact preference summary (~50 tokens) loaded during plan_trip."""
    
    full_preferences: Optional[Dict[str, Any]] = None
    """Full preferences loaded via tool call (only in tool_binding mode)."""
    
    # === Computed Properties ===
    @property
    def has_active_conversation(self) -> bool:
        """Check if we're working on an existing itinerary."""
        return self.itinerary_id is not None
    
    @property
    def is_modification_flow(self) -> bool:
        """Check if this is a modification of an existing itinerary."""
        return self.has_active_conversation and self.itinerary is not None
    
    @property
    def has_llm(self) -> bool:
        """Check if LLM is available for NL processing via model_strategy."""
        if self.model_strategy:
            try:
                from llm.strategy.use_cases import UseCase
                llm = self.model_strategy.get_llm_for_use_case(UseCase.PLANNER)
                return llm is not None
            except Exception:
                return False
        return False
    
    def get_chat_history_text(self, limit: int = 10) -> str:
        """Get formatted chat history for LLM prompts."""
        messages = self.chat_history[:limit] if limit else self.chat_history
        return "\n".join([f"{m.role}: {m.content}" for m in messages])
    
    def __repr__(self) -> str:
        return (
            f"TravelContext(request_id={self.request_id[:8]}..., "
            f"traveler_id={self.traveler_id}, "
            f"criteria={self.criteria.value}, "
            f"itinerary_id={self.itinerary_id})"
        )
