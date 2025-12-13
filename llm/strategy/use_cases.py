from enum import Enum

class UseCase(str, Enum):
    """
    Enumeration of all supported LLM use cases in the application.
    Must match keys in llm/config/model_strategy.yaml.
    """
    PLANNER = "planner"
    INTENT_PARSING = "intent_parsing"
    SUMMARY_GENERATION = "summary_generation"
    TASK_ROUTING = "task_routing"
    MODIFICATION = "modification"
