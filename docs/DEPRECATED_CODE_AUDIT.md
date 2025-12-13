# Deprecated Methods and Redundant Code Audit

## Summary

This document identifies all deprecated methods, redundant code, and unused components in the travel-agents codebase.

---

## 🔴 Deprecated Methods

### 1. **`get_llm_provider()`** - `api/dependencies.py:106`
**Status**: ⚠️ Deprecated with warning  
**Location**: `api/dependencies.py:105-148`

**Details**:
- Uses legacy environment variables (`LLM_MODEL`, `LLM_PROVIDER`, `LLM_TEMPERATURE`)
- Bypasses centralized `model_strategy.yaml` configuration
- Emits `DeprecationWarning` when called

**Replacement**:
```python
# OLD (deprecated)
llm = get_llm_provider()

# NEW (preferred)
strategy = get_model_strategy()
llm = strategy.get_llm_for_use_case(UseCase.PLANNER)
```

**Still Used By**:
- `get_llm()` dependency (line 156-158) - which is also redundant
- Potentially by old test code

**Recommendation**: Remove after updating all callers to use `ModelInvocationStrategy`

---

### 2. **`get_llm_provider_name()`** - `api/dependencies.py:76`
**Status**: ⚠️ Deprecated (documented)  
**Location**: `api/dependencies.py:76-84`

**Details**:
- Reads `LLM_PROVIDER` environment variable
- Part of legacy LLM provider path

**Replacement**: Use `model_strategy.yaml` configuration

**Still Used By**:
- `get_llm_provider()` (deprecated function)
- `get_expected_api_key_name()` (line 89)

**Recommendation**: Remove when `get_llm_provider()` is removed

---

### 3. **`get_default_model()`** - `api/dependencies.py:93`
**Status**: ⚠️ Deprecated (documented)  
**Location**: `api/dependencies.py:93-102`

**Details**:
- Returns hardcoded default models from `PROVIDER_DEFAULT_MODELS` dict
- Part of legacy LLM provider path

**Replacement**: Use `model_strategy.yaml` configuration

**Still Used By**:
- `get_llm_provider()` (deprecated function)

**Recommendation**: Remove when `get_llm_provider()` is removed

---

### 4. **`run_intent()`** - `agents/orchestration/orchestrator.py:423`
**Status**: ⚠️ Deprecated (documented)  
**Location**: `agents/orchestration/orchestrator.py:423-485`

**Details**:
- Legacy method for non-context-aware execution
- Creates minimal `TravelContext` for backward compatibility
- Used primarily in tests

**Replacement**:
```python
# OLD (deprecated)
result = orchestrator.run_intent(intent)

# NEW (preferred)
# For NL queries:
plan = planning_service.plan_trip(query, ctx)

# For ExecutionPlan objects:
result = orchestrator.execute_plan(plan, ctx)
```

**Still Used By**:
- `tests/test_integration/test_flows.py` (lines 37, 119)
- `tests/test_core/test_orchestrator.py` (line 55)
- `README.md` examples (line 916)

**Recommendation**: Update tests to use `PlanningService.plan_trip()` or `Orchestrator.execute_plan()`

---

### 5. **`create_plan()`** - `agents/planning/planner.py:65`
**Status**: ⚠️ Deprecated (documented)  
**Location**: `agents/planning/planner.py:65-73`

**Details**:
- Wrapper around `DeterministicPlanner.create_plan_from_intent()`
- Kept for backward compatibility
- **BUG**: Has duplicate docstring (lines 74-79 are unreachable dead code)

**Replacement**:
```python
# OLD (deprecated)
plan = planner.create_plan(intent, traveler_id)

# NEW (preferred)
plan = planner.deterministic_planner.create_plan_from_intent(intent, traveler_id)
# Or use:
plan = planner.create_plan_from_query(query, ctx)  # For NL queries
```

**Still Used By**:
- `Orchestrator.run_intent()` (deprecated method, line 436)

**Recommendation**: Remove after updating `run_intent()` or remove both together

---

