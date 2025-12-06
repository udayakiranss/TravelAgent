#!/usr/bin/env python3
"""
test_agents.py - Individual Agent Testing Script

This script allows you to test each agent independently to verify they work correctly
with the mock data before running the full orchestrator.

Usage:
    python test_agents.py                    # Run all tests
    python test_agents.py --agent flight     # Test only flight agent
    python test_agents.py --agent hotel      # Test only hotel agent
    python test_agents.py --agent car        # Test only car agent
    python test_agents.py --agent itinerary  # Test only itinerary agent
    python test_agents.py --agent payment    # Test only payment agent
    python test_agents.py --interactive      # Interactive mode
"""

import argparse
import json
from typing import Dict, Any
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import agents
from agents.flight_booking_agent import FlightBookingAgent
from agents.hotel_booking_agent import HotelBookingAgent
from agents.car_rental_agent import CarRentalAgent
from agents.itinerary_agent import ItineraryAgent
from agents.payment_agent import PaymentAgent
from agents.llm_provider import create_llm_provider


def get_llm():
    """Initialize LLM if API key is available"""
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        try:
            return create_llm_provider(model_name="gpt-4o", model_provider="openai", temperature=0)
        except Exception as e:
            print(f"⚠️  Could not initialize LLM: {e}")
            return None
    return None


def print_result(title: str, result: Any):
    """Pretty print test results"""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print('='*60)
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    elif isinstance(result, list):
        for item in result:
            print(json.dumps(item, indent=2, default=str))
    else:
        print(result)


def test_flight_agent(llm=None):
    """Test FlightBookingAgent with various scenarios"""
    print("\n" + "="*70)
    print("✈️  TESTING FLIGHT BOOKING AGENT")
    print("="*70)
    
    agent = FlightBookingAgent(llm=llm)
    print(f"\nAvailable tools: {agent.get_available_tools()}")
    
    # Test 1: Search flights from Bangalore to Dubai
    print_result("Test 1: Search BLR to DXB on 2026-04-01", 
                 agent.execute('search_flights', {'from': 'BLR', 'to': 'DXB', 'date': '2026-04-01'}))
    
    # Test 2: Search flights with different date
    print_result("Test 2: Search BLR to DXB on 2026-04-05", 
                 agent.execute('search_flights', {'from': 'BLR', 'to': 'DXB', 'date': '2026-04-05'}))
    
    # Test 3: Search return flights
    print_result("Test 3: Search DXB to BLR on 2026-04-06 (Return)", 
                 agent.execute('search_flights', {'from': 'DXB', 'to': 'BLR', 'date': '2026-04-06'}))
    
    # Test 4: Compare flights
    print_result("Test 4: Compare flights F001, F002", 
                 agent.execute('compare_flights', {'flight_ids': ['F001', 'F002']}))
    
    # Test 5: Book a flight
    print_result("Test 5: Book flight F002 for John Doe", 
                 agent.execute('book_flight', {'flight_id': 'F002', 'passenger_name': 'John Doe'}))
    
    # Test 6: Search non-existent route (should return empty)
    print_result("Test 6: Search non-existent route (XXX to YYY)", 
                 agent.execute('search_flights', {'from': 'XXX', 'to': 'YYY', 'date': '2026-04-01'}))
    
    print("\n✅ Flight Agent tests completed!")
    return True


def test_hotel_agent(llm=None):
    """Test HotelBookingAgent with various scenarios"""
    print("\n" + "="*70)
    print("🏨 TESTING HOTEL BOOKING AGENT")
    print("="*70)
    
    agent = HotelBookingAgent(llm=llm)
    print(f"\nAvailable tools: {agent.get_available_tools()}")
    
    # Test 1: Search hotels in Dubai
    print_result("Test 1: Search hotels in Dubai (DXB)", 
                 agent.execute('search_hotels', {'city': 'DXB'}))
    
    # Test 2: Search hotels in London
    print_result("Test 2: Search hotels in London (LON)", 
                 agent.execute('search_hotels', {'city': 'LON'}))
    
    # Test 3: Compare hotels
    print_result("Test 3: Compare hotels H001, H004, H005 (Luxury vs Budget)", 
                 agent.execute('compare_hotels', {'hotel_ids': ['H001', 'H004', 'H005']}))
    
    # Test 4: Book a hotel
    print_result("Test 4: Book Rove Downtown (H004) for Jane Smith", 
                 agent.execute('book_hotel', {
                     'hotel_id': 'H004',
                     'guest_name': 'Jane Smith',
                     'check_in': '2026-04-01',
                     'check_out': '2026-04-06'
                 }))
    
    # Test 5: Search in non-existent city
    print_result("Test 5: Search non-existent city (XXX)", 
                 agent.execute('search_hotels', {'city': 'XXX'}))
    
    print("\n✅ Hotel Agent tests completed!")
    return True


