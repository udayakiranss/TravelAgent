"""
Unit tests for ConversationService.
"""
import pytest

from api.services.conversation_service import ConversationService
from database.repository import ItineraryNotFoundError
from database.models import ChatHistory
from datetime import datetime


class TestConversationService:
    """Tests for ConversationService."""
    
    def test_load_conversation_state_success(self, mock_session, sample_itinerary, sample_chat_messages, mock_context):
        """Test loading conversation state."""
        service = ConversationService(mock_session)
        
        service.load_conversation_state(sample_itinerary.id, mock_context)
        
        assert mock_context.itinerary is not None
        assert mock_context.itinerary.id == sample_itinerary.id
        assert mock_context.original_query == sample_itinerary.original_query
        assert len(mock_context.chat_history) == 2
        assert mock_context.chat_history[0].role == "user"
        assert mock_context.chat_history[1].role == "assistant"
    
    def test_load_conversation_state_not_found(self, mock_session, mock_context):
        """Test loading conversation state for non-existent itinerary."""
        service = ConversationService(mock_session)
        
        with pytest.raises(ItineraryNotFoundError):
            service.load_conversation_state("itin-nonexistent", mock_context)
    
    def test_load_conversation_state_no_history(self, mock_session, sample_itinerary, mock_context):
        """Test loading conversation state when no chat history exists."""
        service = ConversationService(mock_session)
        
        service.load_conversation_state(sample_itinerary.id, mock_context)
        
        assert mock_context.itinerary is not None
        assert mock_context.chat_history == []  # Empty history
    
    def test_save_chat_message_success(self, mock_session, sample_itinerary):
        """Test saving a chat message."""
        service = ConversationService(mock_session)
        
        service.save_chat_message(
            sample_itinerary.id,
            "user",
            "Test message"
        )
        
        # Verify message was saved
        messages = service.chat_repo.get_history(sample_itinerary.id, limit=10)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Test message"
    
    def test_save_chat_message_multiple(self, mock_session, sample_itinerary):
        """Test saving multiple chat messages."""
        service = ConversationService(mock_session)
        
        service.save_chat_message(sample_itinerary.id, "user", "Message 1")
        service.save_chat_message(sample_itinerary.id, "assistant", "Message 2")
        service.save_chat_message(sample_itinerary.id, "user", "Message 3")
        
        messages = service.chat_repo.get_history(sample_itinerary.id, limit=10)
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"
