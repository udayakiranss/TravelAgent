#!/usr/bin/env python3
"""
API Benchmark Script - Measures actual API call latency for plan trip endpoint.

This script:
1. Makes real HTTP requests to /api/v1/agent/plan
2. Measures end-to-end latency (including network overhead)
3. Compares with direct planner benchmarks
4. Can optionally start the server if not running

Usage:
    python3 benchmark_api_latency.py                    # Test against running server
    python3 benchmark_api_latency.py --start-server     # Start server and test
    python3 benchmark_api_latency.py --port 8001        # Use different port
"""

import json
import time
import statistics
import sys
import subprocess
import signal
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Install with: pip install httpx")
    sys.exit(1)


@dataclass
class APIResult:
    """Results from a single API call."""
    query: str
    latency_ms: float
    status_code: int
    response_size: int
    plan_status: Optional[str] = None
    task_count: Optional[int] = None
    error: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


class APIBenchmark:
    """Benchmark the plan trip API endpoint."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 120.0):
        """
        Initialize API benchmark.
        
        Args:
            base_url: Base URL of the API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.endpoint = f"{self.base_url}/api/v1/agent/plan"
        self.client = httpx.Client(timeout=timeout)
    
    def check_server_health(self) -> bool:
        """Check if the API server is running."""
        try:
            response = self.client.get(f"{self.base_url}/docs", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def plan_trip(self, query: str, traveler_id: str = "benchmark_user", iterations: int = 3) -> APIResult:
        """
        Make API call to plan trip endpoint and measure latency.
        
        Args:
            query: Natural language query
            traveler_id: Traveler ID for the request
            iterations: Number of iterations to average
        
        Returns:
            APIResult with averaged latency
        """
        latencies = []
        last_result: Optional[APIResult] = None
        
        for i in range(iterations):
            payload = {
                "query": query,
                "traveler_id": traveler_id,
                "include_summary": False  # Skip summary to focus on planning latency
            }
            
            start_time = time.perf_counter()
            
            try:
                response = self.client.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                latencies.append(latency_ms)
                
                response_data = None
                plan_status = None
                task_count = None
                error = None
                
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        # Extract plan status if available
                        if isinstance(response_data, dict):
                            # The response might have itinerary data
                            plan_status = "success"
                            if "itinerary_id" in response_data:
                                plan_status = "executable"
                    except Exception as e:
                        error = f"Failed to parse JSON: {e}"
                else:
                    try:
                        error_data = response.json()
                        error = error_data.get("detail", {}).get("message", f"HTTP {response.status_code}")
                    except:
                        error = f"HTTP {response.status_code}: {response.text[:100]}"
                
                last_result = APIResult(
                    query=query,
                    latency_ms=latency_ms,
                    status_code=response.status_code,
                    response_size=len(response.content),
                    plan_status=plan_status,
                    task_count=task_count,
                    error=error,
                    response_data=response_data
                )
                
            except httpx.TimeoutException:
                last_result = APIResult(
                    query=query,
                    latency_ms=self.timeout * 1000,
                    status_code=0,
                    response_size=0,
                    error=f"Request timeout after {self.timeout}s"
                )
            except Exception as e:
                last_result = APIResult(
                    query=query,
                    latency_ms=0,
                    status_code=0,
                    response_size=0,
                    error=str(e)
                )
        
        # Use average latency
        if latencies:
            last_result.latency_ms = statistics.mean(latencies)
        
        return last_result
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()


def start_server(port: int = 8000) -> Optional[subprocess.Popen]:
    """Start the FastAPI server in the background."""
    print(f"Starting server on port {port}...")
    
    # Change to the project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main_web:app", "--port", str(port), "--host", "127.0.0.1"],
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        # Wait a bit for server to start
        print("Waiting for server to start...")
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print(f"✓ Server started (PID: {process.pid})")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"✗ Server failed to start:")
            print(stderr.decode() if stderr else stdout.decode())
            return None
            
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return None


def stop_server(process: subprocess.Popen):
    """Stop the server process."""
    if process:
        print(f"\nStopping server (PID: {process.pid})...")
        try:
            if hasattr(os, 'setsid'):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=5)
            print("✓ Server stopped")
        except Exception as e:
            print(f"Warning: Error stopping server: {e}")
            try:
                process.kill()
            except:
                pass


