"""
Typed domain models for travel booking options.

These models provide type safety and validation for flight, hotel, and car options
returned by agents. Use `origin`/`destination` instead of `from`/`to` to avoid
Python reserved word conflicts.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FlightOption(BaseModel):
    """Flight option from search results."""
    
    id: str = Field(..., description="Unique flight identifier")
    origin: str = Field(..., description="Departure airport code (was 'from')")
    destination: str = Field(..., description="Arrival airport code (was 'to')")
    date: str = Field(..., description="Flight date (YYYY-MM-DD)")
    price: float = Field(..., ge=0, description="Flight price")
    airline: str = Field(..., description="Airline name")
    departure: Optional[str] = Field(default=None, description="Departure time (HH:MM)")
    arrival: Optional[str] = Field(default=None, description="Arrival time (HH:MM)")
    duration: Optional[str] = Field(default=None, description="Flight duration")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Rating for selection")
    
    class Config:
        extra = "allow"  # Allow additional fields from mock data
    
    @classmethod
    def from_legacy(cls, data: dict) -> "FlightOption":
        """Convert legacy format (using 'from'/'to') to new format."""
        converted = data.copy()
        if "from" in converted:
            converted["origin"] = converted.pop("from")
        if "to" in converted:
            converted["destination"] = converted.pop("to")
        return cls(**converted)
    
    def to_reservation_dict(self) -> dict:
        """Convert to dictionary format for storing as reservation."""
        return {
            "flight_id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "date": self.date,
            "price": self.price,
            "airline": self.airline,
            "departure": self.departure,
            "arrival": self.arrival,
            "duration": self.duration,
        }


class HotelOption(BaseModel):
    """Hotel option from search results."""
    
    id: str = Field(..., description="Unique hotel identifier")
    city: str = Field(..., description="City code")
    name: str = Field(..., description="Hotel name")
    price: float = Field(..., ge=0, description="Price per night")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Star rating")
    category: Optional[str] = Field(default=None, description="Hotel category (Luxury, Mid-Range, etc.)")
    amenities: Optional[List[str]] = Field(default=None, description="Available amenities")
    check_in: Optional[str] = Field(default=None, description="Check-in date")
    check_out: Optional[str] = Field(default=None, description="Check-out date")
    total_price: Optional[float] = Field(default=None, description="Total price for stay")
    
    class Config:
        extra = "allow"
    
    def to_reservation_dict(self) -> dict:
        """Convert to dictionary format for storing as reservation."""
        return {
            "hotel_id": self.id,
            "city": self.city,
            "name": self.name,
            "price_per_night": self.price,
            "total_price": self.total_price or self.price,
            "rating": self.rating,
            "category": self.category,
            "amenities": self.amenities,
            "check_in": self.check_in,
            "check_out": self.check_out,
        }


class CarOption(BaseModel):
    """Car rental option from search results."""
    
    id: str = Field(..., description="Unique car rental identifier")
    city: str = Field(..., description="City code")
    company: str = Field(..., description="Rental company name")
    type: str = Field(..., description="Car type (Economy, SUV, Luxury, etc.)")
    model: str = Field(..., description="Car model")
    price: float = Field(..., ge=0, description="Price per day")
    features: Optional[List[str]] = Field(default=None, description="Car features")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Rating for selection")
    pickup_date: Optional[str] = Field(default=None, description="Pickup date")
    return_date: Optional[str] = Field(default=None, description="Return date")
    total_price: Optional[float] = Field(default=None, description="Total rental price")
    
    class Config:
        extra = "allow"
    
    def to_reservation_dict(self) -> dict:
        """Convert to dictionary format for storing as reservation."""
        return {
            "car_id": self.id,
            "city": self.city,
            "company": self.company,
            "car_type": self.type,
            "model": self.model,
            "price_per_day": self.price,
            "total_price": self.total_price or self.price,
            "features": self.features,
            "pickup_date": self.pickup_date,
            "return_date": self.return_date,
        }
