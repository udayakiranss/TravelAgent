import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

load_dotenv()

from database.connection import get_session_context, create_db_and_tables
from agents.orchestrator import Orchestrator
from api.context import TravelContext
from utils.logger import get_logger

logger = get_logger()
logger.setup()

def run():
    # Ensure DB tables exist
    create_db_and_tables()

    with get_session_context() as session:
        # Create orchestrator
        print("Initializing Orchestrator...")
        orch = Orchestrator()
        
        if orch.llm:
            print("✓ LLM Provider initialized")
            query = "Plan a weekend trip to Paris"
        else:
            print("⚠️  LLM not available. Using rule-based fallback.")
            # Rule based requires specific format "from XXX to YYY"
            # We'll help it out since 'Paris' isn't an airport code
            query = "Plan a weekend trip from JFK to CDG" 
            print(f"Adjusted query for rule-based parser: {query}")

        # Create context
        ctx = TravelContext(
            session=session,
            llm=orch.llm,
            traveler_id="user_123"
        )

        print(f"Executing plan for traveler: {ctx.traveler_id}")
        print(f"Query: {query}")
        
        try:
            result = orch.plan_trip(query, ctx)
            print("\n" + "="*50)
            print("PLANNING RESULT")
            print("="*50)
            print(result.get('summary', 'No summary generated'))
            print("\nDetailed Options:")
            print(f"- Flights found: {len(result.get('flight_options', []))}")
            print(f"- Hotels found: {len(result.get('hotel_options', []))}")
            print(f"- Cars found: {len(result.get('car_options', []))}")
            
            if result.get('flight_reservation'):
                print("\nSelected Flight:")
                print(result['flight_reservation'])
                
            if result.get('hotel_reservation'):
                print("\nSelected Hotel:")
                print(result['hotel_reservation'])
                
        except Exception as e:
            print(f"\n❌ Error executing plan: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run()
