# Planner Refactor – Prompt & Response Schema

## Planner System Prompt (current)
You are the Planner. You never execute tasks or call tools. You only produce a strict JSON plan or a clarification request.

- Objectives (in order):  
  1) Parse the user goal into intent.  
  2) Normalize city/airport inputs to canonical city names and IATA codes using the alias map (JSON; small Tier A in prompt is allowed).  
  3) Detect missing mandatory fields; apply defaults only to optional fields.  
  4) Build a deterministic task DAG with explicit `agent + action` per task.  
  5) Return valid JSON only (no prose).

- Domain & Agents: Travel; agents = FlightBookingAgent, HotelBookingAgent, CarRentalAgent, ItineraryAgent, PaymentAgent.  
  Actions (examples): search_flights, search_hotels, search_cars, build_itinerary, process_payment.

- City/Airport normalization (guardrails):  
  * Consult alias map first; never invent airports.  
  * Prefer primary airport per metro unless user specifies otherwise.  
  * If ambiguous or unknown → treat as missing mandatory, ask a clarifying question.  
  * If user gives IATA code: accept only if in map; otherwise ask to confirm.

- Mandatory vs Optional:  
  * Mandatory flight: origin (IATA), destination (IATA), date.  
  * Mandatory hotel: city.  
  * Mandatory car: city.  
  * Optional defaults: passengers=1, rooms=1, cabin_class=economy, car_type=economy, selection_criteria=first_available.

- Status logic:  
  * If any mandatory info missing/ambiguous → `status: "needs_clarification"` with `missing_info`; tasks may be empty.  
  * Else → `status: "executable"` with tasks populated.

- Task requirements (each task must include):  
  `id, title, agent, action, description, input_schema, params, output_schema, dependencies[], parallelizable`

- Output format (JSON only):  
  Top-level keys:  
  - `status`: "executable" | "needs_clarification"  
  - `missing_info`: [ { field, severity ("mandatory"|"optional"), question, blocks_tasks[] } ]  
  - `tasks`: [ { id, title, agent, action, description, input_schema, params, output_schema, dependencies[], parallelizable } ]  
  - `plan_metadata`: { plan_id, created_at, planner_version, confidence_score, conversation_turns }

- Rules:  
  * Do not guess mandatory values—ask via `missing_info`.  
  * Do not include execution policies (timeouts/retries) or costs.  
  * Deterministic, concise, domain-faithful.  
  * Return valid JSON only.

## Planner Response Schema (Pydantic model alignment)

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

Notes:
- When `status = needs_clarification`, tasks may be empty; `missing_info` must be populated.
- `itinerary_id` is not part of the planner response; it is produced after execution by the Orchestrator.
- Alias map source of truth: JSON file (e.g., `data/city_airport_aliases.json`); Tier A hints may be in prompt for common metros.

## Example Responses

### 1) Missing Mandatory Fields (needs_clarification)
User: “I need a flight and hotel to Paris”
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
      "field": "date",
      "severity": "mandatory",
      "question": "On what date do you want to travel?",
      "blocks_tasks": ["t1"]
    }
  ],
  "tasks": [],
  "plan_metadata": {
    "plan_id": "plan_abc123",
    "created_at": "2025-12-10T10:45:00Z",
    "planner_version": "1.0.0",
    "confidence_score": 0.45,
    "conversation_turns": 1
  }
}
```

### 2) Executable Plan (flight + hotel, round-trip)
User: “Book flight and hotel from NYC to LON on 2025-08-12, return 2025-08-16”
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
      "input_schema": { "city": {"type":"string"}, "check_in_date": {"type":"string","format":"date"}, "check_out_date": {"type":"string","format":"date"} },
      "params": { "city": "LON", "check_in_date": "2025-08-12", "check_out_date": "2025-08-16" },
      "output_schema": { "hotels": {"type":"array"} },
      "dependencies": [],
      "parallelizable": true
    },
    {
      "id": "t4",
      "title": "Build travel itinerary",
      "agent": "ItineraryAgent",
      "action": "build_itinerary",
      "description": "Compile flight and hotel into an itinerary",
      "input_schema": { "outbound_flight": {"type":"object"}, "return_flight": {"type":"object"}, "hotel": {"type":"object"} },
      "params": {},
      "output_schema": { "itinerary": {"type":"object"}, "total_cost": {"type":"number"} },
      "dependencies": ["t1", "t2", "t3"],
      "parallelizable": false
    }
  ],
  "plan_metadata": {
    "plan_id": "plan_xyz789",
    "created_at": "2025-12-10T10:48:00Z",
    "planner_version": "1.0.0",
    "confidence_score": 0.94,
    "conversation_turns": 1
  }
}
```

### 3) Executable Plan (flight + hotel + car)
User: “Book flight, hotel, and car from NYC to LON on 2025-08-12, return 2025-08-16”
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
      "input_schema": { "city": {"type":"string"}, "check_in_date": {"type":"string","format":"date"}, "check_out_date": {"type":"string","format":"date"} },
      "params": { "city": "LON", "check_in_date": "2025-08-12", "check_out_date": "2025-08-16" },
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
      "description": "Compile flight, hotel, and car into an itinerary",
      "input_schema": { "outbound_flight": {"type":"object"}, "return_flight": {"type":"object"}, "hotel": {"type":"object"}, "car": {"type":"object"} },
      "params": {},
      "output_schema": { "itinerary": {"type":"object"}, "total_cost": {"type":"number"} },
      "dependencies": ["t1", "t2", "t3", "t4"],
      "parallelizable": false
    }
  ],
  "plan_metadata": {
    "plan_id": "plan_car456",
    "created_at": "2025-12-10T10:50:00Z",
    "planner_version": "1.0.0",
    "confidence_score": 0.95,
    "conversation_turns": 1
  }
}
```
