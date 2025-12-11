"""
Agents package - Backward-compatible re-exports

This module provides backward-compatible imports for the restructured agents package.
All imports from the old flat structure are re-exported here.
"""

# Core components
from agents.core import (
    BaseAgent,
    LLMProvider,
    create_llm_provider,
    extract_token_usage,
    route_task,
    SimpleMemory,
    create_memory,
)

# Planning components
from agents.planning import (
    TravelPlanner,
    plan_trip,
    ExecutionPlan,
    MissingInfo,
    PlanMetadata,
    PlanTask,
)

# Domain agents
from agents.domain import (
    FlightBookingAgent,
    HotelBookingAgent,
    CarRentalAgent,
    ItineraryAgent,
    PaymentAgent,
)

# Orchestration components
from agents.orchestration import (
    Orchestrator,
    ResponseFormatter,
    OutputFormat,
)

# Backward compatibility: Re-export commonly used items at package level
# This allows: from agents import Orchestrator, TravelPlanner, etc.
__all__ = [
    # Core
    "BaseAgent",
    "LLMProvider",
    "create_llm_provider",
    "extract_token_usage",
    "route_task",
    "SimpleMemory",
    "create_memory",
    # Planning
    "TravelPlanner",
    "plan_trip",
    "ExecutionPlan",
    "MissingInfo",
    "PlanMetadata",
    "PlanTask",
    # Domain agents
    "FlightBookingAgent",
    "HotelBookingAgent",
    "CarRentalAgent",
    "ItineraryAgent",
    "PaymentAgent",
    # Orchestration
    "Orchestrator",
    "ResponseFormatter",
    "OutputFormat",
]
