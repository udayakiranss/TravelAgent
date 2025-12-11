import pytest
from agents.domain.payment_agent import PaymentAgent, process_payment_tool

class TestPaymentAgent:
    
    @pytest.fixture
    def agent(self, mock_llm):
        return PaymentAgent(llm=mock_llm)

    def test_process_payment_tool(self):
        query = {"amount": 1000, "method": "card"}
        result = process_payment_tool.invoke({"query": query})
        assert result["status"] == "success"
        assert result["charged"] == 1000
        
    def test_process_payment_tool_invalid(self):
        query = {"amount": -100}
        result = process_payment_tool.invoke({"query": query})
        assert "error" in result