def run_api_benchmark(base_url: str = "http://localhost:8000", start_server_flag: bool = False, port: int = 8000):
    """Run the full API benchmark suite."""
    print("=" * 80)
    print("API Latency Benchmark - Plan Trip Endpoint")
    print("=" * 80)
    print()
    
    server_process = None
    
    # Adjust base_url if port is different
    if port != 8000:
        base_url = f"http://localhost:{port}"
    
    # Start server if requested
    if start_server_flag:
        server_process = start_server(port)
        if not server_process:
            print("Failed to start server. Exiting.")
            return
        base_url = f"http://localhost:{port}"
    
    # Test queries
    test_queries = [
        "Book a flight from NYC to London on 2025-08-12",
        "Plan a trip from New York to Paris on 2025-09-01 with hotel and car rental",
        "I need a flight from San Francisco to Chicago on 2025-10-15, a hotel for 3 nights, and a rental car",
        "Flight from JFK to LHR on 2025-11-20",
        "Plan complete trip: flight NYC to Paris, hotel in Paris, car rental, return flight on 2025-12-01",
    ]
    
    benchmark = APIBenchmark(base_url=base_url, timeout=120.0)
    
    # Check if server is running
    print(f"Checking server at {base_url}...")
    if not benchmark.check_server_health():
        print(f"✗ Server not responding at {base_url}")
        print("  Make sure the server is running:")
        print(f"    python3 -m uvicorn main_web:app --reload --port {port}")
        print("  Or use --start-server flag to start it automatically")
        benchmark.close()
        if server_process:
            stop_server(server_process)
        return
    
    print(f"✓ Server is running at {base_url}")
    print(f"\nRunning {len(test_queries)} test queries ({3} iterations each)...")
    print("-" * 80)
    
    results = []
    
    try:
        for i, query in enumerate(test_queries, 1):
            print(f"\n[{i}/{len(test_queries)}] Query: {query[:60]}...")
            result = benchmark.plan_trip(query, iterations=3)
            results.append(result)
            
            print(f"  Status: {result.status_code}")
            print(f"  Latency: {result.latency_ms:.2f}ms")
            print(f"  Response size: {result.response_size:,} bytes")
            if result.plan_status:
                print(f"  Plan status: {result.plan_status}")
            if result.error:
                print(f"  ERROR: {result.error}")
    
    finally:
        benchmark.close()
        if server_process:
            stop_server(server_process)
    
    # Print summary
    print_summary(results)
    
    # Save results
    output_file = "benchmark_api_results.json"
    with open(output_file, "w") as f:
        json.dump([
            {
                "query": r.query,
                "latency_ms": r.latency_ms,
                "status_code": r.status_code,
                "response_size": r.response_size,
                "plan_status": r.plan_status,
                "task_count": r.task_count,
                "error": r.error
            }
            for r in results
        ], f, indent=2)
    print(f"\nResults saved to: {output_file}")


def print_summary(results: List[APIResult]):
    """Print benchmark summary statistics."""
    print("\n" + "=" * 80)
    print("API BENCHMARK SUMMARY")
    print("=" * 80)
    
    if not results:
        print("No results to summarize.")
        return
    
    successful = [r for r in results if r.status_code == 200]
    failed = [r for r in results if r.status_code != 200]
    
    if successful:
        latencies = [r.latency_ms for r in successful]
        response_sizes = [r.response_size for r in successful]
        
        print(f"\nSuccessful Requests: {len(successful)}/{len(results)}")
        print(f"\nLatency Statistics (successful requests):")
        print(f"  Average: {statistics.mean(latencies):.2f}ms")
        print(f"  Median: {statistics.median(latencies):.2f}ms")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")
        if len(latencies) > 1:
            print(f"  Std Dev: {statistics.stdev(latencies):.2f}ms")
        
        print(f"\nResponse Size Statistics:")
        print(f"  Average: {statistics.mean(response_sizes):,.0f} bytes")
        print(f"  Median: {statistics.median(response_sizes):,.0f} bytes")
        print(f"  Min: {min(response_sizes):,} bytes")
        print(f"  Max: {max(response_sizes):,} bytes")
        
        # Compare with estimated baseline (7-8 seconds = 7000-8000ms)
        baseline_ms = 7500
        avg_latency = statistics.mean(latencies)
        improvement = ((baseline_ms - avg_latency) / baseline_ms) * 100
        
        print(f"\nPerformance Comparison (vs estimated baseline of ~{baseline_ms}ms):")
        print(f"  Latency reduction: {baseline_ms - avg_latency:.0f}ms ({improvement:.1f}%)")
        print(f"  Current average: {avg_latency:.2f}ms")
        print(f"  Target: <500ms")
        if avg_latency < 500:
            print(f"  ✓ Target achieved!")
        else:
            print(f"  ⚠ Still above target (need {avg_latency - 500:.0f}ms more reduction)")
    
    if failed:
        print(f"\nFailed Requests: {len(failed)}")
        for r in failed:
            print(f"  - {r.query[:50]}... → {r.error or f'HTTP {r.status_code}'}")
    
    print("\n" + "=" * 80)
    print("Note: API latency includes:")
    print("  - Network overhead")
    print("  - FastAPI request processing")
    print("  - LLM call latency (if LLM available)")
    print("  - Plan execution (if enabled)")
    print("  - Response serialization")
    print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark the plan trip API endpoint")
    parser.add_argument("--start-server", action="store_true", help="Start the server automatically")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--base-url", type=str, default=None, help="Base URL of the API server")
    
    args = parser.parse_args()
    
    base_url = args.base_url or f"http://localhost:{args.port}"
    
    try:
        run_api_benchmark(
            base_url=base_url,
            start_server_flag=args.start_server,
            port=args.port
        )
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
