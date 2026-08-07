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
# Compile
#app = workflow.compile()
config = {"configurable": {"thread_id": "session-1"}}
# 2. Compile the graph with the checkpointer AND your interrupt point
# 'interrupt_before=["tools"]' forces the graph to pause right before running a tool
app = workflow.compile(checkpointer=checkpointer) #, interrupt_before=["tools"])

print("--------------------------------------------------------------------------------")

result = app.invoke(
    {"messages": [HumanMessage(content="What is the climate in India?")]},
    config=config)

# 5. For the next turn, just call invoke with the NEW input
result = app.invoke(
    {"messages": [HumanMessage(content="What is the capital of France?")]},
    config=config
)

result = app.invoke(
    {"messages": [HumanMessage(content="Prime Minister of India?")]},
    config=config    
)

# Finally, get the full history from the checkpointer's database
final_state = app.get_state(config)
for msg in final_state.values["messages"]:
    if msg.type == "human":
        print(f"HUMAN: {msg.content}")
    elif msg.type == "ai":
        # Check if the AI made a tool call or gave a final answer
        if msg.tool_calls:
            print(f"AI (Thinking): Calling tool {msg.tool_calls[0]['name']}")
        else:
            print(f"AI: {msg.content}")
    elif msg.type == "tool":
        print(f"TOOL ({msg.name}): {msg.content}")