def test_car_agent(llm=None):
    """Test CarRentalAgent with various scenarios"""
    print("\n" + "="*70)
    print("🚗 TESTING CAR RENTAL AGENT")
    print("="*70)
    
    agent = CarRentalAgent(llm=llm)
    print(f"\nAvailable tools: {agent.get_available_tools()}")
    
    # Test 1: Search cars in Dubai
    print_result("Test 1: Search cars in Dubai (DXB)", 
                 agent.execute('search_cars', {'city': 'DXB'}))
    
    # Test 2: Search cars in San Francisco
    print_result("Test 2: Search cars in San Francisco (SFO)", 
                 agent.execute('search_cars', {'city': 'SFO'}))
    
    # Test 3: Compare cars
    print_result("Test 3: Compare cars C001, C004, C005 (Economy vs Luxury)", 
                 agent.execute('compare_cars', {'car_ids': ['C001', 'C004', 'C005']}))
    
    # Test 4: Book a car
    print_result("Test 4: Book Toyota Camry (C007) for Mike Johnson", 
                 agent.execute('book_car', {
                     'car_id': 'C007',
                     'renter_name': 'Mike Johnson',
                     'pickup_date': '2026-04-01',
                     'return_date': '2026-04-06'
                 }))
    
    # Test 5: Search with empty city
    print_result("Test 5: Search with no city (should return empty)", 
                 agent.execute('search_cars', {'city': ''}))
    
    print("\n✅ Car Rental Agent tests completed!")
    return True


def test_itinerary_agent(llm=None):
    """Test ItineraryAgent with various scenarios"""
    print("\n" + "="*70)
    print("📅 TESTING ITINERARY AGENT")
    print("="*70)
    
    agent = ItineraryAgent(llm=llm)
    print(f"\nAvailable tools: {agent.get_available_tools()}")
    
    # Test 1: Build itinerary with all bookings
    mock_flight_booking = {
        "status": "confirmed",
        "booking_id": "BK-F002-JOH",
        "flight": {"id": "F002", "from": "BLR", "to": "DXB", "date": "2026-04-01", "price": 280},
        "passenger": "John Doe",
        "total_price": 280
    }
    
    mock_hotel_booking = {
        "status": "confirmed",
        "booking_id": "HTL-H004-JAN",
        "hotel": {"id": "H004", "city": "DXB", "name": "Rove Downtown", "price": 150},
        "guest": "Jane Smith",
        "check_in": "2026-04-01",
        "check_out": "2026-04-06",
        "total_price": 150
    }
    
    mock_car_booking = {
        "status": "confirmed",
        "booking_id": "CAR-C007-MIK",
        "car": {"id": "C007", "city": "DXB", "company": "Budget UAE", "model": "Toyota Camry", "price": 80},
        "renter": "Mike Johnson",
        "pickup_date": "2026-04-01",
        "return_date": "2026-04-06",
        "total_price": 80
    }
    
    print_result("Test 1: Build complete itinerary", 
                 agent.execute('build_itinerary', {
                     'destination': 'Dubai',
                     'start_date': '2026-04-01',
                     'end_date': '2026-04-06',
                     'flight_booking': mock_flight_booking,
                     'hotel_booking': mock_hotel_booking,
                     'car_booking': mock_car_booking
                 }))
    
    # Test 2: Build itinerary without car
    print_result("Test 2: Build itinerary (flight + hotel only)", 
                 agent.execute('build_itinerary', {
                     'destination': 'Dubai',
                     'start_date': '2026-04-01',
                     'end_date': '2026-04-06',
                     'flight_booking': mock_flight_booking,
                     'hotel_booking': mock_hotel_booking
                 }))
    
    print("\n✅ Itinerary Agent tests completed!")
    return True


