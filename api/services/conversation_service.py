"""
Conversation service for managing chat history and conversation state.
"""
from typing import TYPE_CHECKING

from database.repository import TravelItineraryRepository, ChatMessageRepository
from utils.logger import get_logger

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


class ConversationService:
    """Service for conversation and chat history operations."""
    
    def __init__(self, session):
        """
        Initialize conversation service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.itinerary_repo = TravelItineraryRepository(session)
        self.chat_repo = ChatMessageRepository(session)
    
    def load_conversation_state(self, itinerary_id: str, ctx: "TravelContext") -> None:
        """
        Load conversation state into TravelContext.
        
        Loads itinerary and chat history for modification operations.
        
        Args:
            itinerary_id: Itinerary ID to load
            ctx: TravelContext to populate
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
        """
        logger.debug(f"Loading conversation state for itinerary id={itinerary_id}")
        
        # Load itinerary
        ctx.itinerary = self.itinerary_repo.get_by_id_or_raise(itinerary_id)
        ctx.original_query = ctx.itinerary.original_query
        
        # Load chat history (last 10 messages for context)
        ctx.chat_history = self.chat_repo.get_history(itinerary_id, limit=10)
        
        logger.debug(f"Loaded conversation state: itinerary={itinerary_id}, messages={len(ctx.chat_history)}")
    
    def save_chat_message(self, itinerary_id: str, role: str, content: str) -> None:
        """
        Save a chat message to the conversation history.
        
        Args:
            itinerary_id: Associated itinerary ID
            role: Message role ("user" or "assistant")
            content: Message content
        """
        logger.debug(f"Saving chat message: itinerary={itinerary_id}, role={role}")
        self.chat_repo.add_message(itinerary_id, role, content)
