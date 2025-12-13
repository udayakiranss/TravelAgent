# Model Invocation Strategy Design Plan

## Overview

This plan designs a centralized model invocation strategy for the travel booking application that provides fine-grained control over provider and model selection per use case. The design includes:

- **Provider-specific configuration isolation** - Model changes don't affect overall design
- **Explicit use case overrides** - Same provider/model with different settings per use case
- **Prompt repository** - Centralized prompt management with template support
- **Dedicated LLM module** - Clean separation of concerns for long-term maintainability
- **Fail-fast error handling** - Catch configuration issues at startup
- **Comprehensive testing** - Unit, integration, and validation tests

## Design Decisions

### Configuration Design

- **Format**: YAML (readable, easy to edit manually)
- **Location**: `llm/config/` directory (co-located with code)
- **Loading**: At import time (simpler, fail fast on errors)
- **Overrides**: Explicit per use case, merge with defaults (only override specified keys)
- **Validation**: No strict validation - allow any parameter override, fail at runtime if unsupported
- **Environment Variables**: Supported for secrets. Config files store the *name* of the env var (e.g. `OPENAI_API_KEY`), not the value. Values are loaded from `os.environ` at runtime.

### Prompt Repository

- **Storage**: Single `prompts.yaml` file
- **Templating**: F-string style variable substitution
- **Reference**: Use cases reference prompts by ID
- **Inheritance**: Not supported initially (keep simple)
- **Provider Variants**: Explicit selection by use case
- **Inline Overrides**: Supported for complex dynamic prompts

### Error Handling

- **Config Loading**: Fail fast (raise exceptions if config missing/invalid)
- **Runtime**: Fail fast (raise exceptions for missing prompts, invalid references)
- **No Graceful Degradation**: Catch issues early, don't silently fail

### Migration Strategy

- **Approach**: Big bang (move everything at once)
- **Timeline**: Since not live, can do clean break
- **Scope**: Update all imports, remove old code

### Testing Strategy

- **Unit Tests**: Each module (`llm/strategy/`, `llm/providers/`, `llm/prompts/`)
- **Integration Tests**: Full flow (use case → LLM → response)
- **Config Validation Tests**: Invalid configs, missing files, schema validation

## Architecture Design

### Folder Structure

```
travel-agents/
├── llm/                                    # NEW - Dedicated LLM module
│   ├── __init__.py                         # Public API + config loading at import
│   │
│   ├── strategy/                           # Model invocation strategy
│   │   ├── __init__.py
│   │   ├── model_strategy.py              # Main orchestrator
│   │   ├── use_cases.py                   # UseCase enum/constants
│   │   ├── config_loader.py               # Load YAML, validate, fail fast
│   │   └── resolver.py                    # Merge defaults + overrides
│   │
│   ├── providers/                          # Provider abstractions
│   │   ├── __init__.py
│   │   ├── base.py                        # Base provider interface
│   │   ├── factory.py                     # Create provider instances
│   │   └── capabilities.py                # Provider capability detection
│   │
│   ├── prompts/                            # Prompt management
│   │   ├── __init__.py
│   │   ├── repository.py                 # Load prompts.yaml, template substitution
│   │   └── template.py                    # Variable substitution logic
│   │
│   └── config/                             # Configuration files
│       ├── model_strategy.yaml             # Main config (use cases, providers, defaults)
│       └── prompts.yaml                    # Prompt repository
│
├── agents/
│   └── core/
│       └── llm_provider.py                 # EXISTING - Will use llm/ module internally
│
└── api/
    └── config.py                           # EXISTING - API-specific config only
```

### Module Responsibilities

#### `llm/strategy/`

- **model_strategy.py**: Main entry point, orchestrates LLM selection and prompt retrieval
- **use_cases.py**: UseCase enum defining all use cases
- **config_loader.py**: Load and validate YAML configs, fail fast on errors
- **resolver.py**: Merge provider defaults, global defaults, and use case overrides

#### `llm/providers/`

- **base.py**: Abstract base class for providers
- **factory.py**: Create provider instances based on config
- **capabilities.py**: Detect and validate provider capabilities

#### `llm/prompts/`

- **repository.py**: Load prompts from YAML, cache, template substitution
- **template.py**: F-string style variable substitution

### Public API Design

```python
# llm/__init__.py - Clean public API
from llm.strategy.model_strategy import ModelInvocationStrategy
from llm.strategy.use_cases import UseCase
from llm.prompts.repository import PromptRepository

# Usage in agents:
from llm import ModelInvocationStrategy, UseCase

strategy = ModelInvocationStrategy()
llm = strategy.get_llm_for_use_case(UseCase.PLANNER, context=ctx)
prompt = strategy.get_prompt_for_use_case(
    UseCase.PLANNER, 
    query=query, 
    preference_summary=preference_summary
)
```

