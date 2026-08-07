from langchain.tools import tool
from typing import Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage

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
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content="Who is the current Prime Minister of India?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content

@tool
def get_capital_of_country(country: str) -> str:
    """
    Get the capital of a given country.
    """
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content=f"What is the capital of {country}?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content

@tool
def get_climate_of_country(country: str) -> str:
    """
    Get the climate of a given country.
    """
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content=f"What is the climate in {country}?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content 

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

def print_spy_node(state: AgentState):
    print(f"\n--- DEBUG: Current Messages Count: {len(state['messages'])} ---")
    for msg in state['messages']:
        print(f"  - {msg.type}: {msg.content[:30]}...") # Print snippet of content
    return state # Pass through unchanged

# 4. Graph Construction
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
# Add this node to your graph flow
workflow.add_node("spy", print_spy_node)

# ToolNode is a prebuilt LangGraph component that handles the loop you wrote manually
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "agent")

# tools_condition is a smart edge that routes to 'tools' if tool_calls exist, else END
workflow.add_conditional_edges("agent", tools_condition)
# Insert it into your edges
workflow.add_edge("tools", "spy") 
workflow.add_edge("spy", "agent")
#workflow.add_edge("tools", "agent") # This edge is the "Feedback Loop" that turns a static script into an autonomous agent. Without this line, your agent would be a "one-shot" system that stops after executing a tool.


# Compile
app = workflow.compile()

# 1. Start with an initial state
state = {"messages": []}

print("--------------------------------------------------------------------------------")

result = app.invoke({"messages": [HumanMessage(content="What is the climate in India?")]})
# 2. First Turn
state["messages"].append(HumanMessage(content="What is the climate in India?"))
result = app.invoke(state)
state = result
#print(result["messages"][-1].content)

print("--------------------------------------------------------------------------------")

result = app.invoke({"messages": [HumanMessage(content="get capital of Franace")]})
# 3. Second Turn (It now 'remembers' the climate of India)
state["messages"].append(HumanMessage(content="get capital of Franace"))
result = app.invoke(state)
state = result  # <--- CRITICAL: Update again!
#print(result["messages"][-1].content)

print("--------------------------------------------------------------------------------")

result = app.invoke({"messages": [HumanMessage(content="Prime Minister of India?")]})
# 3. Second Turn (It now 'remembers' the climate of India)
state["messages"].append(HumanMessage(content="Prime Minister of India?"))
result = app.invoke(state)
state = result  # <--- CRITICAL: Update again!

#print(result["messages"][-1].content)

# messages = result["messages"]

print("------------------conversation history (messages)---------------------------------")
# Loop through ALL messages to see the conversation history
for msg in state["messages"]:
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