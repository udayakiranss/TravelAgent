# payment_agent.py
# Payment processing agent
from typing import Dict, Any
from langchain.tools import tool
from agents.core.base_agent import BaseAgent
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


@tool
def process_payment_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment. Returns payment confirmation."""
    amount = query.get('amount', 0)
    method = query.get('method', 'card')
    card_number = query.get('card_number', '****')
    currency = query.get('currency', 'USD')
    
    logger.debug(f"Processing payment: amount={amount} {currency}, method={method}")
    
    if amount <= 0:
        logger.warning(f"Invalid payment amount: {amount}")
        return {"error": "Invalid payment amount"}
    
    transaction_id = f"TXN-{hash(f'{amount}{method}') % 1000000:06d}"
    payment = {
        "status": "success",
        "transaction_id": transaction_id,
        "charged": amount,
        "method": method,
        "currency": currency,
        "card_last4": card_number[-4:] if len(card_number) > 4 else "****"
    }
    
    logger.info(f"Payment processed successfully: {transaction_id}, amount=${amount} {currency}")
    return payment


@tool
def verify_payment_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a payment transaction by transaction ID."""
    transaction_id = query.get('transaction_id')
    
    logger.debug(f"Verifying payment transaction: {transaction_id}")
    
    if not transaction_id:
        logger.warning("Transaction ID is required for verification")
        return {"error": "Transaction ID is required"}
    
    # In a real system, this would query a payment database
    result = {
        "status": "verified",
        "transaction_id": transaction_id,
        "verified": True
    }
    
    logger.info(f"Payment transaction verified: {transaction_id}")
    return result


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
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute payment processing task"""
        logger.debug(f"PaymentAgent executing task: {task} with params: {params}")
        if task in self.tools:
            result = self._call_tool(task, params)
            logger.debug(f"Task '{task}' completed successfully")
            return result
        else:
            if self.llm:
                logger.debug(f"Task '{task}' not found in tools, using LLM routing")
                return self._llm_route_task(task, params)
            else:
                logger.warning(f"Unknown task '{task}' for PaymentAgent and no LLM available")
                return {"error": f"Unknown task '{task}' for PaymentAgent"}
    
    @log_method_entry_exit(level="DEBUG")
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Payment Processing Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        logger.debug(f"Using LLM to route task '{task}' to appropriate tool")
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM suggested tool: {tool_name}")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            logger.warning(f"LLM suggested unknown tool '{tool_name}'")
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}

