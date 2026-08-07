from langchain.tools import tool
from typing import Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

# -------------------------------
# 1. Define tools (no LLM calls inside)
# -------------------------------
@tool
def get_prime_minister_of_india() -> str:
    """
    Get the current Prime Minister of India.
    """
    """Return the current Prime Minister of India."""
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

tools = [get_prime_minister_of_india, get_capital_of_country, get_climate_of_country]
# 1. State: Use Annotated and operator.add to enable message accumulation
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    city: str

# Assume 'tools' is your list of bound tools
llm_with_tools = llm_openai.bind_tools(tools)

# 3. Node: The "Agent" (LLM)
def call_model(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])
    #print(f"LLM OUTPUT: {response.tool_calls}")
    return {"messages": [response]}

# 4. Graph Construction
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
# ToolNode is a prebuilt LangGraph component that handles the loop you wrote manually
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "agent")
# tools_condition is a smart edge that routes to 'tools' if tool_calls exist, else END
workflow.add_conditional_edges("agent", tools_condition)
# Insert it into your edges
workflow.add_edge("tools", "agent") 

#workflow.add_edge("tools", "agent") # This edge is the "Feedback Loop" that turns a static script into an autonomous agent. Without this line, your agent would be a "one-shot" system that stops after executing a tool.
# Initialize a memory saver (the checkpointer)
checkpointer = MemorySaver()

# 'interrupt_before=["tools"]' forces the graph to pause right before running a tool
app = workflow.compile(checkpointer=checkpointer, interrupt_before=["tools"])

def run_turn(prompt: str, config):
    # 1. Trigger the agent
    app.invoke({"messages": [HumanMessage(content=prompt)]}, config=config)

    # 2. Keep resuming until the task is completely finished (next step is None)
    while True:
        snapshot = app.get_state(config)
        # Check if there is an interrupt
        if snapshot.tasks and snapshot.tasks[0].interrupts:
            print("Agent paused. Resuming tool execution...")
            input() # <--- THE AGENT WILL WAIT HERE FOR YOU
            app.invoke(None, config=config)
        # If no tasks are currently running, the agent is finished
        elif not snapshot.next:
            break
        # Otherwise, the graph is still processing (e.g., waiting for the next node)
        else:
            app.invoke(None, config=config)

    return app.get_state(config).values


'''
With no interrupts, the graph runs:
Human → AIMessage (tool call) → ToolNode → ToolMessage → AIMessage (final answer).

With interrupts enabled, the graph stops before ToolNode. If you don’t explicitly resume, the ToolMessage never gets created. If you then send another HumanMessage, the API sees a dangling tool call and throws the error.
'''
#config = {"configurable": {"thread_id": "session-1"}}
# 1. Define distinct configurations for each session
session_a = {"configurable": {"thread_id": "session-A"}}
session_b = {"configurable": {"thread_id": "session-B"}}

print("--------------------------------------------------------------------------------")

# 1. Clear out your existing prints and run these specific turns
# Turn 1: Establish context in Session A
run_turn("My name is Alice.", {"configurable": {"thread_id": "session-A"}})

# Turn 2: Establish different context in Session B
run_turn("My name is Bob.", {"configurable": {"thread_id": "session-B"}})

# Turn 3: Ask a question relying on memory in Session A
result_a = app.invoke({"messages": [HumanMessage(content="What is my name?")]}, 
                     config={"configurable": {"thread_id": "session-A"}})
print(f"SESSION A Memory Test: {result_a['messages'][-1].content}")

# Turn 4: Ask the same question in Session B
result_b = app.invoke({"messages": [HumanMessage(content="What is my name?")]}, 
                     config={"configurable": {"thread_id": "session-B"}})
print(f"SESSION B Memory Test: {result_b['messages'][-1].content}")

# 5. Print the full memory for inspection
def show_full_history(tid):
    config = {"configurable": {"thread_id": tid}}
    state = app.get_state(config)
    print(f"\n--- FULL HISTORY FOR {tid} ---")
    for msg in state.values["messages"]:
        print(f"{msg.type.upper()}: {msg.content}")

show_full_history("session-A")
show_full_history("session-B")