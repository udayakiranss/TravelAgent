# Prompt Audit Report

## Summary

This audit identifies all places where prompts are hardcoded in the codebase instead of being stored in `prompts.yaml`.

## Prompts Currently in `prompts.yaml` ✅

1. **`planner_base`** - Main planning prompt (used by TravelPlanner)
2. **`intent_parsing_base`** - Basic intent parsing (exists but not used)
3. **`intent_parsing_tool_binding`** - Intent parsing with tool binding (exists but not used)
4. **`modification_base`** - Itinerary modification prompt (partially used)
5. **`summary_generation_base`** - Summary generation prompt (used by ResponseFormatter)
6. **`task_routing_base`** - Task routing prompt (exists but NOT used by agents)

## Hardcoded Prompts Found ❌

### 1. **ResponseFormatter** (`agents/orchestration/response_formatter.py`)
- **Location**: Line 101-116
- **Status**: Has fallback prompt (should be removed)
- **Current**: Uses `prompts.yaml` via strategy, but has hardcoded fallback
- **Action**: Remove fallback prompt (strategy should always be available)

### 2. **Orchestrator - Modification** (`agents/orchestration/orchestrator.py`)
- **Location**: Line 383-398
- **Status**: Has fallback prompt (should be removed)
- **Current**: Uses `prompts.yaml` via strategy, but has hardcoded fallback
- **Action**: Remove fallback prompt (strategy should always be available)

### 3. **DeterministicPlanner - Intent Parsing** (`agents/planning/deterministic_planner.py`)
- **Location**: Line 204-220 (`_parse_query_with_preferences`)
- **Status**: Hardcoded prompt (should use `intent_parsing_base`)
- **Current**: Builds prompt manually
- **Action**: Use `prompts.yaml` → `intent_parsing_base`

### 4. **DeterministicPlanner - Tool Binding** (`agents/planning/deterministic_planner.py`)
- **Location**: Line 297-309 (`_parse_query_with_tool_binding`)
- **Status**: Hardcoded prompt (should use `intent_parsing_tool_binding`)
- **Current**: Builds prompt manually
- **Action**: Use `prompts.yaml` → `intent_parsing_tool_binding`

### 5. **FlightBookingAgent - Task Routing** (`agents/domain/flight_booking_agent.py`)
- **Location**: Line 212-218 (`_llm_route_task`)
- **Status**: Hardcoded prompt (should use `task_routing_base`)
- **Current**: Builds prompt manually with agent name
- **Action**: Use `prompts.yaml` → `task_routing_base` with `agent_name="Flight Booking Agent"`

### 6. **HotelBookingAgent - Task Routing** (`agents/domain/hotel_booking_agent.py`)
- **Location**: Line 208-214 (`_llm_route_task`)
- **Status**: Hardcoded prompt (should use `task_routing_base`)
- **Current**: Builds prompt manually with agent name
- **Action**: Use `prompts.yaml` → `task_routing_base` with `agent_name="Hotel Booking Agent"`

### 7. **CarRentalAgent - Task Routing** (`agents/domain/car_rental_agent.py`)
- **Location**: Line 138-144 (`_llm_route_task`)
- **Status**: Hardcoded prompt (should use `task_routing_base`)
- **Current**: Builds prompt manually with agent name
- **Action**: Use `prompts.yaml` → `task_routing_base` with `agent_name="Car Rental Agent"`

### 8. **ItineraryAgent - Task Routing** (`agents/domain/itinerary_agent.py`)
- **Location**: Line 340-346 (`_llm_route_task`)
- **Status**: Hardcoded prompt (should use `task_routing_base`)
- **Current**: Builds prompt manually with agent name
- **Action**: Use `prompts.yaml` → `task_routing_base` with `agent_name="Itinerary Management Agent"`

### 9. **PaymentAgent - Task Routing** (`agents/domain/payment_agent.py`)
- **Location**: Line 94-100 (`_llm_route_task`)
- **Status**: Hardcoded prompt (should use `task_routing_base`)
- **Current**: Builds prompt manually with agent name
- **Action**: Use `prompts.yaml` → `task_routing_base` with `agent_name="Payment Processing Agent"`

## Recommendations

### ✅ Priority 1: Remove Fallback Prompts - COMPLETED
- **ResponseFormatter**: ✅ Removed fallback (strategy required)
- **Orchestrator**: ✅ Removed fallback (strategy required)

### ✅ Priority 2: Use Existing Prompts from prompts.yaml - COMPLETED
- **DeterministicPlanner**: ✅ Uses `intent_parsing_base` and `intent_parsing_tool_binding`
- **All Agents**: ✅ Use `task_routing_base` with appropriate `agent_name` parameter
  - FlightBookingAgent ✅
  - HotelBookingAgent ✅
  - CarRentalAgent ✅
  - ItineraryAgent ✅
  - PaymentAgent ✅

### Design Compliance - ACHIEVED ✅
All prompts now come from `prompts.yaml` per the Model Invocation Strategy design. All hardcoded prompts have been removed and replaced with prompt repository calls.

## Implementation Summary

### Files Modified:
1. `agents/orchestration/response_formatter.py` - Removed fallback, requires strategy
2. `agents/orchestration/orchestrator.py` - Removed fallback, requires strategy, updated run_intent for legacy compatibility
3. `agents/planning/deterministic_planner.py` - Uses prompts.yaml for both intent parsing methods
4. `agents/domain/flight_booking_agent.py` - Uses task_routing_base from prompts.yaml
5. `agents/domain/hotel_booking_agent.py` - Uses task_routing_base from prompts.yaml
6. `agents/domain/car_rental_agent.py` - Uses task_routing_base from prompts.yaml
7. `agents/domain/itinerary_agent.py` - Uses task_routing_base from prompts.yaml
8. `agents/domain/payment_agent.py` - Uses task_routing_base from prompts.yaml

### Key Changes:
- All `_llm_route_task` methods now accept `ctx` parameter and use `ctx.model_strategy.get_prompt_for_use_case(UseCase.TASK_ROUTING, ...)`
- All `execute` methods now pass `ctx` to `_llm_route_task`
- DeterministicPlanner methods use `ctx.model_strategy` or `PromptRepository` directly
- Legacy `run_intent` method creates minimal ctx with strategy for backward compatibility
