# payment_agent.py
# Payment processing agent
from typing import Dict, Any
from langchain.tools import tool
from agents.base_agent import BaseAgent


@tool
def process_payment_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment. Returns payment confirmation."""
    amount = query.get('amount', 0)
    method = query.get('method', 'card')
    card_number = query.get('card_number', '****')
    currency = query.get('currency', 'USD')
    
    if amount <= 0:
        return {"error": "Invalid payment amount"}
    
    payment = {
        "status": "success",
        "transaction_id": f"TXN-{hash(f'{amount}{method}') % 1000000:06d}",
        "charged": amount,
        "method": method,
        "currency": currency,
        "card_last4": card_number[-4:] if len(card_number) > 4 else "****"
    }
    return payment


@tool
def verify_payment_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a payment transaction by transaction ID."""
    transaction_id = query.get('transaction_id')
    
    if not transaction_id:
        return {"error": "Transaction ID is required"}
    
    # In a real system, this would query a payment database
    return {
        "status": "verified",
        "transaction_id": transaction_id,
        "verified": True
    }


class PaymentAgent(BaseAgent):
    """Agent specialized in payment processing"""
    
    def __init__(self, llm=None):
        super().__init__(llm=llm, name="PaymentAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize payment processing tools"""
        return {
            'process_payment': process_payment_tool,
            'verify_payment': verify_payment_tool,
        }
    
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute payment processing task"""
        if task in self.tools:
            return self._call_tool(task, params)
        else:
            if self.llm:
                return self._llm_route_task(task, params)
            else:
                return {"error": f"Unknown task '{task}' for PaymentAgent"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Payment Processing Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        tool_name = self.llm.invoke(prompt).strip()
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}

