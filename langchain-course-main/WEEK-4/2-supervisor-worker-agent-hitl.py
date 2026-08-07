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
# Supervisor Agent
# -------------------------------
class SupervisorAgent:
    def __init__(self, api_key, workers:dict):
        """
        workers:dict mapping worker names to aorker app objects
        Example: {"country_worker": country_worker, "politics_worker": politics_worker}
        """
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)
        self.workers = workers

    def route_task(self, user_prompt:str)->str:
        """
        Decide which worker should handle the task.
        Uses LLM reasoning to pick the right worker.
        """
        routing_prompt = f"""
        You are a supervisor agent.
        Available workers:
        - country_worker: Handles geography, capitals, climate, and country-related queries.
        - politics_worker: Handles political leaders, government roles, and political facts.

        Decide which worker should handle the following request:
        "{user_prompt}"

        Respond ONLY with the worker name.
        """
      
        decision = self.llm.invoke([HumanMessage(content=routing_prompt)])
        return decision.content.strip()
    
    def run(self, user_prompt:str, config):
        worker_name = self.route_task(user_prompt)
        if worker_name not in self.workers:
            return f" No suitable worker found for: {user_prompt}"
        
        worker = self.workers[worker_name]
        worker.invoke({"messages": [HumanMessage(content=user_prompt)]}, config=config)

        snapshot = worker.get_state(config)
        if snapshot.next == ('tools',):
            ai_msg = snapshot.values["messages"][-1]
            print(f"LLM wants a tool call:{ai_msg} ")
            user_input = input("Approve tool calls y/n: ").strip().lower()
            if user_input != 'y':
                return "Execution stopped by human"
            worker.invoke(None, config=config)

        while True:
            snapshot = worker.get_state(config)
            if not snapshot.next:
                break
            worker.invoke(None, config=config)

        final_snapshot = worker.get_state(config)
        final_msg = final_snapshot.values["messages"][-1]
        return f"[{worker_name}]->{final_msg.content}"
    
# -------------------------------
# Build the workflow graph
# -------------------------------

def create_worker_agent(api_key, tools):
    llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

    def call_model(state: AgentState):
        response = llm_openai.invoke(state["messages"])   # Run LLM with current messages
        return {"messages": [response]}                       # Return updated messages

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)                   # Agent node (LLM execution)
    workflow.add_node("tools", ToolNode(tools))              # Tools node (executes defined functions)
    workflow.add_edge(START, "agent")                        # Start → Agent
    workflow.add_conditional_edges("agent", tools_condition) # Agent → Tools if tool calls exist, else END
    workflow.add_edge("tools", "agent")                      # Tools → Agent (loop back after tool execution)
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["tools"])

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
    #llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

    country_worker = create_worker_agent(api_key, [get_capital_of_country, get_climate_of_country])
    politics_worker = create_worker_agent(api_key, [get_prime_minister_of_india])

    workers = {
        "country_worker":country_worker,
        "politics_worker":politics_worker
    }

    supervisor = SupervisorAgent(api_key, workers)

    config = {"configurable": {"thread_id": "supervisor-session-1"}}
    

    print(supervisor.run("Use the get_climate_of_country tool to tell me the climate of India.", config))
    print(supervisor.run("What is the capital of France?", config))
    print(supervisor.run("Prime Minister of India?", config))

'''
in this code why supervisor is just a pythnon calss and worker agents are function ?
why supervosor agent is not part of the stategraph ?
teach me when agent defined as class or function. so that i can design my self next time

Workers (StateGraph) = Assembly line machines. Each machine has a workflow (input → process → output).

Supervisor (Class) = Factory manager. Decides which machine should handle which job. The manager doesn’t stand on the assembly line; they assign tasks.


workflow = StateGraph(AgentState)
...
return workflow.compile()
You’re not just returning a function — you’re returning a compiled LangGraph workflow object.

That object is:

A graph runtime: it knows about nodes, edges, and state transitions.

Callable: you can run it with .invoke() or .stream().

Self‑contained: it manages its own state, checkpoints, and execution loop.

So in practice:

create_worker_agent(...) returns a LangGraph workflow object.

That object behaves like an agent: you can invoke it, inspect its state, and it will run the LLM + tools loop automatically.

'''