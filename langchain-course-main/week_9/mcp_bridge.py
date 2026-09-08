from langchain_core.tools import Tool

async def get_langchain_mcp_tools(mcp_client_manager):
    """Dynamically converts MCP tools into LangChain tools safely."""
    mcp_tools = await mcp_client_manager.list_available_tools()
    langchain_tools = []
    
    for tool in mcp_tools:
        # Safely extract input schema supporting different SDK naming conventions
        schema = (
            getattr(tool, "inputSchema", None) or 
            getattr(tool, "input_schema", None) or 
            (tool.get("inputSchema") if isinstance(tool, dict) else {}) or
            {}
        )
        
        schema_properties = schema.get("properties", {}) if hasattr(schema, "get") else {}
        param_names = list(schema_properties.keys())
        
        def make_run_func(name=tool.name, params=param_names):
            async def run_tool(*args, **kwargs):
                call_args = dict(kwargs)
                
                # Map positional arguments to the tool's expected schema parameter names
                if args:
                    for i, arg in enumerate(args):
                        if i < len(params):
                            call_args[params[i]] = arg
                        else:
                            call_args[f"arg_{i}"] = arg
                            
                # Fallback if a single string was passed and the schema expects a single parameter
                if not call_args and args:
                    if len(params) == 1:
                        call_args[params[0]] = args[0]
                    else:
                        call_args = {"query": args[0]}
                        
                result = await mcp_client_manager.call_tool(name, call_args)
                return result.content[0].text
            return run_tool

        # Create the LangChain Tool wrapper
        lc_tool = Tool(
            name=tool.name,
            description=tool.description,
            func=None,
            coroutine=make_run_func(tool.name, param_names)
        )
        langchain_tools.append(lc_tool)
        
    return langchain_tools