## Configuration Format

### YAML Structure

**`llm/config/model_strategy.yaml`**:

> [!CAUTION]
> **Security Warning**: Do NOT store actual API keys or secrets in this YAML file.
> Always use `api_key_env` to reference the environment variable name (e.g. `OPENAI_API_KEY`).
> The application will read the value from the environment at runtime.

```yaml
use_cases:
  planner:
    provider: openai
    model: gpt-4o
    prompt: planner_base
    overrides:
      temperature: 0
      enable_json_mode: true
      max_tokens: 4000
      enable_prompt_caching: true
      timeout: 30
      max_retries: 3
    fallback:
      provider: anthropic
      model: claude-3-5-sonnet-latest
      overrides:
        temperature: 0
        enable_json_mode: true

  intent_parsing:
    provider: openai
    model: gpt-4o-mini
    prompt: intent_parsing_base
    overrides:
      temperature: 0
      enable_json_mode: true
      max_tokens: 2000
      enable_tool_binding: true

  summary_generation:
    provider: openai
    model: gpt-4o  # Same provider/model as planner
    prompt: summary_generation_base
    overrides:  # But different settings
      temperature: 0.3
      enable_json_mode: false
      max_tokens: 500
      enable_prompt_caching: false

  task_routing:
    provider: openai
    model: gpt-3.5-turbo
    prompt: task_routing_base
    overrides:
      temperature: 0
      enable_json_mode: false
      max_tokens: 50
      timeout: 5
      max_retries: 1

  modification:
    provider: openai
    model: gpt-4o
    prompt: modification_base
    overrides:
      temperature: 0
      enable_json_mode: false
      max_tokens: 2000
      timeout: 20

providers:
  openai:
    default_model: gpt-4o
    capabilities:
      json_mode: true
      tool_binding: true
      prompt_caching: true
    models:
      gpt-4o:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 16384
        default_temperature: 0
      gpt-4-turbo:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 128000
        default_temperature: 0
      gpt-4o-mini:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 16384
        default_temperature: 0
      gpt-3.5-turbo:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 16384
        default_temperature: 0
    provider_specific_settings:
      json_mode_param: response_format
      json_mode_value:
        type: json_object
      api_key_env: OPENAI_API_KEY

  anthropic:
    default_model: claude-3-5-sonnet-latest
    capabilities:
      json_mode: true
      tool_binding: true
      prompt_caching: false
    models:
      claude-3-5-sonnet-latest:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 8192
        default_temperature: 0
    provider_specific_settings:
      json_mode_param: response_format
      json_mode_value:
        type: json_schema
      api_key_env: ANTHROPIC_API_KEY

  google_genai:
    default_model: gemini-2.0-flash
    capabilities:
      json_mode: true
      tool_binding: true
      prompt_caching: false
    models:
      gemini-2.0-flash:
        supports_json_mode: true
        supports_tool_binding: true
        max_tokens_limit: 8192
        default_temperature: 0
    provider_specific_settings:
      json_mode_param: response_mime_type
      json_mode_value: application/json
      api_key_env: GOOGLE_API_KEY

  groq:
    default_model: llama-3.1-70b-versatile
    capabilities:
      json_mode: false
      tool_binding: false
      prompt_caching: false
    models:
      llama-3.1-70b-versatile:
        supports_json_mode: false
        supports_tool_binding: false
        max_tokens_limit: 8192
        default_temperature: 0
    provider_specific_settings:
      api_key_env: GROQ_API_KEY

defaults:
  temperature: 0
  max_tokens: 2000
  timeout: 30
  max_retries: 2
```

**`llm/config/prompts.yaml`**:

