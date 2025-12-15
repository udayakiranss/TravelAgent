from langchain_core.tools import tool
from typing import Dict, Any

@tool
def process_payment(query: Dict[str, Any]):
    """Simulate a payment. Fields: amount, method."""
    amount = query.get('amount')
    method = query.get('method', 'card')
    # Very simple simulation
    return {'status':'success', 'charged': amount, 'method': method}
