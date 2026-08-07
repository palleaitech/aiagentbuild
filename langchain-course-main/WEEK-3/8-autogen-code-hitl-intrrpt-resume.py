import os
from typing import Annotated, Dict, List, Literal, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from dotenv import load_dotenv  

# =====================================================================
# 1. LOCAL FALLBACKS & EXTERNAL TOOLS
# =====================================================================

# Local fallback dictionaries for resilient routing when external APIs fail
COUNTRY_FALLBACK_DB = {
    "india": "Capital: New Delhi, Currency: INR, Dialing Code: +91",
    "france": "Capital: Paris, Currency: EUR, Dialing Code: +33",
    "japan": "Capital: Tokyo, Currency: JPY, Dialing Code: +81",
}

HOLIDAY_FALLBACK_DB = {
    "india": "January 26: Republic Day, August 15: Independence Day, October 2: Gandhi Jayanti",
    "usa": "July 4: Independence Day, November 26: Thanksgiving, December 25: Christmas",
}


@tool
def get_country_info(country: str) -> str:
    """Retrieves country profile information like capital, currency, and dialing code."""
    country_clean = country.strip().lower()
    # Check local fallback dictionary first for high resilience
    if country_clean in COUNTRY_FALLBACK_DB:
        return f"[Fallback Source] {COUNTRY_FALLBACK_DB[country_clean]}"
    return f"Error: Country '{country}' not found in the information database."


@tool
def get_holiday_info(country: str) -> str:
    """Retrieves major national public holidays for a given country."""
    country_clean = country.strip().lower()
    if country_clean in HOLIDAY_FALLBACK_DB:
        return f"[Fallback Source] {HOLIDAY_FALLBACK_DB[country_clean]}"
    return f"Error: Holiday calendar for '{country}' is unavailable."


# Bind tools to the GPT-4o LLM instance
tools = [get_country_info, get_holiday_info]
tools_by_name = {tool.name: tool for tool in tools}
#llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

# =====================================================================
# 2. STATE DEFINITION & GRAPH NODES
# =====================================================================


class AgentState(TypedDict):
    """Tracks the continuous conversational state of the orchestrator graph."""

    messages: Annotated[List[BaseMessage], add_messages]


def agent_node(state: AgentState) -> Dict:
    """Reasoning node execution: passes conversation history to the model."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def action_node(state: AgentState) -> Dict:
    """Reactive node execution: processes and executes requested tools."""
    last_message = state["messages"][-1]
    tool_outputs = []

    for tool_call in last_message.tool_calls:
        tool_obj = tools_by_name[tool_call["name"]]
        try:
            # Execute tool and intercept runtime errors gracefully
            output = tool_obj.invoke(tool_call["args"])
        except Exception as e:
            output = f"Fallback error safety triggered: {str(e)}"

        tool_outputs.append(
            ToolMessage(
                content=str(output),
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
            )
        )

    return {"messages": tool_outputs}


def route_next_node(state: AgentState) -> Literal["tools", "__end__"]:
    """Conditional router determining whether to terminate or call a tool."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# =====================================================================
# 3. GRAPH ORCHESTRATION COMPOSITION
# =====================================================================

workflow = StateGraph(AgentState)

# Add logical processing units to the orchestration grid
workflow.add_node("agent", agent_node)
workflow.add_node("tools", action_node)

# Map edge transitions representing the ReAct pattern
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", route_next_node, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

# Enable state continuity and Human-in-the-Loop intervention points
memory = MemorySaver()
orchestrator = workflow.compile(
    checkpointer=memory,
    interrupt_before=["tools"],  # Human approval checkpoint before executing any tool
)

# =====================================================================
# 4. RUNTIME EXECUTION SIMULATION
# =====================================================================
if __name__ == "__main__":

  # Load environment variables (API key stored in .env file)
  load_dotenv()
  api_key = os.getenv("OPENAI_API_KEY")

  # Validate API key presence
  if not api_key:
      raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

  # Initialize the LLM (GPT-4o) with given parameters
  llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

  # Set up thread session config
  config = {"configurable": {"thread_id": "session_001"}}
  user_query = "What is the capital of Japan and what major holidays do they celebrate in India?"

  print(f"--- Initializing Agentic Orchestration Session ---")
  print(f"User Input: {user_query}\n")

  # Step 1: Stream the graph until it reaches the tool interruption checkpoint
  events = orchestrator.stream(
      {"messages": [HumanMessage(content=user_query)]},
      config,
      stream_mode="values",
  )
  
  # Process the stream up to the breakpoint
  for event in events:
      pass 

  # Step 2: Read the state snapshot to check if we are currently interrupted
  state_snapshot = orchestrator.get_state(config)
  
  if state_snapshot.next:  # If 'next' contains values, the graph is paused at a node
      print("==> [ORCHESTRATOR PAUSED: HUMAN-IN-THE-LOOP CHECKPOINT] <=")
      print(f"Next node pending execution: {list(state_snapshot.next)}")
      
      # Extract and print the pending tool actions for user visibility
      last_msg = state_snapshot.values["messages"][-1]
      if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
          print("Pending tool calls:")
          for call in last_msg.tool_calls:
              print(f" - Tool: {call['name']} | Arguments: {call['args']}")
      
      print("\n" + "="*50)
      # Real-time keyboard input block
      human_choice = input("Type 'yes' or 'approve' to execute tools, or 'no' to abort: ").strip().lower()
      print("="*50 + "\n")

      # Step 3: Handle the live keyboard decision
      if human_choice in ["yes", "approve"]:
          print(f"[Terminal Input]: {human_choice.upper()} received. Resuming orchestrator thread...")
          
          # Resume processing by sending None into the stream
          resume_events = orchestrator.stream(None, config, stream_mode="values")
          for event in resume_events:
              final_message = event["messages"][-1]

          print("\n==> [FINAL ORCHESTRATOR RESPONSE] <==")
          print(final_message.content)
      else:
          print("[Terminal Input]: REJECTED/ABORTED. Terminating session safely without running tools.")
