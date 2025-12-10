# Planner DAG Design

## Problem Statement
The current planner is naive (flat list, no validation, no DAG, weak schema). We need a deterministic planner that:
- Decomposes a user goal into an executable DAG of atomic tasks.
- Detects missing mandatory info, applies defaults to optional info.
- Emits a strict JSON plan the Orchestrator can validate and execute (parallel or serial).
- Never executes tasks, calls external APIs, or guesses critical inputs.

## Goals
- Deterministically build a task DAG with explicit dependencies and parallelizable hints.
- Explicit routing via `agent + action` for each task.
- Return strict, schema-validated JSON with status (`executable` or `needs_clarification`).
- Surface missing mandatory fields with clarifying questions and which tasks are blocked.
- Include concrete `params` plus `input_schema`/`output_schema` contracts to avoid extra lookups.
- Keep planner output execution-agnostic (no retries/timeouts/costs).

## Non-Goals
- Do not execute tasks or call agents/tools.
- Do not guess mandatory inputs.
- Do not emit execution policies (timeouts, retries) or cost estimates.

## Final Planner Output Schema (travel-specific)
Top-level:
- `status`: `executable` | `needs_clarification`
- `missing_info`: array of missing field objects (see below)
- `tasks`: array of DAG nodes (agent+action explicit)
- `plan_metadata`: plan metadata

Schema sketch:
```json
{
  "status": "executable | needs_clarification",
  "missing_info": [
    {
      "field": "string",
      "severity": "mandatory | optional",
      "question": "string",
      "blocks_tasks": ["t1", "t2"]
    }
  ],
  "tasks": [
    {
      "id": "t1",
      "title": "string",
      "agent": "FlightBookingAgent | HotelBookingAgent | CarRentalAgent | ItineraryAgent | PaymentAgent",
      "action": "search_flights | search_hotels | search_cars | build_itinerary | process_payment",
      "description": "string",
      "input_schema": { "type": "object" },
      "params": { "type": "object" },
      "output_schema": { "type": "object" },
      "dependencies": ["tX"],
      "parallelizable": true
    }
  ],
  "plan_metadata": {
    "plan_id": "string",
    "created_at": "date-time",
    "planner_version": "string",
    "confidence_score": "number",
    "conversation_turns": "integer"
  }
}
```
Required fields:
- Top-level: `status`, `missing_info`, `tasks`, `plan_metadata`
- Task: `id`, `agent`, `action`, `input_schema`, `params`, `output_schema`, `dependencies`, `parallelizable`
- MissingInfo: `field`, `severity`, `question` (optional `blocks_tasks`)
- PlanMetadata: `plan_id`, `confidence_score` (others recommended)

## Examples
### Needs Clarification
User: “I need a flight and hotel to Paris.”
```json
{
  "status": "needs_clarification",
  "missing_info": [
    {
      "field": "origin",
      "severity": "mandatory",
      "question": "From which airport/city will you depart?",
      "blocks_tasks": ["t1"]
    },
    {
      "field": "departure_date",
      "severity": "mandatory",
      "question": "On what date would you like to fly to Paris?",
      "blocks_tasks": ["t1", "t2"]
    }
  ],
  "tasks": [],
  "plan_metadata": {
    "plan_id": "plan_12345",
    "created_at": "2025-12-10T10:45:00Z",
    "planner_version": "1.0.0",
    "confidence_score": 0.52,
    "conversation_turns": 1
  }
}
```

