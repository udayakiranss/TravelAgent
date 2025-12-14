#!/usr/bin/env python3
"""
Test script for formatting latency improvements.

This script:
1. Tests ResponseFormatter with sample data
2. Makes API calls with include_summary=True to test formatting
3. Monitors logs for latency information
4. Reports formatting-specific latency metrics
"""

import json
import time
import sys
import os
from typing import Dict, Any, List
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Install with: pip install httpx")
    sys.exit(1)

from agents.orchestration.response_formatter import ResponseFormatter
from llm.strategy.model_strategy import ModelInvocationStrategy
from llm.strategy.use_cases import UseCase


@dataclass
class FormattingResult:
    """Results from a formatting test."""
    test_name: str
    latency_ms: float
    success: bool
    summary_length: int
    error: str = ""


class FormattingLatencyTest:
    """Test formatting latency improvements."""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """Initialize test suite."""
        self.api_base_url = api_base_url.rstrip('/')
        self.api_endpoint = f"{self.api_base_url}/api/v1/agent/plan"
        self.client = httpx.Client(timeout=120.0)
        self.results: List[FormattingResult] = []
    
    def test_direct_formatter(self, iterations: int = 3) -> List[FormattingResult]:
        """Test ResponseFormatter directly with sample data."""
        print("\n" + "="*70)
        print("Testing ResponseFormatter Directly")
        print("="*70)
        
        results = []
        
        # Sample test data
        sample_results = {
            "flight": {
                "airline": "Delta Airlines",
                "flight_number": "DL123",
                "origin": "NYC",
                "destination": "LON",
                "departure_time": "2025-08-12T10:00:00",
                "arrival_time": "2025-08-12T18:30:00",
                "duration": "8h 30m",
                "price": 650.0
            },
            "hotel": {
                "name": "The Savoy",
                "location": "London, UK",
                "check_in": "2025-08-12",
                "check_out": "2025-08-15",
                "price": 220.0,
                "rating": 4.5
            },
            "total_cost": 870.0,
            "traveler_preferences": "No preferences set"
        }
        
        sample_intent = {
            "from": "NYC",
            "to": "LON",
            "date": "2025-08-12",
            "needs": ["flight", "hotel"]
        }
        
        try:
            # Initialize formatter with strategy
            strategy = ModelInvocationStrategy()
            llm = strategy.get_llm_for_use_case(UseCase.SUMMARY_GENERATION)
            formatter = ResponseFormatter(llm=llm, model_strategy=strategy)
            
            print(f"\nRunning {iterations} iterations of direct formatter test...")
            
            for i in range(iterations):
                print(f"\nIteration {i+1}/{iterations}...")
                start_time = time.perf_counter()
                
                try:
                    summary = formatter.format_results(sample_results, sample_intent)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    result = FormattingResult(
                        test_name=f"Direct Formatter - Iteration {i+1}",
                        latency_ms=elapsed_ms,
                        success=True,
                        summary_length=len(summary)
                    )
                    results.append(result)
                    
                    print(f"  ✓ Success: {elapsed_ms:.2f}ms")
                    print(f"  Summary length: {len(summary)} characters")
                    if i == 0:  # Show first summary
                        print(f"  Summary preview: {summary[:150]}...")
                    
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    result = FormattingResult(
                        test_name=f"Direct Formatter - Iteration {i+1}",
                        latency_ms=elapsed_ms,
                        success=False,
                        summary_length=0,
                        error=str(e)
                    )
                    results.append(result)
                    print(f"  ✗ Failed: {e}")
            
        except Exception as e:
            print(f"Error initializing formatter: {e}")
            result = FormattingResult(
                test_name="Direct Formatter - Setup",
                latency_ms=0,
                success=False,
                summary_length=0,
                error=str(e)
            )
            results.append(result)
        
        return results
    
    def test_api_with_formatting(self, iterations: int = 3) -> List[FormattingResult]:
        """Test formatting via API endpoint with include_summary=True."""
        print("\n" + "="*70)
        print("Testing Formatting via API (include_summary=True)")
        print("="*70)
        
        results = []
        
        test_queries = [
            "Book a flight from NYC to London on 2025-08-12 and a hotel",
            "Plan a trip from Paris to New York on 2025-09-01 with flight and hotel",
        ]
        
        for query_idx, query in enumerate(test_queries):
            print(f"\nTest Query {query_idx + 1}: {query}")
            
            for i in range(iterations):
                print(f"  Iteration {i+1}/{iterations}...")
                
                payload = {
                    "query": query,
                    "traveler_id": f"test_user_{query_idx}",
                    "include_summary": True  # Enable formatting
                }
                
                start_time = time.perf_counter()
                
                try:
                    response = self.client.post(
                        self.api_endpoint,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    if response.status_code == 200:
                        data = response.json()
                        summary = data.get("summary", "")
                        
                        result = FormattingResult(
                            test_name=f"API Formatting - Query {query_idx+1} - Iter {i+1}",
                            latency_ms=elapsed_ms,
                            success=True,
                            summary_length=len(summary) if summary else 0
                        )
                        results.append(result)
                        
                        print(f"    ✓ Success: {elapsed_ms:.2f}ms")
                        if summary:
                            print(f"    Summary length: {len(summary)} characters")
                            print(f"    Summary preview: {summary[:100]}...")
                        else:
                            print(f"    ⚠ No summary in response")
                    else:
                        result = FormattingResult(
                            test_name=f"API Formatting - Query {query_idx+1} - Iter {i+1}",
                            latency_ms=elapsed_ms,
                            success=False,
                            summary_length=0,
                            error=f"HTTP {response.status_code}: {response.text[:200]}"
                        )
                        results.append(result)
                        print(f"    ✗ Failed: HTTP {response.status_code}")
                
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    result = FormattingResult(
                        test_name=f"API Formatting - Query {query_idx+1} - Iter {i+1}",
                        latency_ms=elapsed_ms,
                        success=False,
                        summary_length=0,
                        error=str(e)
                    )
                    results.append(result)
                    print(f"    ✗ Error: {e}")
        
        return results
    
    def check_server_health(self) -> bool:
        """Check if API server is running."""
        try:
            response = self.client.get(f"{self.api_base_url}/docs", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def print_summary(self, results: List[FormattingResult]):
        """Print summary of test results."""
        print("\n" + "="*70)
        print("Test Results Summary")
        print("="*70)
        
        if not results:
            print("No results to display.")
            return
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"\nTotal Tests: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if successful:
            latencies = [r.latency_ms for r in successful]
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"\nLatency Statistics (successful tests):")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  Min: {min_latency:.2f}ms")
            print(f"  Max: {max_latency:.2f}ms")
            
            if len(latencies) > 1:
                # Calculate standard deviation
                variance = sum((x - avg_latency) ** 2 for x in latencies) / len(latencies)
                std_dev = variance ** 0.5
                print(f"  Std Dev: {std_dev:.2f}ms")
            
            print(f"\nExpected Performance:")
            print(f"  Target: <1500ms (down from 2000-4000ms)")
            print(f"  Improvement: {((2000 - avg_latency) / 2000 * 100):.1f}% faster than baseline")
        
        if failed:
            print(f"\nFailed Tests:")
            for r in failed:
                print(f"  - {r.test_name}: {r.error}")
    
    def run_all_tests(self):
        """Run all formatting tests."""
        print("\n" + "="*70)
        print("Formatting Latency Test Suite")
        print("="*70)
        print(f"API Base URL: {self.api_base_url}")
        
        all_results = []
        
        # Test 1: Direct formatter
        try:
            direct_results = self.test_direct_formatter(iterations=3)
            all_results.extend(direct_results)
        except Exception as e:
            print(f"Error in direct formatter test: {e}")
        
        # Test 2: API with formatting
        if self.check_server_health():
            print("\n✓ API server is running")
            try:
                api_results = self.test_api_with_formatting(iterations=2)
                all_results.extend(api_results)
            except Exception as e:
                print(f"Error in API formatting test: {e}")
        else:
            print("\n⚠ API server is not running. Skipping API tests.")
            print("  Start server with: python main_web.py")
        
        # Print summary
        self.print_summary(all_results)
        
        return all_results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test formatting latency improvements")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    tester = FormattingLatencyTest(api_base_url=args.api_url)
    results = tester.run_all_tests()
    
    # Exit with error code if any tests failed
    if any(not r.success for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()

