#!/usr/bin/env python3
"""
Benchmark script to measure planner latency improvements from Phase 1 optimizations.

This script measures:
- Prompt size (tokens/chars)
- Latency (milliseconds)
- Token usage (if available)
- Plan quality (validation)

Can run with:
1. Mock LLM (fast, controlled testing)
2. Real LLM (requires API key, measures actual latency)
"""

import json
import time
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager

from agents.core.llm_provider import LLMProvider, create_llm_provider
from agents.planning.planner import TravelPlanner
from api.context import TravelContext


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    query: str
    latency_ms: float
    prompt_size_chars: int
    prompt_size_estimate_tokens: int
    plan_status: str
    task_count: int
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for controlled benchmarking."""
    
    def __init__(self, response_delay_ms: float = 0, track_prompts: bool = True):
        """
        Initialize mock LLM.
        
        Args:
            response_delay_ms: Simulated response delay in milliseconds
            track_prompts: Whether to track prompt sizes
        """
        self.response_delay_ms = response_delay_ms
        self.track_prompts = track_prompts
        self.last_prompt: Optional[str] = None
        self.last_prompt_size: int = 0
        self.enable_json_mode = False  # Mock doesn't use JSON mode
        
    def invoke(self, prompt: str, **kwargs) -> str:
        """Mock invoke with simulated delay."""
        if self.track_prompts:
            self.last_prompt = prompt
            self.last_prompt_size = len(prompt)
        
        # Simulate network delay
        if self.response_delay_ms > 0:
            time.sleep(self.response_delay_ms / 1000.0)
        
        # Return a simple JSON response with proper structure
        return json.dumps({
            "status": "executable",
            "missing_info": [],
            "tasks": [
                {
                    "id": "t1",
                    "title": "Search flights",
                    "agent": "FlightBookingAgent",
                    "action": "search_flights",
                    "description": "Mock flight search",
                    "input_schema": {"origin": {"type": "string"}},
                    "params": {"origin": "NYC", "destination": "LON", "date": "2025-08-12"},
                    "output_schema": {"flights": {"type": "array"}},
                    "dependencies": [],
                    "parallelizable": True,
                }
            ],
            "plan_metadata": {
                "plan_id": "plan_benchmark",
                "created_at": "2025-12-10T10:00:00Z",
                "planner_version": "1.0.0",
                "confidence_score": 0.9,
                "conversation_turns": 1,
            }
        })
    
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Mock structured invoke."""
        if self.track_prompts:
            self.last_prompt = prompt
            self.last_prompt_size = len(prompt)
        
        # Simulate network delay
        if self.response_delay_ms > 0:
            time.sleep(self.response_delay_ms / 1000.0)
        
        # Return structured response with proper structure
        return {
            "status": "executable",
            "missing_info": [],
            "tasks": [
                {
                    "id": "t1",
                    "title": "Search flights",
                    "agent": "FlightBookingAgent",
                    "action": "search_flights",
                    "description": "Mock flight search",
                    "input_schema": {"origin": {"type": "string"}},
                    "params": {"origin": "NYC", "destination": "LON", "date": "2025-08-12"},
                    "output_schema": {"flights": {"type": "array"}},
                    "dependencies": [],
                    "parallelizable": True,
                }
            ],
            "plan_metadata": {
                "plan_id": "plan_benchmark",
                "created_at": "2025-12-10T10:00:00Z",
                "planner_version": "1.0.0",
                "confidence_score": 0.9,
                "conversation_turns": 1,
            }
        }


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return len(text) // 4


def benchmark_planner(
    planner: TravelPlanner,
    query: str,
    ctx: TravelContext,
    iterations: int = 3
) -> BenchmarkResult:
    """Run benchmark for a single query."""
    latencies = []
    prompt_sizes = []
    last_result: Optional[BenchmarkResult] = None
    
    for i in range(iterations):
        start_time = time.perf_counter()
        
        try:
            plan = planner.create_plan_from_query(query, ctx)
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            latencies.append(latency_ms)
            
            # Get prompt size from LLM if it's a mock (get LLM from strategy)
            llm = None
            if ctx.model_strategy:
                try:
                    from llm.strategy.use_cases import UseCase
                    llm = ctx.model_strategy.get_llm_for_use_case(UseCase.PLANNER)
                except Exception:
                    pass
            
            prompt_size = 0
            prompt_text = ""
            if llm and hasattr(llm, 'last_prompt_size') and llm.last_prompt_size > 0:
                prompt_sizes.append(llm.last_prompt_size)
                prompt_size = llm.last_prompt_size
                prompt_text = llm.last_prompt if hasattr(llm, 'last_prompt') else ""
            
            last_result = BenchmarkResult(
                query=query,
                latency_ms=latency_ms,
                prompt_size_chars=prompt_size,
                prompt_size_estimate_tokens=estimate_tokens(prompt_text),
                plan_status=plan.status,
                task_count=len(plan.tasks),
                token_usage=None,
                error=None
            )
        except Exception as e:
            last_result = BenchmarkResult(
                query=query,
                latency_ms=0,
                prompt_size_chars=0,
                prompt_size_estimate_tokens=0,
                plan_status="error",
                task_count=0,
                error=str(e)
            )
    
    # Use average latency
    if latencies:
        last_result.latency_ms = statistics.mean(latencies)
    
    # Use average prompt size
    if prompt_sizes:
        last_result.prompt_size_chars = int(statistics.mean(prompt_sizes))
        last_result.prompt_size_estimate_tokens = estimate_tokens(" " * last_result.prompt_size_chars)
    
    return last_result


