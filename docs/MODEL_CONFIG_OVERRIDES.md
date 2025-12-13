# Model Configuration Overrides Audit

## Summary

This document identifies all places where model configuration can be overridden outside of `llm/config/model_strategy.yaml`.

## Primary Configuration Source ✅

**`llm/config/model_strategy.yaml`** - This is the **single source of truth** for model configuration in production code. All use cases (planner, intent_parsing, summary_generation, task_routing, modification) are configured here.

## Override Locations Found ⚠️

### 1. **`api/dependencies.py`** - Legacy LLM Provider Path ⚠️ **HIGH PRIORITY**

**Location**: Lines 64-115

**Issue**: This file provides a legacy path for LLM provider creation that bypasses `model_strategy.yaml`.

**Details**:
- `PROVIDER_DEFAULT_MODELS` dictionary (lines 65-71) - Hardcoded default models per provider
- `get_llm_provider()` function (lines 91-115) - Creates LLM providers using:
  - Environment variable `LLM_PROVIDER` (defaults to 'openai')
  - Environment variable `LLM_MODEL` (defaults to provider-specific model from `PROVIDER_DEFAULT_MODELS`)
  - Environment variable `LLM_TEMPERATURE` (defaults to '0')

**Impact**: 
- This function is used by `get_llm()` dependency (line 123-125)
- The `llm` parameter is passed to `TravelContext` (line 159) but marked as deprecated
- This creates LLM providers that are **not** configured via `model_strategy.yaml`

**Usage**:
- Used in `get_context()` dependency (line 135) - but `model_strategy` is also provided (line 136)
- Used in `get_health_service()` dependency (line 297) - for health checks

**Recommendation**: 
- Mark `get_llm_provider()` as deprecated
- Update `get_health_service()` to use `ModelInvocationStrategy` instead
- Consider removing the legacy `llm` parameter from `TravelContext` once all code paths use `model_strategy`

### 2. **`agents/orchestration/orchestrator.py`** - Default Parameters ⚠️ **MEDIUM PRIORITY**

**Location**: Line 35

**Issue**: Default parameters `model_name: str = "gpt-4o"` and `model_provider: str = "openai"` in `__init__`

**Details**:
- Only used as fallback when **both** `llm` and `strategy` are `None` (lines 50-59)
- This is a legacy fallback path for backward compatibility

**Impact**: 
- Low - Only used if Orchestrator is initialized without both `llm` and `strategy`
- Production code (via `api/dependencies.py`) always passes `strategy` (line 187)

**Recommendation**:
- Keep for backward compatibility but document as deprecated
- Consider raising an error if both `llm` and `strategy` are None in production

### 3. **`agents/core/llm_provider.py`** - Factory Function Defaults ⚠️ **LOW PRIORITY**

**Location**: Line 55

**Issue**: `create_llm_provider()` has default parameters `model_name: str = "gpt-4o"` and `model_provider: str = "openai"`

**Details**:
- This is a factory function with defaults
- Typically called with explicit values from `model_strategy.yaml` via `ProviderFactory`
- Defaults are only used if function is called directly without parameters

**Impact**: 
- Very Low - Function is typically called with explicit values
- Defaults are only a safety net

**Recommendation**:
- Keep defaults for safety, but document that they should not be used in production
- All production code should use `ModelInvocationStrategy` which calls `ProviderFactory` with explicit config

### 4. **Environment Variables** - Deprecated but Functional ⚠️ **MEDIUM PRIORITY**

**Location**: `api/dependencies.py` lines 76, 99, 105

**Environment Variables**:
- `LLM_PROVIDER` - Overrides provider selection (defaults to 'openai')
- `LLM_MODEL` - Overrides model selection (defaults to provider-specific model)
- `LLM_TEMPERATURE` - Overrides temperature (defaults to '0')

**Impact**:
- These are used by the legacy `get_llm_provider()` function
- They bypass `model_strategy.yaml` configuration
- README.md marks them as deprecated (line 808-809)

**Recommendation**:
- Document that these are deprecated and should not be used
- Consider removing support for these in a future version
- All model configuration should come from `model_strategy.yaml`

### 5. **Benchmark/Test Files** - Not Production Code ✅ **NO ACTION NEEDED**

**Locations**:
- `benchmark_planner_latency.py` (line 220) - Hardcoded `model_name="gpt-4o"` for benchmarking
- Various test files - Hardcoded model names for testing

**Impact**: None - These are not production code paths

**Recommendation**: No action needed - test/benchmark code can use hardcoded values

## Current State Analysis

### Production Code Paths ✅

1. **API Routes** → Use `get_model_strategy()` → Loads from `model_strategy.yaml` ✅
2. **Orchestrator** → Initialized with `strategy` parameter → Uses `model_strategy.yaml` ✅
3. **TravelPlanner** → Initialized with `strategy` parameter → Uses `model_strategy.yaml` ✅
4. **All Agents** → Receive `ctx` with `model_strategy` → Use `model_strategy.yaml` ✅

### Legacy Code Paths ⚠️

1. **Health Service** → Uses `get_llm()` → May use legacy `get_llm_provider()` ⚠️
2. **Direct Orchestrator initialization** → May use default `model_name`/`model_provider` if no strategy ⚠️
3. **Environment variables** → Can override via `LLM_MODEL`/`LLM_PROVIDER` ⚠️

## Recommendations

### Priority 1: Update Health Service
- Update `get_health_service()` to use `ModelInvocationStrategy` instead of legacy `get_llm()`
- This ensures health checks use the same model configuration as production code

### Priority 2: Document Deprecation
- Add deprecation warnings to `get_llm_provider()` function
- Document that `LLM_MODEL` and `LLM_PROVIDER` environment variables are deprecated
- Update README to clearly state that `model_strategy.yaml` is the only source of truth

### Priority 3: Remove Legacy Paths (Future)
- Consider removing `get_llm_provider()` in a future version
- Remove `llm` parameter from `TravelContext` (already marked as deprecated)
- Remove support for `LLM_MODEL` and `LLM_PROVIDER` environment variables

## Conclusion

**Current State**: The system has a **primary path** (via `model_strategy.yaml`) that is used in all production code, but there are **legacy fallback paths** that can override configuration.

**Recommendation**: The legacy paths should be:
1. Documented as deprecated
2. Updated to use `ModelInvocationStrategy` where possible
3. Removed in a future version

**Design Compliance**: Production code paths are compliant with the centralized configuration design. Legacy paths exist for backward compatibility but should be phased out.
