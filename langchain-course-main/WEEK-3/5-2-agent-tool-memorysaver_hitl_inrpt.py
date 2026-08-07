# Import required modules
from langchain.tools import tool                     # Decorator to define custom tools callable by the agent
from typing import Annotated, TypedDict              # For structured state typing
import operator                                      # Used to accumulate messages in state
from langgraph.graph import StateGraph, START, END   # Core graph framework for agent workflow
from langgraph.prebuilt import ToolNode, tools_condition  # Prebuilt tool execution + routing logic
from langchain_openai import ChatOpenAI              # OpenAI LLM integration
from langchain_core.messages import (SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage)
from langgraph.checkpoint.memory import MemorySaver  # Checkpointer to persist agent state
from dotenv import load_dotenv                       # Load environment variables from .env file
import os


# -------------------------------
# Define tools (simple functions callable by the agent)
# -------------------------------
@tool
def get_prime_minister_of_india() -> str:
    """
    Get the current Prime Minister of India.
    """
    return "Narendra Modi"

@tool
def get_capital_of_country(country: str) -> str:
    """
    Get the capital of a given country.
    """
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

@tool
def get_climate_of_country(country: str) -> str:
    """
    Get the climate of a given country.
    """
    climate_of_country = " coll and hot"
    return climate_of_country 

# Collect all tools in a list for binding
tools = [get_prime_minister_of_india, get_capital_of_country, get_climate_of_country]

# -------------------------------
# Define agent state
# -------------------------------
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]  # Holds conversation messages
    city: str                                             # Example extra field

# -------------------------------
# Define the agent node (LLM execution)
# -------------------------------
def call_model(state: AgentState):
    response = llm_openai.invoke(state["messages"])   # Run LLM with current messages
    return {"messages": [response]}                       # Return updated messages

# -------------------------------
# Build the workflow graph
# -------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)                   # Agent node (LLM execution)
workflow.add_node("tools", ToolNode(tools))              # Tools node (executes defined functions)

workflow.add_edge(START, "agent")                        # Start → Agent
workflow.add_conditional_edges("agent", tools_condition) # Agent → Tools if tool calls exist, else END
workflow.add_edge("tools", "agent")                      # Tools → Agent (loop back after tool execution)

# -------------------------------
# Enable memory checkpointing
# -------------------------------
checkpointer = MemorySaver()

# Compile workflow with pause before agent execution
app = workflow.compile(checkpointer=checkpointer, interrupt_before=["tools"])

# -------------------------------
# Run function with human approval step
# -------------------------------
def run_with_approval(prompt: str, config):
    print(f"\n--- Turn: {prompt} ---", flush=True)

    # Step 1: Start execution with human message
    app.invoke({"messages": [HumanMessage(content=prompt)]}, config=config)

    # Step 2: Pause before agent runs (approval required)
    snapshot = app.get_state(config)
    if snapshot.next == ('tools',):
        user_input = input("Type 'y' to approve, 'n' to stop: ").strip().lower()
        if user_input != 'y':
            return print("Execution stopped.")
        app.invoke(None, config=config)  # Resume agent if approved

    # Step 3: Drain the graph until all nodes finish
    while True:
        snapshot = app.get_state(config)
        if not snapshot.next:            # Stop when no nodes left
            break
        app.invoke(None, config=config)  # Continue execution

    # Step 4: Print final AI response
    final_snapshot = app.get_state(config)
    final_msg = final_snapshot.values["messages"][-1]
    print(f"\n>>> AI RESPONSE: {final_msg.content}")
    print("Turn complete.", flush=True)

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
    llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

    # -------------------------------
    # Test runs (force agent to use tools)
    # -------------------------------

    config = {"configurable": {"thread_id": "session-test-1"}}

    run_with_approval("Use the get_climate_of_country tool to tell me the climate of India.", config)
    run_with_approval("What is the capital of France?", config)
    run_with_approval("Prime Minister of India?", config)