### Executable Plan
User: “Book flight and hotel from NYC to LON. Depart 2025-08-12, return 2025-08-16. Need car rental too.”
```json
{
  "status": "executable",
  "missing_info": [],
  "tasks": [
    {
      "id": "t1",
      "title": "Search outbound flights",
      "agent": "FlightBookingAgent",
      "action": "search_flights",
      "description": "Search flights NYC → LON on 2025-08-12",
      "input_schema": { "origin": {"type":"string"}, "destination": {"type":"string"}, "date": {"type":"string","format":"date"} },
      "params": { "origin": "NYC", "destination": "LON", "date": "2025-08-12" },
      "output_schema": { "flights": {"type":"array"} },
      "dependencies": [],
      "parallelizable": true
    },
    {
      "id": "t2",
      "title": "Search return flights",
      "agent": "FlightBookingAgent",
      "action": "search_flights",
      "description": "Search flights LON → NYC on 2025-08-16",
      "input_schema": { "origin": {"type":"string"}, "destination": {"type":"string"}, "date": {"type":"string","format":"date"} },
      "params": { "origin": "LON", "destination": "NYC", "date": "2025-08-16" },
      "output_schema": { "flights": {"type":"array"} },
      "dependencies": [],
      "parallelizable": true
    },
    {
      "id": "t3",
      "title": "Search hotels in London",
      "agent": "HotelBookingAgent",
      "action": "search_hotels",
      "description": "Search hotels in London 2025-08-12 to 2025-08-16",
      "input_schema": { "city": {"type":"string"}, "check_in": {"type":"string","format":"date"}, "check_out": {"type":"string","format":"date"} },
      "params": { "city": "LON", "check_in": "2025-08-12", "check_out": "2025-08-16" },
      "output_schema": { "hotels": {"type":"array"} },
      "dependencies": [],
      "parallelizable": true
    },
    {
      "id": "t4",
      "title": "Search car rentals in London",
      "agent": "CarRentalAgent",
      "action": "search_cars",
      "description": "Search cars in London 2025-08-12 to 2025-08-16",
      "input_schema": { "city": {"type":"string"}, "pickup_date": {"type":"string","format":"date"}, "return_date": {"type":"string","format":"date"} },
      "params": { "city": "LON", "pickup_date": "2025-08-12", "return_date": "2025-08-16" },
      "output_schema": { "cars": {"type":"array"} },
      "dependencies": [],
      "parallelizable": true
    },
    {
      "id": "t5",
      "title": "Build travel itinerary",
      "agent": "ItineraryAgent",
      "action": "build_itinerary",
      "description": "Compile chosen flight, hotel, and car into an itinerary",
      "input_schema": { "outbound_flight": {"type":"object"}, "return_flight": {"type":"object"}, "hotel": {"type":"object"}, "car": {"type":"object"} },
      "params": {},
      "output_schema": { "itinerary": {"type":"object"}, "total_cost": {"type":"number"} },
      "dependencies": ["t1", "t2", "t3", "t4"],
      "parallelizable": false
    }
  ],
  "plan_metadata": {
    "plan_id": "plan_67890",
    "created_at": "2025-12-10T10:48:00Z",
    "planner_version": "1.0.0",
    "confidence_score": 0.94,
    "conversation_turns": 1
  }
}
```

## Design Decisions (recap)
1) Explicit routing: include `agent + action` per task.  
2) Parallelizable hint kept: convenience for orchestrator; dependencies remain source of truth for DAG.  
3) Missing info: structured with severity, question, and blocks_tasks; drives `status`.  
4) Params vs schema: include both `params` (values) and `input_schema`/`output_schema` (contracts).  
5) Mandatory vs optional: block on missing mandatory; apply defaults for optional (e.g., passengers=1, cabin_class=economy).  
6) Execution concerns out-of-scope: timeouts, retries, cost estimation remain in agent config, not planner output.  
7) Domain-specific: travel agents only (FlightBookingAgent, HotelBookingAgent, CarRentalAgent, ItineraryAgent, PaymentAgent).  
8) City/Airport normalization: use tiered aliasing; never invent airports—ask if ambiguous.  
9) Data source: store aliases in JSON (e.g., `data/city_airport_aliases.json`); allow add/update/delete via PR; small Tier A list may be echoed in prompt for most common metros.  
10) Prompt: include normalization rules and fallback policy; defer to JSON map for authoritative resolution; ask clarifying questions when not found or ambiguous.

## Flow Summary
1) Validate intent → identify missing mandatory/optional; apply defaults to optional.  
2) If mandatory missing → `status=needs_clarification`, return missing_info (tasks empty or partial).  
3) If complete → build tasks (agent+action), params, schemas; set dependencies; mark parallelizable; derive execution groups (orchestrator).  
4) Return strict JSON plan; orchestrator runs groups; planner never executes tasks.  

## City/Airport Normalization & Alias Map
- Tiered approach:  
  - Tier A (small, common metros) may be mirrored in prompt for guidance;  
  - Full alias map lives in JSON (e.g., `data/city_airport_aliases.json`) and is loaded at runtime.  
- Guardrails:  
  - Normalize user lingo to canonical city + IATA codes using the map.  
  - If not found or ambiguous, do not guess—ask via `missing_info`.  
  - Prefer primary airports from the map; if multiple plausible options, ask which one.  
  - Reject/clarify unknown or invalid IATA codes (not in map).  
- Maintenance: source-controlled JSON, PR-reviewed updates, unit tests for known aliases, ambiguity handling, and typo rejection.  
