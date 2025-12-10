"""
Repository layer for database operations with optimistic locking support.
Provides CRUD operations for Itinerary and ChatHistory models.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import time
import json
import os
from sqlmodel import Session, select
from sqlalchemy import func

from .models import Itinerary, ChatHistory, UserPreferences
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


class PreferencesNotFoundError(Exception):
    """Raised when user preferences are not found."""
    def __init__(self, traveler_id: str):
        self.traveler_id = traveler_id
        super().__init__(f"Preferences not found for traveler: {traveler_id}")


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
# User Preferences Repository
# =============================================================================

class UserPreferencesRepository:
    """
    Repository for UserPreferences CRUD operations with filesystem cache.
    
    Uses a write-through cache pattern:
    - Database is source of truth
    - Filesystem cache (data/user_preferences/{traveler_id}.json) for fast tool reads
    - Cache is updated on every write operation
    """
    
    # Cache directory relative to project root
    CACHE_DIR = Path(__file__).parent.parent / "data" / "user_preferences"
    
    def __init__(self, session: Session):
        self.session = session
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Ensure the cache directory exists."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _cache_path(self, traveler_id: str) -> Path:
        """Get the cache file path for a traveler."""
        return self.CACHE_DIR / f"{traveler_id}.json"
    
    def _write_cache(self, preferences: UserPreferences):
        """Write preferences to filesystem cache."""
        cache_path = self._cache_path(preferences.traveler_id)
        cache_data = {
            **preferences.to_full_dict(),
            "summary": preferences.generate_summary(),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2, default=str)
        logger.debug(f"Cache written: {cache_path}")
    
    def _delete_cache(self, traveler_id: str):
        """Delete cache file for a traveler."""
        cache_path = self._cache_path(traveler_id)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Cache deleted: {cache_path}")
    
    def _read_cache(self, traveler_id: str) -> Optional[Dict[str, Any]]:
        """Read preferences from filesystem cache (fast path for tools)."""
        cache_path = self._cache_path(traveler_id)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return None
    
    # =========================================================================
    # Create / Update (Upsert)
    # =========================================================================
    
    def upsert(
        self,
        traveler_id: str,
        flight_preferences: Optional[Dict[str, Any]] = None,
        hotel_preferences: Optional[Dict[str, Any]] = None,
        car_preferences: Optional[Dict[str, Any]] = None,
        budget_range: Optional[Dict[str, Any]] = None,
        dietary_restrictions: Optional[List[str]] = None,
        accessibility_needs: Optional[List[str]] = None,
        loyalty_programs: Optional[List[Dict[str, Any]]] = None,
        past_bookings_summary: Optional[Dict[str, Any]] = None,
    ) -> UserPreferences:
        """
        Create or update user preferences (upsert).
        
        Args:
            traveler_id: Traveler identifier
            flight_preferences: Flight preferences dict
            hotel_preferences: Hotel preferences dict
            car_preferences: Car preferences dict
            budget_range: Budget range dict {min, max, currency}
            dietary_restrictions: List of dietary restrictions
            accessibility_needs: List of accessibility needs
            loyalty_programs: List of loyalty program dicts
            past_bookings_summary: Aggregated booking stats
        
        Returns:
            Created/updated UserPreferences instance
        """
        start_time = time.perf_counter()
        
        # Check if exists
        existing = self.session.get(UserPreferences, traveler_id)
        
        if existing:
            # Update existing
            if flight_preferences is not None:
                existing.flight_preferences = flight_preferences
            if hotel_preferences is not None:
                existing.hotel_preferences = hotel_preferences
            if car_preferences is not None:
                existing.car_preferences = car_preferences
            if budget_range is not None:
                existing.budget_range = budget_range
            if dietary_restrictions is not None:
                existing.dietary_restrictions = dietary_restrictions
            if accessibility_needs is not None:
                existing.accessibility_needs = accessibility_needs
            if loyalty_programs is not None:
                existing.loyalty_programs = loyalty_programs
            if past_bookings_summary is not None:
                existing.past_bookings_summary = past_bookings_summary
            existing.updated_at = datetime.now(timezone.utc)
            
            preferences = existing
        else:
            # Create new
            preferences = UserPreferences(
                traveler_id=traveler_id,
                flight_preferences=flight_preferences,
                hotel_preferences=hotel_preferences,
                car_preferences=car_preferences,
                budget_range=budget_range,
                dietary_restrictions=dietary_restrictions,
                accessibility_needs=accessibility_needs,
                loyalty_programs=loyalty_programs,
                past_bookings_summary=past_bookings_summary,
            )
        
        self.session.add(preferences)
        self.session.commit()
        self.session.refresh(preferences)
        
        # Write-through to cache
        self._write_cache(preferences)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        action = "updated" if existing else "created"
        logger.info(f"⏱ DB preferences {action}: {_format_duration(duration_ms)} | traveler_id={traveler_id}")
        
        return preferences
    
    # =========================================================================
    # Read
    # =========================================================================
    
    def get_by_id(self, traveler_id: str) -> Optional[UserPreferences]:
        """Get preferences by traveler ID from database."""
        return self.session.get(UserPreferences, traveler_id)
    
    def get_by_id_or_raise(self, traveler_id: str) -> UserPreferences:
        """Get preferences by traveler ID or raise PreferencesNotFoundError."""
        preferences = self.get_by_id(traveler_id)
        if preferences is None:
            raise PreferencesNotFoundError(traveler_id)
        return preferences
    
    def get_summary(self, traveler_id: str) -> str:
        """
        Get preference summary for prompt inclusion.
        
        Fast path: reads from cache if available, otherwise from DB.
        
        Returns:
            Summary string (~50 tokens) or default message if not found
        """
        # Try cache first (fastest)
        cached = self._read_cache(traveler_id)
        if cached and "summary" in cached:
            return cached["summary"]
        
        # Fall back to database
        preferences = self.get_by_id(traveler_id)
        if preferences:
            return preferences.generate_summary()
        
        return "No preferences set for this traveler"
    
    def get_full_preferences(self, traveler_id: str) -> Dict[str, Any]:
        """
        Get full preferences for tool response.
        
        Fast path: reads from cache if available (for tool execution speed).
        
        Returns:
            Full preferences dict (~500 tokens)
        
        Raises:
            PreferencesNotFoundError: If preferences don't exist
        """
        # Try cache first (fastest - critical for tool latency)
        cached = self._read_cache(traveler_id)
        if cached:
            return cached
        
        # Fall back to database and rebuild cache
        preferences = self.get_by_id_or_raise(traveler_id)
        self._write_cache(preferences)  # Rebuild cache
        return preferences.to_full_dict()
    
    # =========================================================================
    # Delete
    # =========================================================================
    
    def delete(self, traveler_id: str) -> bool:
        """
        Delete user preferences.
        
        Returns:
            True if deleted
        
        Raises:
            PreferencesNotFoundError: If preferences don't exist
        """
        preferences = self.get_by_id_or_raise(traveler_id)
        
        self.session.delete(preferences)
        self.session.commit()
        
        # Remove from cache
        self._delete_cache(traveler_id)
        
        logger.info(f"Deleted preferences: traveler_id={traveler_id}")
        return True
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def rebuild_cache(self, traveler_id: str) -> bool:
        """Rebuild cache from database for a specific traveler."""
        preferences = self.get_by_id(traveler_id)
        if preferences:
            self._write_cache(preferences)
            return True
        return False
    
    def rebuild_all_caches(self) -> int:
        """Rebuild all preference caches from database."""
        query = select(UserPreferences)
        all_prefs = list(self.session.exec(query).all())
        
        for pref in all_prefs:
            self._write_cache(pref)
        
        logger.info(f"Rebuilt {len(all_prefs)} preference caches")
        return len(all_prefs)


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Alias for backward compatibility during migration
ItineraryRepository = TravelItineraryRepository
ChatHistoryRepository = ChatMessageRepository
