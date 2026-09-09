from typing import TypedDict, Annotated, List
import operator
import asyncio
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

from app.core.llm import get_llm

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    city: str
    next_worker: str
    input: str
    plan: List[str]
    current_step_index: int
    execution_history: Annotated[List[str], operator.add]      
    critique: str
    final_output: str

def create_worker_agent(tools, system_prompt: str = None):
    llm_openai = get_llm(tier="summarization", temperature=0.7).bind_tools(tools)
    tool_map = {tool.name: tool for tool in tools}

    def call_model(state: AgentState):
        messages = state["messages"]
        if system_prompt and not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
            
        response = llm_openai.invoke(messages)
        return {"messages": [response]} 

    # ⚡ Standard synchronous node function that safely executes async tool coroutines
    def call_tools(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_messages = []
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            # Get or create an event loop to run the async tool ainvoke
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]
                
                if tool_name in tool_map:
                    tool_obj = tool_map[tool_name]
                    try:
                        # Run the async tool coroutine safely from sync context
                        if hasattr(tool_obj, "ainvoke"):
                            if loop.is_running():
                                # If loop is running, run via a helper or future
                                future = asyncio.run_coroutine_threadsafe(tool_obj.ainvoke(tool_args), loop)
                                tool_result = future.result(timeout=10)
                            else:
                                tool_result = loop.run_until_complete(tool_obj.ainvoke(tool_args))
                        else:
                            tool_result = tool_obj.invoke(tool_args)
                    except Exception as e:
                        tool_result = f"Error executing tool {tool_name}: {str(e)}"
                else:
                    tool_result = f"Error: Tool {tool_name} not found."
                
                tool_messages.append(
                    ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
                )
                
        return {"messages": tool_messages}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tools)  # 👈 Standard sync node compatible with LangGraph execution
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    workflow.add_edge("agent", END)

    return workflow.compile(checkpointer=MemorySaver())