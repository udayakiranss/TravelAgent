# User Preferences as Skill Tool

## Architecture Overview

Adding user preferences as a new feature using a **tiered loading pattern** that balances latency and token efficiency:

```
Current: [system prompt + query] → Model → Response
         (no personalization - all travelers get same recommendations)

New:     [system prompt + preference SUMMARY (~50 tokens) + query] → Model
            │
            ├── 90% of cases: Response (single LLM call)
            │
            └── 10% of cases: tool call → full preferences → Response (2 LLM calls)
```

**Design choice:** Rather than always sending full preferences (~500 tokens) with every request, we use a tiered approach:
- Always include a compact summary for basic personalization
- Provide a tool for full details when the model determines it needs them (e.g., dietary restrictions, loyalty numbers)

## Latency and Token Analysis

| Approach | Avg Latency | Input Tokens | LLM Calls |
|----------|-------------|--------------|-----------|
| Always full preferences | ~1.5s | ~1000 | 1 |
| **Summary + tool (chosen)** | **~1.6s** | **~500 avg** | **1.1 avg** |
| Pure tool-based | ~2.7s | ~600 + ~1000 | 2 |

## Data Architecture

### Storage Strategy (Database + Filesystem Cache)

```
┌─────────────────────────────────────────────────────────────────┐
│  Custom @tool (semantic layer)                                  │
│  load_full_preferences(traveler_id) -> dict                     │
│    - Clear docstring for model understanding                    │
│    - Returns full detailed preferences                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Filesystem Cache (fast reads for tool execution)               │
│  data/user_preferences/{traveler_id}.json                       │
│    - Read via standard file I/O                                 │
│    - ~5ms read latency                                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Database (source of truth)                                     │
│  UserPreferences table                                          │
│    - CRUD via repository                                        │
│    - Write-through to filesystem cache on updates               │
└─────────────────────────────────────────────────────────────────┘
```

### Preference Structure (Detailed)

```python
class UserPreferences(SQLModel, table=True):
    traveler_id: str              # Primary key
    # Core preferences
    flight_preferences: dict      # seat_type, airline, cabin_class
    hotel_preferences: dict       # min_rating, room_type, amenities
    car_preferences: dict         # car_type, features
    budget_range: dict            # min, max, currency
    # Detailed (loaded via tool)
    dietary_restrictions: list    # vegetarian, gluten-free, etc.
    accessibility_needs: list     # wheelchair, hearing, etc.
    loyalty_programs: list        # [{program, number, tier}]
    past_bookings_summary: dict   # aggregated stats
    updated_at: datetime
```

### Two-Tier Data Split

**Summary (always in prompt, ~50 tokens):**
```
"Traveler prefers: economy+, aisle seat, 4+ star hotels, budget $1500-3000"
```

**Full Details (via tool, ~500 tokens):**
```json
{
  "flight_preferences": {"seat": "aisle", "cabin": "economy_plus", "airlines": ["Delta", "United"]},
  "dietary_restrictions": ["vegetarian", "no-nuts"],
  "loyalty_programs": [{"program": "Delta SkyMiles", "number": "123456", "tier": "Gold"}],
  "past_bookings_summary": {"avg_hotel_rating": 4.2, "preferred_destinations": ["LAX", "SFO"]}
}
```

## Tool Implementation

### Custom @tool with LangChain (Recommended)

```python
# tools/preference_tools.py
from langchain.tools import tool

@tool
def load_full_preferences(traveler_id: str) -> dict:
    """Load complete user preferences for personalized travel recommendations.
    
    Call this when you need detailed information such as:
    - Specific dietary restrictions or allergies
    - Loyalty program numbers and tiers
    - Past booking patterns and preferred destinations
    - Accessibility requirements
    
    For basic preferences (seat type, budget range, hotel rating), 
    use the summary already provided in the context.
    """
    # Reads from filesystem cache for speed
    cache_path = f"data/user_preferences/{traveler_id}.json"
    with open(cache_path) as f:
        return json.load(f)
```

