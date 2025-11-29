Agentic Travel Booking Prototype (LangChain + OpenAI)
----------------------------------------------------
This prototype demonstrates:
  - LangChain agents calling local hard-coded tools
  - Planner + Orchestrator (multi-step orchestration)
  - Router agent to dispatch to specialized agents
  - Conversation memory (buffer + summary)
  - Function-calling style tools
  - Streaming callback example (comments / placeholders)
Run:
  1) Create a virtualenv and install requirements.txt
  2) Set OPENAI_API_KEY in your environment
  3) python main.py
Files:
  - data/: hard-coded flights, hotels, cars
  - tools/: tool wrappers (search & payment)
  - agents/: agent wrappers & orchestrator
  - main.py: demo runner
