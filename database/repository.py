"""
Repository layer for database operations with optimistic locking support.
Provides CRUD operations for Itinerary and ChatHistory models.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import func

from .models import Itinerary, ChatHistory


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


class ItineraryRepository:
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
        flight_data: Optional[Dict[str, Any]] = None,
        hotel_data: Optional[Dict[str, Any]] = None,
        car_data: Optional[Dict[str, Any]] = None,
    ) -> Itinerary:
        """
        Create a new itinerary in draft status.
        
        Args:
            traveler_id: Identifier for the traveler
            original_query: Original NL query that created this
            flight_data: Flight booking details
            hotel_data: Hotel booking details
            car_data: Car rental details
        
        Returns:
            Created Itinerary instance
        """
        itinerary = Itinerary(
            traveler_id=traveler_id,
            original_query=original_query,
            status="draft",
            flight_data=flight_data,
            hotel_data=hotel_data,
            car_data=car_data,
        )
        
        # Calculate and set total cost
        itinerary.total_cost = itinerary.calculate_total_cost()
        
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
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
        
        return itineraries, total
    
    # =========================================================================
    # Update (with optimistic locking)
    # =========================================================================
    
    def update(
        self,
        itinerary_id: str,
        version: int,
        flight_data: Optional[Dict[str, Any]] = ...,  # Use ... as sentinel for "not provided"
        hotel_data: Optional[Dict[str, Any]] = ...,
        car_data: Optional[Dict[str, Any]] = ...,
    ) -> Itinerary:
        """
        Update an itinerary with optimistic locking.
        
        Args:
            itinerary_id: ID of itinerary to update
            version: Expected version (for optimistic locking)
            flight_data: New flight data (None to clear, ... to keep existing)
            hotel_data: New hotel data (None to clear, ... to keep existing)
            car_data: New car data (None to clear, ... to keep existing)
        
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
            raise InvalidStatusTransitionError(itinerary.status, "draft (update)")
        
        # Check version for optimistic locking
        if itinerary.version != version:
            raise VersionConflictError(version, itinerary.version)
        
        # Update fields (... means "not provided", None means "clear")
        if flight_data is not ...:
            itinerary.flight_data = flight_data
        if hotel_data is not ...:
            itinerary.hotel_data = hotel_data
        if car_data is not ...:
            itinerary.car_data = car_data
        
        # Recalculate total cost
        itinerary.total_cost = itinerary.calculate_total_cost()
        
        # Increment version and update timestamp
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
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
            raise InvalidStatusTransitionError(itinerary.status, "confirmed")
        
        itinerary.status = "confirmed"
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
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
            raise InvalidStatusTransitionError(itinerary.status, "cancelled")
        
        itinerary.status = "cancelled"
        itinerary.cancelled_at = datetime.now(timezone.utc)
        itinerary.version += 1
        itinerary.updated_at = datetime.now(timezone.utc)
        
        self.session.add(itinerary)
        self.session.commit()
        self.session.refresh(itinerary)
        
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
            raise InvalidStatusTransitionError(
                itinerary.status, 
                "deleted (only drafts can be deleted)"
            )
        
        self.session.delete(itinerary)
        self.session.commit()
        
        return True


class ChatHistoryRepository:
    """Repository for ChatHistory operations."""
    
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

