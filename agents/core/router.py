# router.py
# A tiny router that maps high-level task names to tool-callable names (keeps agents simple)
def route_task(task_name: str, tools: dict, params: dict):
    # tools: dict mapping tool_name -> tool_callable
    if task_name in tools:
        tool = tools[task_name]
        # Check if it's a LangChain StructuredTool (has invoke method)
        if hasattr(tool, 'invoke'):
            # LangChain tools expect params wrapped in 'query' key based on function signature
            return tool.invoke({'query': params})
        else:
            # Regular function call
            return tool(params)
    else:
        return {'error':'unknown_task: '+task_name}
