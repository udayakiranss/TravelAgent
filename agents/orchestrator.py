# orchestrator.py
from typing import Dict, Any
from agents.planner import plan_trip
from agents.router import route_task
from tools.search_tools import search_flights, search_hotels, search_cars
from tools.payment_tool import process_payment
from tools.search_tools import search_flights as sf
from tools.search_tools import search_hotels as sh
from tools.search_tools import search_cars as sc
from tools.payment_tool import process_payment as pp

# Aggregate tools mapping for router
TOOL_MAP = {
    'search_flights': sf,
    'search_hotels': sh,
    'search_cars': sc,
    'process_payment': pp,
}

class Orchestrator:
    def __init__(self, llm=None, memory=None):
        # Note: llm and memory are kept for API compatibility but not used in this simple implementation
        self.llm = llm
        self.memory = memory
        self.tools = TOOL_MAP

    def run_intent(self, intent: Dict[str, Any]):
        # create a plan (list of tasks)
        tasks = plan_trip(intent)
        print("Tasks: ", tasks)
        results = {}
        for t in tasks:
            name = t['task']
            params = t.get('params', {})
            # route to proper tool
            res = route_task(name, self.tools, params)
            results[name] = res
        return results
