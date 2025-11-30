# main.py - demo runner with LLM-based agent orchestration
from agents.orchestrator import Orchestrator
from agents.memory import create_memory
from agents.llm_provider import create_llm_provider
from utils.logger import get_logger, SessionContext, log_critical_entry_exit, log_method_entry_exit
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger()

@log_method_entry_exit(level="DEBUG")
def interpret_nl(text: str):
    """Simple rule-based NL parser for demo (used only when LLM is not available)"""
    logger.debug(f"Parsing text: {text[:50]}...")
    text = text.lower()
    intent = {'needs': []}
    
    if 'flight' in text or 'fly' in text:
        intent['needs'].append('flight')
    if 'hotel' in text or 'stay' in text:
        intent['needs'].append('hotel')
    if 'car' in text or 'rental' in text:
        intent['needs'].append('car')
    
    import re
    m = re.search(r'from ([a-z]{3}) to ([a-z]{3})', text)
    if m:
        intent['from'] = m.group(1).upper()
        intent['to'] = m.group(2).upper()
    
    d = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if d:
        intent['date'] = d.group(1)
    
    if 'pay' in text or 'charge' in text:
        intent['auto_pay'] = True
    
    return intent


@log_method_entry_exit(level="INFO")
def interpret_nl_with_llm(text: str, llm) -> dict:
    """Use LLM to parse natural language into structured intent"""
    logger.info(f"Using LLM to parse query: {text[:100]}...")
    import json
    
    prompt = f"""Parse the following user query about travel booking into a structured intent format.

User Query: "{text}"

Extract the following information:
- needs: List of services needed (flight, hotel, car)
- from: Origin airport code (3 letters, uppercase)
- to: Destination airport code (3 letters, uppercase)
- date: Travel date in YYYY-MM-DD format
- auto_pay: Boolean indicating if payment should be processed automatically
- budget: Optional budget amount
- payment_method: Optional payment method (card, visa, etc.)

Return ONLY a valid JSON object with these fields. Example:
{{
  "needs": ["flight", "hotel"],
  "from": "NYC",
  "to": "LON",
  "date": "2025-08-12",
  "auto_pay": false
}}"""

    try:
        response = llm.invoke_structured(
            prompt,
            response_format={
                "type": "object",
                "properties": {
                    "needs": {"type": "array", "items": {"type": "string"}},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "date": {"type": "string"},
                    "auto_pay": {"type": "boolean"},
                    "budget": {"type": "number"},
                    "payment_method": {"type": "string"}
                }
            }
        )
        
        # Handle response format
        if isinstance(response, dict):
            if "raw_response" in response:
                # Try to parse raw response
                try:
                    return json.loads(response["raw_response"])
                except:
                    # Fallback to rule-based
                    return interpret_nl(text)
            else:
                # Valid structured response
                intent = {
                    "needs": response.get("needs", []),
                    "from": response.get("from", ""),
                    "to": response.get("to", ""),
                    "date": response.get("date", ""),
                    "auto_pay": response.get("auto_pay", False),
                    "budget": response.get("budget"),
                    "payment_method": response.get("payment_method")
                }
                # Remove None/empty values
                return {k: v for k, v in intent.items() if v or k == "needs"}
        else:
            return interpret_nl(text)  # Fallback
    
    except Exception as e:
        print(f"⚠️  LLM parsing failed: {e}, falling back to rule-based parser")
        return interpret_nl(text)

@log_critical_entry_exit
def main():
    """Main entry point for the travel booking system"""
    # Setup logger (reads from environment variables: LOG_LEVEL, LOG_OUTPUT, LOG_FILE, LOG_DIR)
    logger.setup()
    
    # Create new session
    session_id = SessionContext.new_session()
    logger.info(f"Starting new session: {session_id}")
    
    print("=" * 60)
    print("Travel Booking Agent System with LLM Integration")
    print("=" * 60)
    
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not found in environment")
        print("\n⚠️  Warning: OPENAI_API_KEY not found in environment.")
        print("   The system will work but LLM-based planning will be disabled.")
        print("   Set OPENAI_API_KEY to enable intelligent agent selection.\n")
        llm = None
    else:
        logger.info("OpenAI API key found, initializing LLM provider")
        print("\n✓ OpenAI API key found. LLM-based planning enabled.\n")
        try:
            # Create LLM provider (supports multiple foundation models)
            llm = create_llm_provider(
                model_name="gpt-4o",  # Can be changed to: gpt-3.5-turbo, claude-3-opus, etc.
                model_provider="openai",  # Can be changed to: anthropic, google, etc.
                temperature=0
            )
            logger.info(f"LLM Provider initialized: {llm.model_name} ({llm.model_provider})")
            print(f"✓ LLM Provider initialized: {llm.model_name} ({llm.model_provider})\n")
        except Exception as e:
            logger.error(f"Could not initialize LLM: {e}", exc_info=True)
            print(f"⚠️  Could not initialize LLM: {e}")
            print("   Continuing with rule-based planning.\n")
            llm = None
    
    # Initialize orchestrator with LLM
    logger.info("Initializing orchestrator")
    memory = create_memory()
    orch = Orchestrator(llm=llm, memory=memory)
    
    agents = orch.list_agents()
    logger.info(f"Available agents: {', '.join(agents)}")
    print(f"Available agents: {', '.join(agents)}\n")
    print("=" * 60)
    
    # Example queries
    examples = [
        'Find me a flight from NYC to LON on 2025-08-12 and book a hotel'
        # 'I need a rental car in LON for my trip',
        # 'Charge my Visa to pay the total'
    ]
    
    for i, ex in enumerate(examples, 1):
        logger.info(f"Processing example {i}: {ex}")
        print(f"\n{'='*60}")
        print(f"Example {i}: {ex}")
        print('='*60)
        
        # Parse intent: use LLM if available, otherwise use rule-based parser
        if llm:
            intent = interpret_nl_with_llm(ex, llm)
            logger.debug(f"Parsed intent (LLM): {intent}")
            print(f'Parsed Intent (LLM): {intent}\n')
        else:
            intent = interpret_nl(ex)
            logger.debug(f"Parsed intent (Rule-based): {intent}")
            print(f'Parsed Intent (Rule-based): {intent}\n')
        
        try:
            logger.info(f"Executing intent: {intent}")
            results = orch.run_intent(intent)
            logger.info(f"Intent execution completed successfully")
            
            print('\nResults:')
            for key, value in results.items():
                logger.debug(f"Result for {key}: {str(value)[:100]}")
                print(f"  {key}:")
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list):
                    for item in value:
                        print(f"    {item}")
                else:
                    print(f"    {value}")
        except Exception as e:
            logger.error(f"Error processing example {i}: {e}", exc_info=True)
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("Demo completed successfully")
    print(f"\n{'='*60}")
    print("Demo completed!")
    print('='*60)


if __name__ == '__main__':
    main()
