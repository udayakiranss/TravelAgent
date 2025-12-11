"""
Pydantic models for API request/response validation.
Provides type-safe data structures for the Travel Booking API.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from api.config import SelectionCriteria, DEFAULT_SELECTION_CRITERIA


# =============================================================================
# Error Response Models
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str = Field(..., description="Error code (e.g., ITINERARY_NOT_FOUND)")
    message: str = Field(..., description="Human-readable error description")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")


class VersionConflictResponse(ErrorResponse):
    """Response for optimistic locking conflicts."""
    current_version: int = Field(..., description="Current version in database")


# =============================================================================
# Search Request Models (New for MCP)
# =============================================================================

class FlightSearchRequest(BaseModel):
    """Request body for flight search."""
    origin: str = Field(..., description="Origin city/airport")
    destination: str = Field(..., description="Destination city/airport")
    date: str = Field(..., description="Date of travel (YYYY-MM-DD)")

class HotelSearchRequest(BaseModel):
    """Request body for hotel search."""
    city: str = Field(..., description="City to search hotels in")

class CarSearchRequest(BaseModel):
    """Request body for car rental search."""
    city: str = Field(..., description="City to search cars in")


# =============================================================================
# Itinerary Request Models
# =============================================================================

class ItineraryCreateRequest(BaseModel):
    """Request body for creating a new itinerary."""
    traveler_id: str = Field(..., min_length=1, description="Traveler identifier")
    original_query: Optional[str] = Field(default=None, description="Original NL query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "traveler_id": "user_123",
                "original_query": "Plan a weekend trip to Paris"
            }
        }


class ItineraryUpdateRequest(BaseModel):
    """Request body for updating an itinerary (with optimistic locking)."""
    version: int = Field(..., ge=1, description="Expected version for optimistic locking")
    flight_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Flight reservation to set (null to clear)")
    hotel_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Hotel reservation to set (null to clear)")
    car_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Car rental reservation to set (null to clear)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "version": 2,
                "flight_reservation": {
                    "airline": "British Airways",
                    "flight_number": "BA123",
                    "price": 380
                },
                "hotel_reservation": None  # This will clear the hotel
            }
        }


class NaturalLanguageQueryRequest(BaseModel):
    """Request body for natural language planning."""
    query: str = Field(..., min_length=5, description="Natural language travel query")
    traveler_id: str = Field(..., min_length=1, description="Traveler identifier")
    selection_criteria: Optional[SelectionCriteria] = Field(
        default=None,
        description="Criteria for auto-selecting options: first_available, cheapest, best_rated. Defaults to system config."
    )
    include_summary: bool = Field(
        default=True,
        description="Generate natural language summary using ResponseFormatter (requires LLM)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Plan a weekend trip to Paris from London next Friday",
                "traveler_id": "user_123",
                "selection_criteria": "cheapest",
                "include_summary": True
            }
        }


class NaturalLanguageModifyRequest(BaseModel):
    """Request body for natural language modification of existing itinerary."""
    instruction: str = Field(..., min_length=3, description="Modification instruction")
    traveler_id: str = Field(..., min_length=1, description="Traveler identifier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "instruction": "Change the flight to next Monday",
                "traveler_id": "user_123"
            }
        }


# =============================================================================
# Itinerary Response Models
# =============================================================================

class ItineraryResponse(BaseModel):
    """Response body for a single itinerary."""
    id: str = Field(..., description="Unique itinerary identifier")
    traveler_id: str = Field(..., description="Traveler identifier")
    original_query: Optional[str] = Field(default=None, description="Original NL query")
    status: str = Field(..., description="Status: draft, confirmed, cancelled")
    flight_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Flight reservation details")
    hotel_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Hotel reservation details")
    car_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Car rental reservation details")
    total_cost: float = Field(default=0, description="Total cost of all reservations")
    version: int = Field(..., description="Version for optimistic locking")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    cancelled_at: Optional[datetime] = Field(default=None, description="Cancellation timestamp")
    
    class Config:
        from_attributes = True  # Allow ORM model conversion


class ItineraryListResponse(BaseModel):
    """Response body for itinerary list with pagination."""
    items: List[ItineraryResponse] = Field(..., description="List of itineraries")
    total: int = Field(..., description="Total number of matching itineraries")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")


class ItineraryStatusResponse(BaseModel):
    """Response for status change operations."""
    id: str = Field(..., description="Itinerary ID")
    status: str = Field(..., description="New status")
    message: str = Field(..., description="Status change message")
    cancelled_at: Optional[datetime] = Field(default=None, description="Cancellation time if cancelled")


class ItineraryDeleteResponse(BaseModel):
    """Response for delete operation."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Deletion result message")


