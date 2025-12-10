"""
Database models for the Travel Booking Web API.
Uses SQLModel for combined SQLAlchemy ORM + Pydantic validation.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
import uuid


def generate_itinerary_id() -> str:
    """Generate a unique itinerary ID with prefix."""
    return f"itin-{uuid.uuid4().hex[:12]}"


def generate_chat_id() -> str:
    """Generate a unique chat message ID."""
    return f"chat-{uuid.uuid4().hex[:12]}"


def generate_preference_id() -> str:
    """Generate a unique preference ID."""
    return f"pref-{uuid.uuid4().hex[:12]}"


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


# =============================================================================
# User Preferences Table
# =============================================================================

class UserPreferences(SQLModel, table=True):
    """
    User preferences for personalized travel recommendations.
    
    Uses a two-tier loading pattern:
    - Summary: compact string for always-in-prompt (~50 tokens)
    - Full details: loaded via tool when model needs them (~500 tokens)
    
    Storage: Database as source of truth, filesystem cache for fast tool reads.
    """
    __tablename__ = "user_preferences"
    
    # Primary key - traveler ID (same as itinerary.traveler_id)
    traveler_id: str = Field(
        primary_key=True,
        description="Traveler identifier (matches itinerary.traveler_id)"
    )
    
    # === Core Preferences (included in summary) ===
    flight_preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Flight preferences: seat_type, cabin_class, preferred_airlines"
    )
    
    hotel_preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Hotel preferences: min_rating, room_type, amenities, preferred_chains"
    )
    
    car_preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Car preferences: car_type, features, preferred_companies"
    )
    
    budget_range: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Budget range: min, max, currency"
    )
    
    # === Detailed Preferences (loaded via tool) ===
    dietary_restrictions: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Dietary restrictions: vegetarian, vegan, gluten-free, allergies"
    )
    
    accessibility_needs: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Accessibility requirements: wheelchair, hearing, visual"
    )
    
    loyalty_programs: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Loyalty programs: [{program, number, tier}]"
    )
    
    past_bookings_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Aggregated stats from booking history"
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
    
    def generate_summary(self) -> str:
        """
        Generate a compact preference summary for prompt inclusion (~50 tokens).
        
        Returns:
            Human-readable summary string
        """
        parts = []
        
        # Flight preferences
        if self.flight_preferences:
            fp = self.flight_preferences
            flight_parts = []
            if fp.get("cabin_class"):
                flight_parts.append(fp["cabin_class"])
            if fp.get("seat_type"):
                flight_parts.append(f"{fp['seat_type']} seat")
            if flight_parts:
                parts.append(f"flights: {', '.join(flight_parts)}")
        
        # Hotel preferences
        if self.hotel_preferences:
            hp = self.hotel_preferences
            if hp.get("min_rating"):
                parts.append(f"hotels: {hp['min_rating']}+ star")
        
        # Car preferences
        if self.car_preferences:
            cp = self.car_preferences
            if cp.get("car_type"):
                parts.append(f"cars: {cp['car_type']}")
        
        # Budget
        if self.budget_range:
            br = self.budget_range
            currency = br.get("currency", "USD")
            if br.get("min") and br.get("max"):
                parts.append(f"budget: {currency} {br['min']}-{br['max']}")
            elif br.get("max"):
                parts.append(f"budget: up to {currency} {br['max']}")
        
        if not parts:
            return "No specific preferences set"
        
        return "Prefers: " + "; ".join(parts)
    
    def to_full_dict(self) -> Dict[str, Any]:
        """
        Convert to full dictionary for tool response (~500 tokens).
        
        Returns:
            Complete preferences dictionary
        """
        return {
            "traveler_id": self.traveler_id,
            "flight_preferences": self.flight_preferences,
            "hotel_preferences": self.hotel_preferences,
            "car_preferences": self.car_preferences,
            "budget_range": self.budget_range,
            "dietary_restrictions": self.dietary_restrictions,
            "accessibility_needs": self.accessibility_needs,
            "loyalty_programs": self.loyalty_programs,
            "past_bookings_summary": self.past_bookings_summary,
        }