### Tool Binding with bind_tools

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools([load_full_preferences])
```

## Execution Strategy: Manual Orchestrator Control

Chosen for: **Predictable latency, tight integration with TravelContext, full debugging visibility**

```python
# agents/orchestrator.py - plan_trip method
def plan_trip(self, query: str, ctx: TravelContext) -> dict:
    # 1. Load preference SUMMARY (always, fast ~5ms)
    pref_summary = self._get_preference_summary(ctx.traveler_id)
    
    # 2. Bind tool for full details
    tools = [load_full_preferences]
    llm_with_tools = ctx.llm.bind_tools(tools)
    
    # 3. Build prompt with summary + tool availability
    prompt = f"""Plan a trip based on: {query}
    
    Traveler preferences summary: {pref_summary}
    
    If you need detailed preferences (dietary restrictions, loyalty program 
    numbers, past booking history), call the load_full_preferences tool."""
    
    # 4. First LLM call
    response = llm_with_tools.invoke(prompt)
    
    # 5. Handle tool calls if model needs full details
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "load_full_preferences":
                full_prefs = load_full_preferences(tool_call["args"]["traveler_id"])
                # Continue with enriched context
                response = llm_with_tools.invoke([
                    {"role": "user", "content": prompt},
                    response,
                    {"role": "tool", "content": json.dumps(full_prefs), 
                     "tool_call_id": tool_call["id"]}
                ])
    
    # 6. Continue with normal flow (intent parsing, agent execution)
    ...
```

## Files to Modify

| File | Change |
|------|--------|
| `database/models.py` | Add `UserPreferences` model |
| `database/repository.py` | Add `UserPreferencesRepository` with cache sync + summary generation |
| `tools/preference_tools.py` | New file: `load_full_preferences` tool |
| `agents/orchestrator.py` | Add `_get_preference_summary()`, bind tool in `plan_trip()`, handle tool calls |
| `api/routes.py` | Add CRUD endpoints for user preferences |
| `api/schemas.py` | Add preference request/response schemas |
| `data/user_preferences/` | New directory for filesystem cache |

## Configuration

The preference loading mode is configurable via environment variable:

```bash
# Summary-only mode (default, faster)
export PREFERENCE_LOADING_MODE=summary

# Tool binding mode (LLM can call for detailed prefs)
export PREFERENCE_LOADING_MODE=tool_binding
```

| Mode | Behavior | Latency | Use Case |
|------|----------|---------|----------|
| `summary` | Summary always in prompt | ~1.5s | Basic personalization |
| `tool_binding` | LLM can call tool for details | ~1.5-3s | Loyalty numbers, dietary needs |

## Implementation Status: COMPLETED

All implementation tasks have been completed:

1. ✅ Added `UserPreferences` model to `database/models.py` with detailed structure
2. ✅ Created `UserPreferencesRepository` with filesystem cache sync and summary generation in `database/repository.py`
3. ✅ Implemented `load_full_preferences` tool in `tools/preference_tools.py` using `@tool` decorator
4. ✅ Added `_get_preference_summary()` method to Orchestrator
5. ✅ Integrated preference summary loading in `plan_trip()` with `_interpret_query_with_preferences()`
6. ✅ Added preference CRUD endpoints to `api/routes.py`:
   - `GET /api/v1/preferences/{traveler_id}` - Get full preferences
   - `PUT /api/v1/preferences/{traveler_id}` - Create/update preferences (upsert)
   - `DELETE /api/v1/preferences/{traveler_id}` - Delete preferences
   - `GET /api/v1/preferences/{traveler_id}/summary` - Get compact summary
7. ✅ Added preference schemas to `api/schemas.py`
8. ✅ Created `data/user_preferences/` directory for filesystem cache
9. ✅ Created sample preference data for `user_123` and `user_456`

## Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Database + Filesystem cache | DB for source of truth, cache for fast tool reads |
| Preference structure | Detailed | Includes dietary, accessibility, loyalty, past bookings |
| Tool granularity | Single tool (load all) | Simpler for model, one call gets everything |
| Tool approach | Custom @tool with bind_tools | Semantic naming, encapsulated logic, best model understanding |
| Execution | Manual in Orchestrator | Predictable latency, tight TravelContext integration |
| Loading strategy | Summary + tool for details | Best balance of latency (~1.6s) and token efficiency |