```yaml
prompts:
  planner_base:
    system: null
    user: |
      Planner: Parse query, generate tasks. Return JSON only.
      
      Query: {query}
      Preferences: {preference_summary}
      
      Return JSON with: status ('executable' or 'needs_clarification'), missing_info (array), tasks (array), plan_metadata (object).
      If missing critical info (origin/destination/date for flights, city for hotels/cars), set status='needs_clarification' with missing_info.
      Tasks: Each task needs id (string like 't1'), title, agent, action, description, input_schema (object), params (object), output_schema (object), dependencies (array of task id strings), parallelizable (boolean).
      Agents: FlightBookingAgent, HotelBookingAgent, CarRentalAgent, ItineraryAgent, PaymentAgent.
      Actions: search_flights, search_hotels, search_cars, build_itinerary, process_payment.
      plan_metadata: plan_id (string), created_at (ISO string), planner_version (string), confidence_score (number), conversation_turns (number).

  intent_parsing_base:
    system: null
    user: |
      Parse the following user query about travel booking into a structured intent format.
      
      User Query: "{text}"
      
      Traveler Preferences: {preference_summary}
      
      Extract the following information:
      - needs: List of services needed (flight, hotel, car, itinerary)
      - from: Origin airport code (3 letters, uppercase)
      - to: Destination airport code (3 letters, uppercase)
      - date: Travel date in YYYY-MM-DD format
      
      Note: Consider the traveler's preferences when interpreting ambiguous requests.
      Return ONLY a valid JSON object with these fields.

  intent_parsing_tool_binding:
    system: null
    user: |
      Parse the following user query about travel booking into a structured intent format.
      
      User Query: "{text}"
      
      Traveler ID: {traveler_id}
      Traveler Preferences Summary: {preference_summary}
      
      If you need detailed preferences (loyalty program numbers, dietary restrictions, accessibility needs, or past booking patterns), use the load_full_preferences tool.
      
      Extract the following information:
      - needs: List of services needed (flight, hotel, car, itinerary)
      - from: Origin airport code (3 letters, uppercase)
      - to: Destination airport code (3 letters, uppercase)
      - date: Travel date in YYYY-MM-DD format
      
      Return ONLY a valid JSON object with these fields.

  modification_base:
    system: You are a travel agent assistant.
    user: |
      You are a travel agent assistant. Based on the current itinerary state and user instruction, determine what needs to be modified.
      
      Current Itinerary State:
      {current_state}
      
      Previous Conversation:
      {history_text}
      
      User Instruction: {instruction}
      
      Analyze the instruction and respond with a JSON object containing:
      - "component": which component to modify ("flight", "hotel", or "car")
      - "action": what action to take ("search_new", "remove", "update")
      - "parameters": any search parameters extracted from the instruction
      
      Respond with ONLY the JSON object.

  summary_generation_base:
    system: You are a friendly travel assistant.
    user: |
      You are a friendly travel assistant. Convert the following booking results into a warm, conversational summary for the traveler.
      
      **Travel Request:**
      - Origin: {origin}
      - Destination: {destination}
      - Travel Date: {date}
      - Services Requested: {services}
      
      **Booking Results (JSON):**
      {results_json}
      
      **Instructions:**
      1. Create a friendly, well-formatted summary of the travel booking
      2. Start with a welcoming header mentioning the destination
      3. For each booking (flight, hotel, car, itinerary), provide key details in a readable format
      4. If any booking failed or has an error, mention it politely and suggest alternatives
      5. End with the total estimated cost and a friendly closing message
      6. Use natural dates (e.g., "April 1st" instead of "2026-04-01")
      7. Format prices with currency symbols (e.g., "$350")
      8. Keep the response concise but informative (around 150-250 words)
      9. Do NOT use markdown formatting or special characters - use plain text with simple line breaks
      
      Generate the natural language summary:

  task_routing_base:
    system: You are a {agent_name}.
    user: |
      You are a {agent_name}. Based on the task and parameters, determine which tool to use.
      
      Available tools: {available_tools}
      Task: {task}
      Parameters: {params}
      
      Respond with only the tool name to use.
```

### Configuration Resolution Logic

1. **Start with provider/model defaults** (from `providers[provider].models[model]`)
2. **Merge global defaults** (from `defaults` section) if not in provider config
3. **Merge use case overrides** (from `use_cases[use_case].overrides`) - only specified keys
4. **No validation** - use as-is, fail at runtime if unsupported

### Override Behavior

- **Merge semantics**: Only specified keys override, others inherit
- **No capability checks**: Trust config, fail at runtime if provider doesn't support feature
- **Explicit is better**: Clear what settings are applied per use case

## Implementation Approach

### Phase 1: Create LLM Module Structure

1. Create `llm/` directory structure
2. Create `llm/__init__.py` with public API
3. Create `llm/strategy/` module with placeholder files
4. Create `llm/providers/` module with placeholder files
5. Create `llm/prompts/` module with placeholder files
6. Create `llm/config/` directory with YAML files

### Phase 2: Implement Core Components

1. **Config Loader** (`llm/strategy/config_loader.py`)
   - Load YAML files at import time
   - Validate structure (fail fast)
   - Return config dict

2. **Use Cases** (`llm/strategy/use_cases.py`)
   - Define UseCase enum
   - Map use case names to constants

3. **Resolver** (`llm/strategy/resolver.py`)
   - Merge provider defaults + global defaults + overrides
   - Return resolved config for use case

4. **Prompt Repository** (`llm/prompts/repository.py`)
   - Load prompts.yaml at import
   - Cache prompts
   - Template substitution (f-string style)

5. **Model Strategy** (`llm/strategy/model_strategy.py`)
   - Main orchestrator
   - `get_llm_for_use_case()` - returns LLMProvider instance
   - `get_prompt_for_use_case()` - returns prompt string

