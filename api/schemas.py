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


# =============================================================================
# Agent/LLM Response Models
# =============================================================================

class FlightOption(BaseModel):
    """Flight option from agent search."""
    flight_id: str
    airline: str
    flight_number: Optional[str] = None
    origin: str
    destination: str
    departure: Optional[str] = None
    arrival: Optional[str] = None
    price: float
    
    class Config:
        extra = "allow"  # Allow additional fields


class HotelOption(BaseModel):
    """Hotel option from agent search."""
    hotel_id: str
    name: str
    location: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    price_per_night: Optional[float] = None
    total_price: float
    
    class Config:
        extra = "allow"


class CarOption(BaseModel):
    """Car rental option from agent search."""
    car_id: str
    company: str
    car_type: Optional[str] = None
    model: Optional[str] = None
    price_per_day: Optional[float] = None
    total_price: float
    
    class Config:
        extra = "allow"


class PlanResponse(BaseModel):
    """Response from /agent/plan endpoint - creates draft itinerary with auto-selected options."""
    itinerary_id: str = Field(..., description="Created draft itinerary ID")
    flight_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available flight options")
    hotel_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available hotel options")
    car_options: List[Dict[str, Any]] = Field(default_factory=list, description="All available car options")
    flight_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected flight reservation based on criteria")
    hotel_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected hotel reservation based on criteria")
    car_reservation: Optional[Dict[str, Any]] = Field(default=None, description="Auto-selected car reservation based on criteria")
    selection_criteria_used: str = Field(..., description="The selection criteria that was applied")
    summary: Optional[str] = Field(default=None, description="Natural language summary (generated by ResponseFormatter if include_summary=True)")
    query: str = Field(..., description="Original query")


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