def test_payment_agent(llm=None):
    """Test PaymentAgent with various scenarios"""
    print("\n" + "="*70)
    print("💳 TESTING PAYMENT AGENT")
    print("="*70)
    
    agent = PaymentAgent(llm=llm)
    print(f"\nAvailable tools: {agent.get_available_tools()}")
    
    # Test 1: Process payment
    print_result("Test 1: Process payment of $510 with Visa", 
                 agent.execute('process_payment', {
                     'amount': 510,
                     'payment_method': 'visa',
                     'booking_ids': ['BK-F002-JOH', 'HTL-H004-JAN', 'CAR-C007-MIK']
                 }))
    
    # Test 2: Process payment with different method
    print_result("Test 2: Process payment of $1200 with MasterCard", 
                 agent.execute('process_payment', {
                     'amount': 1200,
                     'payment_method': 'mastercard'
                 }))
    
    # Test 3: Process payment without amount (should fail)
    print_result("Test 3: Process payment without amount (should fail)", 
                 agent.execute('process_payment', {
                     'payment_method': 'visa'
                 }))
    
    print("\n✅ Payment Agent tests completed!")
    return True


def run_interactive_mode(llm=None):
    """Interactive mode for testing agents"""
    print("\n" + "="*70)
    print("🎮 INTERACTIVE AGENT TESTING MODE")
    print("="*70)
    
    agents = {
        'flight': FlightBookingAgent(llm=llm),
        'hotel': HotelBookingAgent(llm=llm),
        'car': CarRentalAgent(llm=llm),
        'itinerary': ItineraryAgent(llm=llm),
        'payment': PaymentAgent(llm=llm)
    }
    
    print("\nAvailable agents and their tools:")
    for name, agent in agents.items():
        print(f"  {name}: {agent.get_available_tools()}")
    
    print("\nCommands:")
    print("  <agent> <tool> <json_params>  - Execute agent tool")
    print("  list                          - List agents and tools")
    print("  exit                          - Exit interactive mode")
    print("\nExamples:")
    print('  flight search_flights {"from": "BLR", "to": "DXB", "date": "2026-04-01"}')
    print('  hotel search_hotels {"city": "DXB"}')
    print('  car book_car {"car_id": "C007", "renter_name": "John"}')
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'exit':
                print("Goodbye! 👋")
                break
            
            if user_input.lower() == 'list':
                for name, agent in agents.items():
                    print(f"  {name}: {agent.get_available_tools()}")
                continue
            
            # Parse input: agent tool {params}
            parts = user_input.split(' ', 2)
            if len(parts) < 2:
                print("❌ Usage: <agent> <tool> <json_params>")
                continue
            
            agent_name = parts[0].lower()
            tool_name = parts[1]
            params = json.loads(parts[2]) if len(parts) > 2 else {}
            
            if agent_name not in agents:
                print(f"❌ Unknown agent: {agent_name}. Available: {list(agents.keys())}")
                continue
            
            agent = agents[agent_name]
            if tool_name not in agent.get_available_tools():
                print(f"❌ Unknown tool: {tool_name}. Available: {agent.get_available_tools()}")
                continue
            
            result = agent.execute(tool_name, params)
            print_result(f"Result from {agent_name}.{tool_name}", result)
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON parameters: {e}")
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='Test individual travel booking agents')
    parser.add_argument('--agent', choices=['flight', 'hotel', 'car', 'itinerary', 'payment', 'all'],
                       default='all', help='Which agent to test (default: all)')
    parser.add_argument('--interactive', '-i', action='store_true', 
                       help='Run in interactive mode')
    parser.add_argument('--no-llm', action='store_true',
                       help='Run without LLM (rule-based only)')
    
    args = parser.parse_args()
    
    print("="*70)
    print("🧪 TRAVEL BOOKING AGENTS - INDIVIDUAL TEST SUITE")
    print("="*70)
    
    # Initialize LLM
    llm = None if args.no_llm else get_llm()
    if llm:
        print(f"✅ LLM initialized: {llm.model_name}")
    else:
        print("⚠️  Running without LLM (rule-based mode)")
    
    if args.interactive:
        run_interactive_mode(llm)
        return
    
    # Run tests based on selection
    test_map = {
        'flight': test_flight_agent,
        'hotel': test_hotel_agent,
        'car': test_car_agent,
        'itinerary': test_itinerary_agent,
        'payment': test_payment_agent
    }
    
    if args.agent == 'all':
        for name, test_func in test_map.items():
            test_func(llm)
    else:
        test_map[args.agent](llm)
    
    print("\n" + "="*70)
    print("🎉 ALL TESTS COMPLETED!")
    print("="*70)


if __name__ == '__main__':
    main()