### 6. **`execute()` Methods in Agents** - Legacy Compatibility
**Status**: ⚠️ Legacy compatibility methods  
**Locations**:
- `agents/domain/flight_booking_agent.py:194`
- `agents/domain/hotel_booking_agent.py:192`
- `agents/domain/car_rental_agent.py:122`
- `agents/domain/itinerary_agent.py:291`
- `agents/domain/payment_agent.py:79`
- `agents/core/base_agent.py:37` (base implementation)

**Details**:
- Generic `execute(task, params, ctx)` method for backward compatibility
- Agents now have specific methods (e.g., `search_flights()`, `book_hotel()`)
- `execute()` routes to specific methods or uses LLM routing as fallback

**Replacement**: Use specific agent methods directly:
```python
# OLD (deprecated)
agent.execute("search_flights", {"from": "BLR", "to": "DXB", "date": "2026-04-01"})

# NEW (preferred)
agent.search_flights(ctx, origin="BLR", destination="DXB", date="2026-04-01")
```

**Still Used By**:
- `Orchestrator.execute_plan()` (line 175) - for executing plan actions
- `Orchestrator.run_intent()` (line 485) - deprecated method
- Various test files

**Recommendation**: Keep for now as `execute_plan()` uses it, but consider refactoring to direct method calls

---

## 🟡 Deprecated Parameters

### 1. **`llm` Parameter in `TravelContext`** - `api/context.py:34`
**Status**: ⚠️ Deprecated (documented)  
**Location**: `api/context.py:34-35`

**Details**:
- Marked as deprecated in docstring
- Usage should move to `model_strategy`

**Replacement**: Use `ctx.model_strategy` instead of `ctx.llm`

**Still Used By**:
- `get_context()` dependency still passes `llm` parameter (line 192)
- Various agents may check `ctx.has_llm` property

**Recommendation**: Remove after ensuring all code uses `model_strategy`

---

### 2. **Default Parameters in `Orchestrator.__init__`** - `agents/orchestration/orchestrator.py:35`
**Status**: ⚠️ Fallback only  
**Location**: `agents/orchestration/orchestrator.py:35`

**Details**:
- `model_name: str = "gpt-4o"` and `model_provider: str = "openai"`
- Only used as fallback when both `llm` and `strategy` are `None` (lines 50-59)

**Replacement**: Always pass `strategy` parameter

**Still Used By**: None (production code always passes `strategy`)

**Recommendation**: Remove default parameters and require `strategy` parameter

---

## 🟠 Deprecated Environment Variables

### 1. **`LLM_MODEL`**
**Status**: ⚠️ Deprecated  
**Documentation**: `README.md:808`

**Details**:
- Used by legacy `get_llm_provider()` function
- Bypasses centralized configuration

**Replacement**: Configure in `llm/config/model_strategy.yaml`

---

### 2. **`LLM_PROVIDER`**
**Status**: ⚠️ Deprecated  
**Documentation**: `README.md:809`

**Details**:
- Used by legacy `get_llm_provider()` function
- Bypasses centralized configuration

**Replacement**: Configure in `llm/config/model_strategy.yaml`

---

### 3. **`LLM_TEMPERATURE`**
**Status**: ⚠️ Deprecated  
**Documentation**: `README.md:810`

**Details**:
- Used by legacy `get_llm_provider()` function
- Temperature is configured per use case in `model_strategy.yaml`

**Replacement**: Configure in `llm/config/model_strategy.yaml` per use case

---

## 🔵 Redundant/Unused Code

### 1. **`routes.py.old`** - Old Routes File
**Status**: ❌ Unused file  
**Location**: `api/routes.py.old`

**Details**:
- Old version of routes file
- Not imported or referenced anywhere
- Contains 767 lines of unused code

**Recommendation**: **DELETE** - This file serves no purpose

---

### 2. **`SimpleMemory` and `create_memory()`** - Unused Memory Implementation
**Status**: ❌ Placeholder, not actively used  
**Location**: `agents/core/memory.py`

**Details**:
- Simple placeholder implementation
- Comment says "not actively used in current implementation"
- Always passed as `None` to `Orchestrator` (see `api/dependencies.py:220, 268`)

**Still Exported By**:
- `agents/__init__.py` (lines 15, 54-55)
- `agents/core/__init__.py` (lines 10, 19-20)

**Recommendation**: 
- Remove if not planning to use memory
- Or implement properly if memory is needed

