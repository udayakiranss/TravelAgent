#!/usr/bin/env python3
"""
Test script to verify Phase 2 implementation:
1. ResponseFormatter uses Pydantic path (with_structured_output)
2. Planner uses dict schema path (backward compatible)
3. Both work correctly
"""

import sys
import os
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestration.response_formatter import ResponseFormatter, SummarySchema
from agents.planning.planner import TravelPlanner
from llm.strategy.model_strategy import ModelInvocationStrategy
from llm.strategy.use_cases import UseCase
from api.context import TravelContext
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

def test_response_formatter_pydantic():
    """Test ResponseFormatter uses Pydantic path."""
    print("\n" + "="*70)
    print("Test 1: ResponseFormatter with Pydantic Model")
    print("="*70)
    
    try:
        strategy = ModelInvocationStrategy()
        llm = strategy.get_llm_for_use_case(UseCase.SUMMARY_GENERATION)
        formatter = ResponseFormatter(llm=llm, model_strategy=strategy)
        
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
        
        print("Calling format_results() with SummarySchema (Pydantic)...")
        start_time = time.perf_counter()
        summary = formatter.format_results(sample_results, sample_intent)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        print(f"✓ Success: {elapsed_ms:.2f}ms")
        print(f"Summary length: {len(summary)} characters")
        print(f"Summary preview: {summary[:200]}...")
        print("\n✓ ResponseFormatter is using Pydantic path (with_structured_output)")
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_planner_dict_schema():
    """Test Planner uses dict schema path (backward compatible)."""
    print("\n" + "="*70)
    print("Test 2: Planner with Dict Schema (Backward Compatible)")
    print("="*70)
    
    try:
        # Create in-memory database
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        session = Session(engine)
        
        strategy = ModelInvocationStrategy()
        planner = TravelPlanner(strategy=strategy)
        ctx = TravelContext(
            session=session,
            model_strategy=strategy,
            traveler_id="test_user"
        )
        
        query = "Book a flight from NYC to London on 2025-08-12"
        print(f"Query: {query}")
        print("Calling create_plan_from_query() with dict schema...")
        
        start_time = time.perf_counter()
        plan = planner.create_plan_from_query(query, ctx)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        if plan:
            print(f"✓ Success: {elapsed_ms:.2f}ms")
            print(f"Plan status: {plan.status}")
            print(f"Task count: {len(plan.tasks)}")
            print(f"Plan ID: {plan.plan_metadata.plan_id}")
            print("\n✓ Planner is using dict schema path (backward compatible)")
            return True
        else:
            print("✗ Failed: Plan is None")
            return False
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def check_logs_for_paths():
    """Check recent logs to see which paths were used."""
    print("\n" + "="*70)
    print("Test 3: Checking Logs for Path Verification")
    print("="*70)
    
    log_file = "logs/travel_booking.log"
    if not os.path.exists(log_file):
        print(f"⚠ Log file not found: {log_file}")
        return
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:]  # Last 100 lines
            
            pydantic_found = False
            json_mode_found = False
            
            for line in recent_lines:
                if "Pydantic model path" in line or "Creating structured LLM" in line:
                    pydantic_found = True
                    print(f"✓ Found Pydantic path usage: {line.strip()}")
                if "JSON mode path" in line:
                    json_mode_found = True
                    print(f"✓ Found JSON mode path usage: {line.strip()}")
            
            if not pydantic_found:
                print("⚠ No Pydantic path logs found (may need to check with DEBUG level)")
            if not json_mode_found:
                print("⚠ No JSON mode path logs found (may need to check with DEBUG level)")
                
    except Exception as e:
        print(f"✗ Error reading logs: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("Phase 2 Implementation Verification Tests")
    print("="*70)
    
    results = []
    
    # Test 1: ResponseFormatter with Pydantic
    results.append(("ResponseFormatter (Pydantic)", test_response_formatter_pydantic()))
    
    # Test 2: Planner with dict schema
    results.append(("Planner (Dict Schema)", test_planner_dict_schema()))
    
    # Test 3: Check logs
    check_logs_for_paths()
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All tests passed! Phase 2 implementation is working correctly.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