class ChatMessageResponse(BaseModel):
    """Response body for a chat message."""
    role: str = Field(..., description="Role: user or assistant")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Message timestamp")

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Response body for chat history."""
    itinerary_id: str = Field(..., description="Itinerary ID")
    messages: List[ChatMessageResponse] = Field(..., description="List of messages")


# =============================================================================
# Agent/LLM Response Models
# =============================================================================

class FlightOption(BaseModel):
    """Flight option from agent search."""
    id: str = Field(..., description="Flight ID")
    airline: str
    price: float
    # Field aliases to match data format: "from" -> origin, "to" -> destination
    origin: str = Field(..., alias="from", description="Origin airport code")
    destination: str = Field(..., alias="to", description="Destination airport code")
    date: Optional[str] = None
    departure: Optional[str] = None
    arrival: Optional[str] = None
    duration: Optional[str] = None
    flight_number: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional fields
        populate_by_name = True  # Allow both alias and field name


class HotelOption(BaseModel):
    """Hotel option from agent search."""
    id: str = Field(..., description="Hotel ID")
    name: str
    city: Optional[str] = None
    rating: Optional[float] = None
    price: float = Field(..., description="Price per night")
    category: Optional[str] = None
    amenities: Optional[List[str]] = None
    
    class Config:
        extra = "allow"


class CarOption(BaseModel):
    """Car rental option from agent search."""
    id: str = Field(..., description="Car ID")
    company: str
    type: Optional[str] = Field(None, description="Car type: Economy, Compact, SUV, etc.")
    model: Optional[str] = None
    city: Optional[str] = None
    price: float = Field(..., description="Price per day")
    features: Optional[List[str]] = None
    
    class Config:
        extra = "allow"


class PlanResponse(BaseModel):
    """Response from /agent/plan endpoint - creates draft itinerary or missing-info guidance."""
    itinerary_id: Optional[str] = Field(default=None, description="Created draft itinerary ID, null when clarification is needed")
    flight_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available flight options")
    hotel_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available hotel options")
    car_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available car options")
    flight_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected flight reservation based on criteria")
    hotel_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected hotel reservation based on criteria")
    car_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected car reservation based on criteria")
    selection_criteria_used: str = Field(..., description="The selection criteria that was applied")
    preference_summary: Optional[str] = Field(default=None, description="Traveler's preference summary used for personalization")
    summary: Optional[str] = Field(default=None, description="Natural language summary (generated by ResponseFormatter if include_summary=True)")
    query: str = Field(..., description="Original query")
    missing_info: Optional[List[Dict[str, Any]]] = Field(default=None, description="When status=needs_clarification, required fields and questions")
    plan_id: Optional[str] = Field(default=None, description="Planner-generated plan identifier")


class ModifyResponse(BaseModel):
    """Response from NL modification endpoint."""
    success: bool = Field(..., description="Whether modification succeeded")
    updated_itinerary: Optional[ItineraryResponse] = Field(default=None)
    message: str = Field(..., description="Modification result message")
    partial: bool = Field(default=False, description="True if operation timed out with partial results")


# =============================================================================
# Health Check Models
# =============================================================================

class HealthResponse(BaseModel):
    """Response from health check endpoint."""
    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    database: str = Field(..., description="Database status: connected, error")
    llm: str = Field(..., description="LLM status: available, unavailable, error")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# User Preferences Models
# =============================================================================

class FlightPreferences(BaseModel):
    """Flight preferences structure."""
    seat_type: Optional[str] = Field(default=None, description="Preferred seat: aisle, window, middle")
    cabin_class: Optional[str] = Field(default=None, description="Cabin class: economy, economy_plus, business, first")
    preferred_airlines: Optional[List[str]] = Field(default=None, description="List of preferred airlines")
    
    class Config:
        extra = "allow"


class HotelPreferences(BaseModel):
    """Hotel preferences structure."""
    min_rating: Optional[float] = Field(default=None, ge=1, le=5, description="Minimum star rating (1-5)")
    room_type: Optional[str] = Field(default=None, description="Room type: single, double, suite")
    amenities: Optional[List[str]] = Field(default=None, description="Required amenities: wifi, pool, gym, etc.")
    preferred_chains: Optional[List[str]] = Field(default=None, description="Preferred hotel chains")
    
    class Config:
        extra = "allow"


class CarPreferences(BaseModel):
    """Car rental preferences structure."""
    car_type: Optional[str] = Field(default=None, description="Car type: economy, compact, suv, luxury")
    features: Optional[List[str]] = Field(default=None, description="Required features: gps, child_seat, etc.")
    preferred_companies: Optional[List[str]] = Field(default=None, description="Preferred rental companies")
    
    class Config:
        extra = "allow"


class BudgetRange(BaseModel):
    """Budget range structure."""
    min: Optional[float] = Field(default=None, ge=0, description="Minimum budget")
    max: Optional[float] = Field(default=None, ge=0, description="Maximum budget")
    currency: str = Field(default="USD", description="Currency code")


class LoyaltyProgram(BaseModel):
    """Loyalty program membership."""
    program: str = Field(..., description="Program name (e.g., Delta SkyMiles)")
    number: Optional[str] = Field(default=None, description="Membership number")
    tier: Optional[str] = Field(default=None, description="Membership tier (e.g., Gold, Platinum)")


class UserPreferencesCreateRequest(BaseModel):
    """Request body for creating/updating user preferences."""
    flight_preferences: Optional[FlightPreferences] = Field(default=None, description="Flight preferences")
    hotel_preferences: Optional[HotelPreferences] = Field(default=None, description="Hotel preferences")
    car_preferences: Optional[CarPreferences] = Field(default=None, description="Car rental preferences")
    budget_range: Optional[BudgetRange] = Field(default=None, description="Budget constraints")
    dietary_restrictions: Optional[List[str]] = Field(default=None, description="Dietary restrictions")
    accessibility_needs: Optional[List[str]] = Field(default=None, description="Accessibility requirements")
    loyalty_programs: Optional[List[LoyaltyProgram]] = Field(default=None, description="Loyalty program memberships")
    past_bookings_summary: Optional[Dict[str, Any]] = Field(default=None, description="Aggregated booking history")
    
    class Config:
        json_schema_extra = {
            "example": {
                "flight_preferences": {
                    "seat_type": "aisle",
                    "cabin_class": "economy_plus",
                    "preferred_airlines": ["Delta", "United"]
                },
                "hotel_preferences": {
                    "min_rating": 4,
                    "amenities": ["wifi", "gym"]
                },
                "budget_range": {
                    "min": 1000,
                    "max": 3000,
                    "currency": "USD"
                },
                "dietary_restrictions": ["vegetarian"],
                "loyalty_programs": [
                    {"program": "Delta SkyMiles", "number": "123456789", "tier": "Gold"}
                ]
            }
        }


class UserPreferencesResponse(BaseModel):
    """Response body for user preferences."""
    traveler_id: str = Field(..., description="Traveler identifier")
    flight_preferences: Optional[Dict[str, Any]] = Field(default=None)
    hotel_preferences: Optional[Dict[str, Any]] = Field(default=None)
    car_preferences: Optional[Dict[str, Any]] = Field(default=None)
    budget_range: Optional[Dict[str, Any]] = Field(default=None)
    dietary_restrictions: Optional[List[str]] = Field(default=None)
    accessibility_needs: Optional[List[str]] = Field(default=None)
    loyalty_programs: Optional[List[Dict[str, Any]]] = Field(default=None)
    past_bookings_summary: Optional[Dict[str, Any]] = Field(default=None)
    summary: str = Field(..., description="Compact preference summary (~50 tokens)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    
    class Config:
        from_attributes = True


class UserPreferencesDeleteResponse(BaseModel):
    """Response for preference deletion."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Result message")