---

### 3. **`get_llm()` Dependency** - Redundant Wrapper
**Status**: ❌ Redundant  
**Location**: `api/dependencies.py:156-158`

**Details**:
- Simply wraps deprecated `get_llm_provider()`
- Adds no value

**Still Used By**:
- `get_context()` dependency (line 168) - but `llm` is deprecated in `TravelContext`

**Recommendation**: Remove and update `get_context()` to not use it

---

### 4. **Duplicate Docstring in `create_plan()`** - Dead Code
**Status**: ❌ Dead code  
**Location**: `agents/planning/planner.py:74-79`

**Details**:
- Unreachable docstring after return statement (line 73)
- Lines 74-79 are never executed

**Recommendation**: **DELETE** - Remove lines 74-79

---

### 5. **`PROVIDER_DEFAULT_MODELS` Dictionary** - Legacy Config
**Status**: ⚠️ Part of deprecated path  
**Location**: `api/dependencies.py:67-73`

**Details**:
- Hardcoded default models per provider
- Only used by deprecated `get_default_model()` function

**Recommendation**: Remove when `get_llm_provider()` is removed

---

## 📊 Usage Analysis

### Production Code Paths ✅
1. **API Routes** → Use `get_model_strategy()` → Loads from `model_strategy.yaml` ✅
2. **Orchestrator** → Initialized with `strategy` parameter → Uses `model_strategy.yaml` ✅
3. **TravelPlanner** → Initialized with `strategy` parameter → Uses `model_strategy.yaml` ✅
4. **All Agents** → Receive `ctx` with `model_strategy` → Use `model_strategy.yaml` ✅
5. **Health Service** → Uses `ModelInvocationStrategy` (already updated) ✅

### Legacy Code Paths ⚠️
1. **Tests** → Some use `run_intent()` (deprecated)
2. **README Examples** → Show deprecated `run_intent()` usage
3. **`get_context()`** → Still passes deprecated `llm` parameter

---

## 🎯 Recommendations by Priority

### Priority 1: Remove Dead/Unused Code (No Breaking Changes)
1. ✅ **DELETE** `api/routes.py.old` - Unused file
2. ✅ **DELETE** Duplicate docstring in `planner.py:74-79` - Dead code
3. ✅ **REMOVE** `get_llm()` dependency - Redundant wrapper
4. ✅ **UPDATE** `get_context()` to not use `get_llm()` dependency

### Priority 2: Clean Up Deprecated Methods (Update Tests)
1. ⚠️ **UPDATE** Tests to use `PlanningService.plan_trip()` instead of `run_intent()`
2. ⚠️ **UPDATE** README examples to show preferred methods
3. ⚠️ **REMOVE** `run_intent()` after tests updated
4. ⚠️ **REMOVE** `create_plan()` wrapper after `run_intent()` removed

### Priority 3: Remove Legacy LLM Provider Path (Breaking Changes)
1. 🔴 **REMOVE** `get_llm_provider()` function
2. 🔴 **REMOVE** `get_llm_provider_name()` function
3. 🔴 **REMOVE** `get_default_model()` function
4. 🔴 **REMOVE** `PROVIDER_DEFAULT_MODELS` dictionary
5. 🔴 **REMOVE** `llm` parameter from `TravelContext`
6. 🔴 **REMOVE** Default `model_name`/`model_provider` from `Orchestrator.__init__`

### Priority 4: Memory Implementation Decision
1. 🤔 **DECIDE**: Remove `SimpleMemory`/`create_memory()` if not needed
2. 🤔 **OR**: Implement proper memory if needed for conversation history

---

## 📝 Notes

- Health Service was already updated to use `ModelInvocationStrategy` ✅
- Most production code paths use the new `model_strategy.yaml` approach ✅
- Legacy paths exist primarily for backward compatibility and tests
- Some deprecated methods are still used by `execute_plan()` (which is the preferred path)

---

## 🔗 Related Documents

- `docs/MODEL_CONFIG_OVERRIDES.md` - Detailed analysis of model configuration overrides
- `docs/PROMPT_AUDIT.md` - Audit of hardcoded prompts
- `README.md:808-810` - Documentation of deprecated environment variables
