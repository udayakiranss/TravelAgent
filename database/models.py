"""
Database models for the Travel Booking Web API.
Uses SQLModel for combined SQLAlchemy ORM + Pydantic validation.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
import uuid


def generate_itinerary_id() -> str:
    """Generate a unique itinerary ID with prefix."""
    return f"itin-{uuid.uuid4().hex[:12]}"


def generate_chat_id() -> str:
    """Generate a unique chat message ID."""
    return f"chat-{uuid.uuid4().hex[:12]}"


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


# =============================================================================
# Itinerary Table
# =============================================================================

class Itinerary(SQLModel, table=True):
    """
    Main itinerary table storing travel bookings.
    
    Uses UUID as primary key and partitioned JSON fields for each booking type
    to prevent overwrite conflicts during concurrent updates.
    """
    __tablename__ = "itinerary"
    
    # Primary key - UUID string
    id: str = Field(
        default_factory=generate_itinerary_id,
        primary_key=True,
        description="Unique itinerary identifier (e.g., itin-abc123)"
    )
    
    # Traveler identification
    traveler_id: str = Field(
        index=True,
        description="Identifier for the traveler"
    )
    
    # Original query that created this itinerary
    original_query: Optional[str] = Field(
        default=None,
        description="Original natural language query"
    )
    
    # Status workflow: draft -> confirmed -> cancelled
    status: str = Field(
        default="draft",
        index=True,
        description="Itinerary status: draft, confirmed, cancelled"
    )
    
    # Partitioned JSON fields for each reservation type
    flight_reservation: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Flight reservation details"
    )
    
    hotel_reservation: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Hotel reservation details"
    )
    
    car_reservation: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Car rental reservation details"
    )
    
    # Computed total cost (persisted for quick access)
    total_cost: float = Field(
        default=0.0,
        description="Total cost of all bookings"
    )
    
    # Optimistic locking version
    version: int = Field(
        default=1,
        description="Version number for optimistic locking"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Creation timestamp"
    )
    
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Last modification timestamp"
    )
    
    cancelled_at: Optional[datetime] = Field(
        default=None,
        description="Cancellation timestamp (if cancelled)"
    )
    
    # Relationship to chat history
    chat_messages: list["ChatHistory"] = Relationship(back_populates="itinerary")
    
    def calculate_total_cost(self) -> float:
        """Recalculate total cost from all reservation components."""
        total = 0.0
        
        if self.flight_reservation and isinstance(self.flight_reservation, dict):
            total += self.flight_reservation.get('total_price', self.flight_reservation.get('price', 0))
        
        if self.hotel_reservation and isinstance(self.hotel_reservation, dict):
            total += self.hotel_reservation.get('total_price', self.hotel_reservation.get('price', 0))
        
        if self.car_reservation and isinstance(self.car_reservation, dict):
            total += self.car_reservation.get('total_price', self.car_reservation.get('price', 0))
        
        return total


# =============================================================================
# Chat History Table
# =============================================================================

class ChatHistory(SQLModel, table=True):
    """
    Chat history for natural language modifications.
    
    Stores conversation context for each itinerary to support
    multi-turn modifications via LLM.
    """
    __tablename__ = "chat_history"
    
    # Primary key - UUID string
    id: str = Field(
        default_factory=generate_chat_id,
        primary_key=True,
        description="Unique message identifier"
    )
    
    # Foreign key to itinerary
    itinerary_id: str = Field(
        foreign_key="itinerary.id",
        index=True,
        description="Associated itinerary ID"
    )
    
    # Message role: "user" or "assistant"
    role: str = Field(
        description="Message role: user or assistant"
    )
    
    # Message content
    content: str = Field(
        description="Message content"
    )
    
    # Timestamp
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Message timestamp"
    )
    
    # Relationship back to itinerary
    itinerary: Optional[Itinerary] = Relationship(back_populates="chat_messages")