### Phase 3: Provider Integration

1. **Provider Factory** (`llm/providers/factory.py`)
   - Create LLMProvider instances based on config
   - Handle provider-specific settings (JSON mode, etc.)

2. **Capabilities** (`llm/providers/capabilities.py`)
   - Detect provider capabilities
   - Map provider names to implementations

### Phase 4: Integration & Migration

1. Update all LLM call sites to use `llm` module
2. Update imports across codebase
3. Remove old `agents/core/llm_provider.py` (or refactor to use `llm/`)
4. Update tests

### Phase 5: Testing

1. Unit tests for each module
2. Integration tests for full flow
3. Config validation tests
4. Prompt template tests

## Migration Plan

### Big Bang Approach

1. **Create new structure** - Build `llm/` module alongside existing code
2. **Update all imports** - Change from `agents.core.llm_provider` to `llm`
3. **Update all call sites** - Use `ModelInvocationStrategy` instead of direct LLMProvider
4. **Remove old code** - Delete or refactor `agents/core/llm_provider.py`
5. **Update tests** - Fix all test imports and mocks

### Files to Modify

**LLM Call Sites** (10 locations):

- `agents/planning/planner.py`
- `agents/planning/deterministic_planner.py`
- `agents/orchestration/orchestrator.py`
- `agents/orchestration/response_formatter.py`
- `agents/domain/flight_booking_agent.py`
- `agents/domain/hotel_booking_agent.py`
- `agents/domain/car_rental_agent.py`
- `agents/domain/itinerary_agent.py`
- `agents/domain/payment_agent.py`
- `api/dependencies.py`

**Dependencies**:

- `api/dependencies.py` - Update LLM provider dependency
- `api/services/planning_service.py` - May need updates
- All test files - Update mocks and imports

## Testing Strategy

### Unit Tests

**`llm/strategy/`**:

- `test_config_loader.py` - Config loading, validation, error cases
- `test_resolver.py` - Override merging logic
- `test_model_strategy.py` - LLM selection, prompt retrieval

**`llm/providers/`**:

- `test_factory.py` - Provider instance creation
- `test_capabilities.py` - Capability detection

**`llm/prompts/`**:

- `test_repository.py` - Prompt loading, caching
- `test_template.py` - Variable substitution

### Integration Tests

- Full flow: Use case → ModelStrategy → LLMProvider → Response
- Multiple use cases with different providers
- Fallback provider behavior
- Prompt template substitution with real variables

### Config Validation Tests

- Invalid YAML structure
- Missing required fields
- Invalid provider/model combinations
- Missing prompt references
- Invalid override values

## Current State Analysis

### LLM Integration Points

1. **Planner - NL Query Parsing** (HIGH complexity)
   - Location: `agents/planning/planner.py::TravelPlanner._plan_with_llm()`
   - Method: `invoke_structured()`
   - Use Case: `UseCase.PLANNER`

2. **Deterministic Planner - Intent Parsing** (MEDIUM complexity)
   - Location: `agents/planning/deterministic_planner.py::_parse_query_with_preferences()`
   - Method: `invoke_structured()`
   - Use Case: `UseCase.INTENT_PARSING`

3. **Deterministic Planner - Tool Binding** (MEDIUM-HIGH complexity)
   - Location: `agents/planning/deterministic_planner.py::_parse_query_with_tool_binding()`
   - Method: `invoke()` with tool binding
   - Use Case: `UseCase.INTENT_PARSING` (with tool_binding override)

4. **Orchestrator - Result Summary** (MEDIUM complexity)
   - Location: `agents/orchestration/orchestrator.py::execute_plan()` → `ResponseFormatter`
   - Method: `invoke()` with `disable_json_mode=True`
   - Use Case: `UseCase.SUMMARY_GENERATION`

5. **Orchestrator - Itinerary Modification** (MEDIUM-HIGH complexity)
   - Location: `agents/orchestration/orchestrator.py::modify_itinerary()`
   - Method: `invoke()`
   - Use Case: `UseCase.MODIFICATION`

6. **Domain Agents - Task Routing** (LOW complexity, 5 agents)
   - Locations: All domain agents `_llm_route_task()` methods
   - Method: `invoke()`
   - Use Case: `UseCase.TASK_ROUTING`

## Benefits

1. **Fine-grained control**: Select optimal model for each use case
2. **Cost optimization**: Use cheaper models for simple tasks
3. **Performance**: Use faster models where latency matters
4. **Flexibility**: Easy to experiment with different models
5. **Resilience**: Per-use-case fallback support
6. **Maintainability**: Centralized configuration and prompts
7. **Long-term scalability**: Clean module structure for future enhancements
8. **Type safety**: UseCase enum prevents typos
9. **Clear separation**: LLM concerns isolated from business logic
