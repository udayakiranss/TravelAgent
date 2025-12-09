"""
Repository layer for database operations with optimistic locking support.
Provides CRUD operations for Itinerary and ChatHistory models.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import time
from sqlmodel import Session, select
from sqlalchemy import func

from .models import Itinerary, ChatHistory
from utils.logger import get_logger, _format_duration

# Initialize logger
logger = get_logger()


class VersionConflictError(Exception):
    """Raised when optimistic locking detects a version conflict."""
    def __init__(self, expected_version: int, current_version: int):
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Version conflict: expected {expected_version}, found {current_version}"
        )


class ItineraryNotFoundError(Exception):
    """Raised when an itinerary is not found."""
    def __init__(self, itinerary_id: str):
        self.itinerary_id = itinerary_id
        super().__init__(f"Itinerary not found: {itinerary_id}")


class InvalidStatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""
    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Invalid status transition from '{current_status}' to '{target_status}'"
        )


class LLMUnavailableError(Exception):
    """Raised when LLM service is required but not available."""
    def __init__(self, message: str = "LLM service is not available"):
        self.message = message
        super().__init__(message)


class TravelItineraryRepository:
    """Repository for Itinerary CRUD operations with optimistic locking."""
    
    def __init__(self, session: Session):
        self.session = session
    
    # =========================================================================
    # Create
    # =========================================================================
    
    def create(
        self,
        traveler_id: str,
        original_query: Optional[str] = None,
        flight_reservation: Optional[Dict[str, Any]] = None,
        hotel_reservation: Optional[Dict[str, Any]] = None,
        car_reservation: Optional[Dict[str, Any]] = None,
    ) -> Itinerary:
        """
        Create a new itinerary in draft status.
        
        Args:
            traveler_id: Identifier for the traveler
            original_query: Original NL query that created this
            flight_reservation: Flight reservation details
            hotel_reservation: Hotel reservation details
            car_reservation: Car rental reservation details
        
        Returns:
            Created Itinerary instance
        """
        start_time = time.perf_counter()
        
        itinerary = Itinerary(
            traveler_id=traveler_id,
            original_query=original_query,
            status="draft",
            flight_reservation=flight_reservation,
            hotel_reservation=hotel_reservation,
            car_reservation=car_reservation,
        )
        
        # Calculate and set total cost
        itinerary.total_cost = itinerary.calculate_total_cost()
        
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"⏱ DB create: {_format_duration(duration_ms)} | Created itinerary: id={itinerary.id}, traveler_id={traveler_id}")
        return itinerary
    
    # =========================================================================
    # Read
    # =========================================================================
    
    def get_by_id(self, itinerary_id: str) -> Optional[Itinerary]:
        """Get an itinerary by ID."""
        return self.session.get(Itinerary, itinerary_id)
    
    def get_by_id_or_raise(self, itinerary_id: str) -> Itinerary:
        """Get an itinerary by ID or raise ItineraryNotFoundError."""
        itinerary = self.get_by_id(itinerary_id)
        if itinerary is None:
            raise ItineraryNotFoundError(itinerary_id)
        return itinerary
    
    def list_all(
        self,
        status: Optional[str] = None,
        traveler_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[Itinerary], int]:
        """
        List itineraries with optional filtering and pagination.
        
        Args:
            status: Filter by status (draft, confirmed, cancelled)
            traveler_id: Filter by traveler ID
            page: Page number (1-indexed)
            limit: Items per page (max 100)
        
        Returns:
            Tuple of (list of itineraries, total count)
        """
        start_time = time.perf_counter()
        
        # Clamp limit
        limit = min(max(1, limit), 100)
        offset = (max(1, page) - 1) * limit
        
        # Build query
        query = select(Itinerary)
        count_query = select(func.count(Itinerary.id))
        
        if status:
            query = query.where(Itinerary.status == status)
            count_query = count_query.where(Itinerary.status == status)
        
        if traveler_id:
            query = query.where(Itinerary.traveler_id == traveler_id)
            count_query = count_query.where(Itinerary.traveler_id == traveler_id)
        
        # Order by created_at desc
        query = query.order_by(Itinerary.created_at.desc())
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute
        itineraries = list(self.session.exec(query).all())
        total = self.session.exec(count_query).one()
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"⏱ DB list: {_format_duration(duration_ms)} | {len(itineraries)} items, {total} total")
        
        return itineraries, total
    
    # =========================================================================
    # Update (with optimistic locking)
    # =========================================================================
    
    def update(
        self,
        itinerary_id: str,
        version: int,
        flight_reservation: Optional[Dict[str, Any]] = ...,  # Use ... as sentinel for "not provided"
        hotel_reservation: Optional[Dict[str, Any]] = ...,
        car_reservation: Optional[Dict[str, Any]] = ...,
    ) -> Itinerary:
        """
        Update an itinerary with optimistic locking.
        
        Args:
            itinerary_id: ID of itinerary to update
            version: Expected version (for optimistic locking)
            flight_reservation: New flight reservation (None to clear, ... to keep existing)
            hotel_reservation: New hotel reservation (None to clear, ... to keep existing)
            car_reservation: New car reservation (None to clear, ... to keep existing)
        
        Returns:
            Updated Itinerary instance
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            VersionConflictError: If version doesn't match
            InvalidStatusTransitionError: If itinerary is not in draft status
        """
        itinerary = self.get_by_id_or_raise(itinerary_id)
        
        # Check status - can only update drafts
        if itinerary.status != "draft":
            logger.warning(f"Update rejected: itinerary id={itinerary_id} is in status={itinerary.status}")
            raise InvalidStatusTransitionError(itinerary.status, "draft (update)")
        
        # Check version for optimistic locking
        if itinerary.version != version:
            logger.warning(f"Version conflict: itinerary id={itinerary_id}, expected={version}, current={itinerary.version}")
            raise VersionConflictError(version, itinerary.version)
        
        # Update fields (... means "not provided", None means "clear")
        if flight_reservation is not ...:
            itinerary.flight_reservation = flight_reservation
        if hotel_reservation is not ...:
            itinerary.hotel_reservation = hotel_reservation
        if car_reservation is not ...:
            itinerary.car_reservation = car_reservation
        
        # Recalculate total cost
        itinerary.total_cost = itinerary.calculate_total_cost()
        
        # Increment version and update timestamp
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        commit_start = time.perf_counter()
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
        duration_ms = (time.perf_counter() - commit_start) * 1000
        logger.info(f"⏱ DB update: {_format_duration(duration_ms)} | id={itinerary_id}, v{itinerary.version}, ${itinerary.total_cost}")
        return itinerary
    
    # =========================================================================
    # Status Transitions
    # =========================================================================
    
    def confirm(self, itinerary_id: str) -> Itinerary:
        """
        Confirm a draft itinerary (locks from further edits).
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If not in draft status
        """
        itinerary = self.get_by_id_or_raise(itinerary_id)
        
        if itinerary.status != "draft":
            logger.warning(f"Confirm rejected: itinerary id={itinerary_id} is in status={itinerary.status}")
            raise InvalidStatusTransitionError(itinerary.status, "confirmed")
        
        itinerary.status = "confirmed"
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        commit_start = time.perf_counter()
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
        duration_ms = (time.perf_counter() - commit_start) * 1000
        logger.info(f"⏱ DB confirm: {_format_duration(duration_ms)} | id={itinerary_id}")
        return itinerary
    
    def cancel(self, itinerary_id: str) -> Itinerary:
        """
        Cancel an itinerary (draft or confirmed).
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If already cancelled
        """
        itinerary = self.get_by_id_or_raise(itinerary_id)
        
        if itinerary.status == "cancelled":
            logger.warning(f"Cancel rejected: itinerary id={itinerary_id} is already cancelled")
            raise InvalidStatusTransitionError(itinerary.status, "cancelled")
        
        itinerary.status = "cancelled"
        itinerary.cancelled_at = datetime.now(timezone.utc)
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        commit_start = time.perf_counter()
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
        duration_ms = (time.perf_counter() - commit_start) * 1000
        logger.info(f"⏱ DB cancel: {_format_duration(duration_ms)} | id={itinerary_id}")
        return itinerary
    
    # =========================================================================
    # Delete
    # =========================================================================
    
    def delete(self, itinerary_id: str) -> bool:
        """
        Delete a draft itinerary permanently.
        
        Returns:
            True if deleted
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If not in draft status
        """
        itinerary = self.get_by_id_or_raise(itinerary_id)
        
        if itinerary.status != "draft":
            logger.warning(f"Delete rejected: itinerary id={itinerary_id} is in status={itinerary.status}")
            raise InvalidStatusTransitionError(
                itinerary.status, 
                "deleted (only drafts can be deleted)"
            )
        
        self.session.delete(itinerary)
        self.session.commit()
        
        logger.info(f"Deleted itinerary: id={itinerary_id}")
        return True


class ChatMessageRepository:
    """Repository for ChatHistory/ChatMessage operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def add_message(
        self,
        itinerary_id: str,
        role: str,
        content: str,
    ) -> ChatHistory:
        """
        Add a chat message to an itinerary's history.
        
        Args:
            itinerary_id: Associated itinerary ID
            role: Message role ("user" or "assistant")
            content: Message content
        
        Returns:
            Created ChatHistory instance
        """
        message = ChatHistory(
            itinerary_id=itinerary_id,
            role=role,
            content=content,
        )
        
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        
        return message
    
    def get_history(
        self,
        itinerary_id: str,
        limit: int = 10,
    ) -> List[ChatHistory]:
        """
        Get chat history for an itinerary (most recent first, limited).
        
        Args:
            itinerary_id: Itinerary ID
            limit: Max messages to return (default 10 for token management)
        
        Returns:
            List of ChatHistory messages (oldest first for context building)
        """
        query = (
            select(ChatHistory)
            .where(ChatHistory.itinerary_id == itinerary_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        
        messages = list(self.session.exec(query).all())
        
        # Reverse to get chronological order for LLM context
        return list(reversed(messages))
    
    def clear_history(self, itinerary_id: str) -> int:
        """
        Clear all chat history for an itinerary.
        
        Returns:
            Number of messages deleted
        """
        query = select(ChatHistory).where(ChatHistory.itinerary_id == itinerary_id)
        messages = list(self.session.exec(query).all())
        
        count = len(messages)
        for message in messages:
            self.session.delete(message)
        
        self.session.commit()
        
        return count


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Alias for backward compatibility during migration
ItineraryRepository = TravelItineraryRepository
ChatHistoryRepository = ChatMessageRepository
