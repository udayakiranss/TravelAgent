# Plan Trip API Flow Diagram

## Request to Response Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HTTP POST /agent/plan                           │
│                    NaturalLanguageQueryRequest                           │
│  { query: "Weekend trip to Paris", traveler_id: "user_123", ... }      │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  api/routes/agent.py                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ plan_trip()                                                      │  │
│  │ - Error handling wrapper                                         │  │
│  │ - Delegates to PlanningService                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  api/dependencies.py                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ get_context()                                                    │  │
│  │ - Creates TravelContext with session, LLM, request_id           │  │
│  │                                                                   │  │
│  │ get_planning_service()                                           │  │
│  │ - Gets cached TravelPlanner & Orchestrator                      │  │
│  │ - Returns PlanningService instance                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  api/services/planning_service.py                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ PlanningService.plan_trip()                                      │  │
│  │ 1. Populate ctx from request                                     │  │
│  │ 2. Call planner.create_plan_from_query()                        │  │
│  │ 3. Handle clarification if needed                               │  │
│  │ 4. Call orchestrator.execute_plan()                             │  │
│  │ 5. Build response via _build_plan_response()                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  agents/planning/planner.py                                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ TravelPlanner.create_plan_from_query()                           │  │
│  │                                                                   │  │
│  │ Path A: LLM Plan Generation (Preferred)                          │  │
│  │   → _plan_with_llm()                                            │  │
│  │     → _build_plan_prompt()                                      │  │
│  │     → llm.invoke_structured()                                   │  │
│  │     → _coerce_plan_dict()                                       │  │
│  │       → _safe_json_loads()                                     │  │
│  │     → ExecutionPlan.model_validate()                           │  │
│  │                                                                   │  │
│  │ Path B: Intent Parsing + Deterministic Planning (Fallback)      │  │
│  │   → _parse_query_with_tool_binding() OR                         │  │
│  │   → _parse_query_with_preferences() OR                         │  │
│  │   → _parse_rule_based()                                        │  │
│  │   → create_plan()                                              │  │
│  │     → _normalize_intent()                                      │  │
│  │       → _resolve_location()                                     │  │
│  │         → _find_city_by_airport()                             │  │
│  │     → _find_missing_mandatory()                                │  │
│  │       → _question_for_field()                                  │  │
│  │       → _blocked_tasks_for_field()                             │  │
│  │     → _apply_defaults()                                        │  │
│  │     → _build_tasks()                                           │  │
│  │     → _build_metadata()                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                │ Returns: ExecutionPlan
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  agents/orchestration/orchestrator.py                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Orchestrator.execute_plan()                                      │  │
│  │                                                                   │  │
│  │ For each task in plan.tasks:                                     │  │
│  │   1. _enrich_params() - Add context from previous tasks          │  │
│  │   2. Get agent from self.agents[agent_name]                      │  │
│  │   3. agent.execute(action, params, ctx)                          │  │
│  │      ┌──────────────────────────────────────────────────────┐  │  │
│  │      │ Domain Agents (agents/domain/*.py)                    │  │  │
│  │      │ - FlightBookingAgent.execute()                        │  │  │
│  │      │   → _select_best() [from BaseAgent]                   │  │  │
│  │      │   → _call_tool() [from BaseAgent]                     │  │  │
│  │      │ - HotelBookingAgent.execute()                         │  │  │
│  │      │ - CarRentalAgent.execute()                            │  │  │
│  │      │ - ItineraryAgent.execute()                            │  │  │
│  │      │ - PaymentAgent.execute()                              │  │  │
│  │      └──────────────────────────────────────────────────────┘  │  │
│  │   4. Store results in context                                 │  │
│  │   5. Extract options/reservations for response                │  │
│  │                                                                   │  │
│  │ Optional: Auto-build itinerary if missing                      │  │
│  │                                                                   │  │
│  │ Optional: Generate LLM summary                                 │  │
│  │   → ResponseFormatter.format_results()                        │  │
│  │     → llm.invoke() [if LLM available]                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                │ Returns: Dict with results
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  api/services/planning_service.py                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ PlanningService._build_plan_response()                          │  │
│  │ - Converts orchestrator result to PlanResponse                 │  │
│  │ - Handles partial results (no itinerary)                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PlanResponse (JSON)                             │
│  {                                                                      │
│    itinerary_id: "itin_abc123",                                        │
│    flight_options: [...],                                               │
│    hotel_options: [...],                                                │
│    car_options: [...],                                                  │
│    flight_reservation: {...},                                           │
│    hotel_reservation: {...},                                            │
│    car_reservation: {...},                                               │
│    summary: "Natural language summary...",                              │
│    ...                                                                  │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Method Count Summary

### By Layer

**API Layer (1 file):**
- `api/routes/agent.py`: 1 method
  - `plan_trip()` - Route handler

**Dependencies Layer (1 file):**
- `api/dependencies.py`: 2 methods
  - `get_context()` - Creates TravelContext
  - `get_planning_service()` - Creates PlanningService

**Service Layer (1 file):**
- `api/services/planning_service.py`: 2 methods
  - `plan_trip()` - Main service method
  - `_build_plan_response()` - Response builder

**Planning Layer (1 file):**
- `agents/planning/planner.py`: 19 methods
  - `create_plan_from_query()` - Public entry point
  - `create_plan()` - Deterministic planning
  - `_plan_with_llm()` - LLM plan generation
  - `_parse_query_with_tool_binding()` - Tool-based parsing
  - `_parse_query_with_preferences()` - Preference-aware parsing
  - `_parse_rule_based()` - Fallback parsing
  - `_normalize_intent()` - Location normalization
  - `_find_missing_mandatory()` - Validation
  - `_apply_defaults()` - Default application
  - `_build_tasks()` - Task DAG construction
  - `_build_metadata()` - Metadata creation
  - `_resolve_location()` - Location resolution
  - `_find_city_by_airport()` - Airport lookup
  - `_load_alias_map()` - Alias map loading
  - `_question_for_field()` - Question generation
  - `_blocked_tasks_for_field()` - Dependency analysis
  - `_build_plan_prompt()` - LLM prompt construction
  - `_coerce_plan_dict()` - Response normalization
  - `_safe_json_loads()` - JSON parsing

**Orchestration Layer (2 files):**
- `agents/orchestration/orchestrator.py`: 3 methods
  - `execute_plan()` - Main execution method
  - `_enrich_params()` - Parameter enrichment
  - `_get_preference_summary()` - Preference loading (optional)

- `agents/orchestration/response_formatter.py`: 1 method
  - `format_results()` - LLM summary generation (optional)

**Agent Layer (5 files):**
- `agents/domain/flight_booking_agent.py`: 1 method
  - `execute()` - Flight operations

- `agents/domain/hotel_booking_agent.py`: 1 method
  - `execute()` - Hotel operations

- `agents/domain/car_rental_agent.py`: 1 method
  - `execute()` - Car operations

- `agents/domain/itinerary_agent.py`: 1 method
  - `execute()` - Itinerary building

- `agents/domain/payment_agent.py`: 1 method
  - `execute()` - Payment processing

**Base Agent (1 file):**
- `agents/core/base_agent.py`: 2 methods (inherited by all agents)
  - `_select_best()` - Selection logic
  - `_call_tool()` - Tool invocation

### Total Method Count

| Layer | Files | Methods |
|-------|-------|---------|
| API Routes | 1 | 1 |
| Dependencies | 1 | 2 |
| Services | 1 | 2 |
| Planning | 1 | 19 |
| Orchestration | 2 | 4 |
| Domain Agents | 5 | 5 |
| Base Agent | 1 | 2 (shared) |
| **TOTAL** | **12 files** | **35 methods** |

### Execution Path Variations

**Path 1: LLM Plan Generation (Preferred)**
- Methods involved: ~12
- Flow: `create_plan_from_query()` → `_plan_with_llm()` → `execute_plan()` → agents

**Path 2: Intent Parsing + Deterministic (Fallback)**
- Methods involved: ~25
- Flow: `create_plan_from_query()` → `_parse_query_*()` → `create_plan()` → `execute_plan()` → agents

**Path 3: Rule-Based (No LLM)**
- Methods involved: ~20
- Flow: `create_plan_from_query()` → `_parse_rule_based()` → `create_plan()` → `execute_plan()` → agents

## Key Decision Points

1. **Clarification Needed?** → Returns 400 with missing_info
2. **LLM Available?** → Uses LLM plan generation or intent parsing
3. **Tool Binding Mode?** → Uses tool-based preference loading
4. **Summary Requested?** → Calls ResponseFormatter.format_results()
5. **Itinerary Built?** → Auto-builds if searches completed but itinerary missing

## Files Involved

1. `api/routes/agent.py`
2. `api/dependencies.py`
3. `api/services/planning_service.py`
4. `api/context.py` (TravelContext class)
5. `agents/planning/planner.py`
6. `agents/orchestration/orchestrator.py`
7. `agents/orchestration/response_formatter.py`
8. `agents/domain/flight_booking_agent.py`
9. `agents/domain/hotel_booking_agent.py`
10. `agents/domain/car_rental_agent.py`
11. `agents/domain/itinerary_agent.py`
12. `agents/domain/payment_agent.py`
13. `agents/core/base_agent.py`
14. `agents/core/llm_provider.py` (LLMProvider class)
15. `database/repository.py` (for itinerary persistence)

**Total: 15 files involved in the flow**
