"""
Schemas for planner output structures.

Defines the strict JSON contract for the Planner:
- ExecutionPlan: top-level plan with status, missing_info, tasks, and metadata
- PlanTask: atomic task node with explicit agent+action, params, schemas, deps
- MissingInfo: describes missing fields, severity, clarifying question, blocked tasks
- PlanMetadata: plan identifiers and confidence
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

StatusType = Literal["executable", "needs_clarification"]
SeverityType = Literal["mandatory", "optional"]


class MissingInfo(BaseModel):
    """Missing field descriptor for clarification."""

    field: str = Field(..., description="Name of the missing field")
    severity: SeverityType = Field(..., description="mandatory or optional")
    question: str = Field(..., description="Clarifying question to ask the user")
    blocks_tasks: Optional[List[str]] = Field(
        default=None, description="Task IDs blocked by this missing field"
    )


class PlanTask(BaseModel):
    """Atomic task node with explicit routing and schemas."""

    id: str = Field(..., description="Unique task ID (e.g., t1)")
    title: Optional[str] = Field(default=None, description="Human-friendly title")
    agent: str = Field(
        ...,
        description="Explicit agent name, e.g., FlightBookingAgent, HotelBookingAgent",
    )
    action: str = Field(
        ...,
        description="Action name understood by the agent, e.g., search_flights",
    )
    description: Optional[str] = Field(
        default=None, description="Short description of what the task does"
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Contract for required/optional inputs"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Concrete runtime values for this task"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Contract for outputs produced"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Task IDs that must complete before this task"
    )
    parallelizable: bool = Field(
        default=True,
        description="Hint: can run alongside other ready tasks; dependencies still enforce order",
    )


class PlanMetadata(BaseModel):
    """Metadata describing the plan."""

    plan_id: str = Field(..., description="Unique plan identifier")
    created_at: Optional[str] = Field(
        default=None, description="Creation timestamp (ISO 8601)"
    )
    planner_version: Optional[str] = Field(
        default=None, description="Planner version string"
    )
    confidence_score: float = Field(
        ..., description="Confidence in the task decomposition"
    )
    conversation_turns: Optional[int] = Field(
        default=None, description="Number of turns used to finalize this plan"
    )


class ExecutionPlan(BaseModel):
    """Top-level planner output."""

    status: StatusType = Field(..., description="executable | needs_clarification")
    missing_info: List[MissingInfo] = Field(
        default_factory=list,
        description="Missing fields that block execution or need defaults/confirmation",
    )
    tasks: List[PlanTask] = Field(
        default_factory=list, description="Planned tasks as a DAG"
    )
    plan_metadata: PlanMetadata = Field(..., description="Plan metadata")