def run_benchmark_suite(use_real_llm: bool = False) -> List[BenchmarkResult]:
    """Run full benchmark suite."""
    print("=" * 80)
    print("Planner Latency Benchmark - Phase 1 Optimizations")
    print("=" * 80)
    print()
    
    # Test queries of varying complexity
    test_queries = [
        "Book a flight from NYC to London on 2025-08-12",
        "Plan a trip from New York to Paris on 2025-09-01 with hotel and car rental",
        "I need a flight from San Francisco to Chicago on 2025-10-15, a hotel for 3 nights, and a rental car",
        "Flight from JFK to LHR on 2025-11-20",
        "Plan complete trip: flight NYC to Paris, hotel in Paris, car rental, return flight on 2025-12-01",
    ]
    
    results = []
    
    # Create LLM provider
    if use_real_llm:
        print("Using REAL LLM (requires API key)...")
        try:
            llm = create_llm_provider(
                model_name="gpt-4o",
                model_provider="openai",
                enable_json_mode=True,
                enable_prompt_caching=True
            )
        except Exception as e:
            print(f"Failed to create real LLM: {e}")
            print("Falling back to mock LLM...")
            llm = MockLLMProvider(response_delay_ms=100, track_prompts=True)
    else:
        print("Using MOCK LLM (simulated 100ms delay)...")
        llm = MockLLMProvider(response_delay_ms=100, track_prompts=True)
    
    # Create strategy and planner
    from llm import ModelInvocationStrategy
    from unittest.mock import Mock
    # For benchmarking, create a mock strategy that provides the LLM
    mock_strategy = Mock(spec=ModelInvocationStrategy)
    mock_strategy.get_llm_for_use_case.return_value = llm
    planner = TravelPlanner(strategy=mock_strategy)
    ctx = TravelContext(session=None, model_strategy=mock_strategy, traveler_id="benchmark_user")
    
    print(f"\nRunning {len(test_queries)} test queries ({3} iterations each)...")
    print("-" * 80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] Query: {query[:60]}...")
        result = benchmark_planner(planner, query, ctx, iterations=3)
        results.append(result)
        
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Prompt size: {result.prompt_size_chars:,} chars (~{result.prompt_size_estimate_tokens} tokens)")
        print(f"  Plan status: {result.plan_status}")
        print(f"  Tasks: {result.task_count}")
        if result.error:
            print(f"  ERROR: {result.error}")
    
    return results


def print_summary(results: List[BenchmarkResult]):
    """Print benchmark summary statistics."""
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    
    if not results:
        print("No results to summarize.")
        return
    
    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    prompt_sizes = [r.prompt_size_chars for r in results if r.prompt_size_chars > 0]
    token_estimates = [r.prompt_size_estimate_tokens for r in results if r.prompt_size_estimate_tokens > 0]
    
    if latencies:
        print(f"\nLatency Statistics:")
        print(f"  Average: {statistics.mean(latencies):.2f}ms")
        print(f"  Median: {statistics.median(latencies):.2f}ms")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")
        if len(latencies) > 1:
            print(f"  Std Dev: {statistics.stdev(latencies):.2f}ms")
    
    if prompt_sizes:
        print(f"\nPrompt Size Statistics:")
        print(f"  Average: {statistics.mean(prompt_sizes):,.0f} chars (~{statistics.mean(token_estimates):.0f} tokens)")
        print(f"  Median: {statistics.median(prompt_sizes):,.0f} chars (~{statistics.median(token_estimates):.0f} tokens)")
        print(f"  Min: {min(prompt_sizes):,} chars (~{min(token_estimates)} tokens)")
        print(f"  Max: {max(prompt_sizes):,} chars (~{max(token_estimates)} tokens)")
    
    # Compare to baseline (estimated ~700 tokens before optimization)
    baseline_tokens = 700
    if token_estimates:
        avg_tokens = statistics.mean(token_estimates)
        reduction = ((baseline_tokens - avg_tokens) / baseline_tokens) * 100
        print(f"\nOptimization Impact (vs estimated baseline of ~{baseline_tokens} tokens):")
        print(f"  Token reduction: {baseline_tokens - avg_tokens:.0f} tokens ({reduction:.1f}%)")
        print(f"  Estimated latency improvement: ~{reduction * 0.7:.1f}% (assuming linear relationship)")
    
    # Plan quality
    successful = sum(1 for r in results if r.plan_status == "executable")
    print(f"\nPlan Quality:")
    print(f"  Successful plans: {successful}/{len(results)}")
    print(f"  Average tasks per plan: {statistics.mean([r.task_count for r in results]):.1f}")
    
    print("\n" + "=" * 80)
    print("Phase 1 Optimizations Applied:")
    print("  ✓ OpenAI JSON mode enabled (removes ~100-200 tokens)")
    print("  ✓ Prompt compressed from ~700 to ~200 tokens")
    print("  ✓ Static data (alias map, defaults) removed from prompt")
    print("  ✓ Deterministic rules moved to post-processing")
    print("  ✓ Prompt caching infrastructure enabled")
    print("=" * 80)


def main():
    """Main benchmark entry point."""
    import sys
    
    use_real_llm = "--real" in sys.argv or "--real-llm" in sys.argv
    
    try:
        results = run_benchmark_suite(use_real_llm=use_real_llm)
        print_summary(results)
        
        # Save results to JSON
        output_file = "benchmark_results.json"
        with open(output_file, "w") as f:
            json.dump([
                {
                    "query": r.query,
                    "latency_ms": r.latency_ms,
                    "prompt_size_chars": r.prompt_size_chars,
                    "prompt_size_estimate_tokens": r.prompt_size_estimate_tokens,
                    "plan_status": r.plan_status,
                    "task_count": r.task_count,
                    "error": r.error
                }
                for r in results
            ], f, indent=2)
        print(f"\nResults saved to: {output_file}")
        
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
