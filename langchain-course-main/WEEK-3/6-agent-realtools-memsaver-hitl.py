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
from pydantic import BaseModel, Field
import requests
import os

# Load environment variables (API key stored in .env file)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Validate API key presence
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Initialize the LLM (GPT-4o) with given parameters
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

# ------------------------------------------------------------------------------------
# Define tools (simple functions callable by the agent)
# ------------------------------------------------------------------------------------

# Weather Tool
# Define schema for tool input
class WeatherInput(BaseModel):
    city: str = Field(..., description="Name of the city to get weather for")

@tool(args_schema=WeatherInput)
def get_weather(city: str) -> str:
    """
    Get current weather for a given city using Open-Meteo API.
    """
    try:
        # Example: Open-Meteo free API (no key required)
        url = f"https://api.open-meteo.com/v1/forecast?latitude=12.9716&longitude=77.5946&current_weather=true"
        response = requests.get(url, timeout=5)
        data = response.json()

        temp = data["current_weather"]["temperature"]
        condition = data["current_weather"]["weathercode"]
        return f"Weather in {city}: {temp}°C, code {condition}"
    except Exception as e:
        return f"Error fetching weather for {city}: {str(e)}"

# ------------------------------------------------------------------------------------
# Local dictionary fallback
# ------------------------------------------------------------------------------------    
COUNTRY_INFO = {
    "india": {"capital": "New Delhi", "currency": "INR", "region": "Asia"},
    "france": {"capital": "Paris", "currency": "EUR", "region": "Europe"},
    "us": {"capital": "Washington, D.C.", "currency": "USD", "region": "North America"}
}

# Country Info Tool
class CountryInput(BaseModel):
    country: str = Field(..., description="Country name to get information about")

@tool(args_schema=CountryInput)
def get_country_info(country: str) -> str:
    """
    Get information about a country using REST Countries API.
    """
    try:
        # Normalize input
        country_key = country.lower()

        url = f"https://restcountries.com/v3.1/name/{country.lower()}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()[0]

        capital = data.get("capital", ["Unknown"])[0]
        population = data.get("population", "Unknown")
        region = data.get("region", "Unknown")
        currency = list(data.get("currencies", {}).keys())[0]

        return f"{country.title()} → Capital: {capital}, Population: {population}, Region: {region}, Currency: {currency}"
    except Exception:
        # Step 2: Fallback to local dictionary
        if country_key in COUNTRY_INFO:
            info = COUNTRY_INFO[country_key]
            return (f"{country.title()} → Capital: {info['capital']}, "
                    f"Currency: {info['currency']}, Region: {info['region']}")
        return f"Information for {country} not available."
    
# ------------------------------------------------------------------------------------    
# Local dictionary fallback - HOLIDAYS
# ------------------------------------------------------------------------------------    
HOLIDAYS = {
    ("IN", 2026): [
        "2026-01-26 Republic Day",
        "2026-08-15 Independence Day",
        "2026-10-02 Gandhi Jayanti"
    ],
    ("US", 2026): [
        "2026-07-04 Independence Day",
        "2026-11-26 Thanksgiving",
        "2026-12-25 Christmas Day"
    ]
}
    

# Public Holidays Tool
class HolidayInput(BaseModel):
    country: str = Field(..., description="Country code (e.g., IN, US, GB)")
    year: int = Field(..., description="Year to fetch public holidays for")

@tool(args_schema=HolidayInput)
def get_public_holidays(country: str, year: int) -> str:
    """
    Get public holidays for a given country and year using Nager.Date API.
    """
    try:
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country.upper()}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        holidays = response.json()

        if not holidays:
            return f"No holidays found for {country} in {year}."

        # Format top 5 holidays for readability
        holiday_list = [
            f"{h['date']} - {h['localName']}" for h in holidays[:5]
        ]
        return f"Top holidays in {country} for {year}:\n" + "\n".join(holiday_list)

    except Exception as e:
      # Step 2: Fallback to local dictionary
      key = (country.upper(), year)
      if key in HOLIDAYS:
        holiday_list = HOLIDAYS[key]
        return f"Fallback holidays in {country.upper()} for {year}:\n" + "\n".join(holiday_list)
      return f"Holiday information not available for {country.upper()} in {year}."


# Collect all tools in a list for binding
tools = [get_weather, get_country_info, get_public_holidays]

# -------------------------------
# Define agent state
# -------------------------------
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]  # Holds conversation messages
    city: str                                             # Example extra field

# Bind tools to the LLM so it can call them directly
llm_with_tools = llm_openai.bind_tools(tools)

# -------------------------------
# Define the agent node (LLM execution)
# -------------------------------
def call_model(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])   # Run LLM with current messages
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
app = workflow.compile(checkpointer=checkpointer, interrupt_before=["agent"])

app.get_graph().draw_mermaid_png(output_file_path="6-agent-realtools-memsaver-hitl.png")

# -------------------------------
# Run function with human approval step
# -------------------------------
def run_with_approval(prompt: str, config):
    print(f"\n--- Turn: {prompt} ---", flush=True)

    # Step 1: Start execution with human message
    app.invoke({"messages": [HumanMessage(content=prompt)]}, config=config)

    # Step 2: Pause before agent runs (approval required)
    snapshot = app.get_state(config)
    if snapshot.next == ('agent',):
        user_input = 'y' #input("Type 'y' to approve, 'n' to stop: ").strip().lower()
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

# -------------------------------
# Test runs (force agent to use tools)
# -------------------------------
config = {"configurable": {"thread_id": "session-test-1"}}

run_with_approval("get wheather for {kolkata}", config)
run_with_approval("get information about india", config)
run_with_approval("get public holidays IN 2026", config)

'''
Here’s a crisp set of short notes showing how your code embodies **Reactive**, **ReAct**, and **Deliberative** paradigms:

---

### ⚡ Reactive
- **Definition:** Immediate stimulus → response, no planning.  
- **In your code:**  
  - User query → `call_model()` → tool executes → answer.  
  - Example: “Weather in Kolkata” → directly calls `get_weather`.  
- **Key trait:** Fast, reflex‑like, one‑shot decision.

---

### 🔄 ReAct (Reason + Act loop)
- **Definition:** Alternates between short reasoning bursts and tool use.  
- **In your code:**  
  - LLM decides → tool executes → LLM interprets → may call another tool → repeat.  
  - Loop: `agent → tools → agent → tools …` until END.  
- **Key trait:** Iterative reasoning + acting, adaptive mid‑task.

---

### 🧠 Deliberative
- **Definition:** Builds internal model, plans before acting.  
- **In your code:**  
  - `MemorySaver` stores state → agent can recall past context.  
  - Human approval (`interrupt_before`) adds deliberation before execution.  
- **Key trait:** Thoughtful, checkpointed, goal‑aware.

---

✅ **Summary:**  
Your agent is a **hybrid**:  
- **Reactive core** (tool calls on demand),  
- **ReAct loop** (reason → act → interpret),  
- **Deliberative overlays** (memory + human approval).  

✅ Summary:  
Your agent is a hybrid:

Reactive at its core,

ReAct loop for iterative reasoning,

Deliberative overlays with memory + human checkpoints.

'''
'''
📚 Architectural Classification
Agentic AI Architecture (because it combines LLM reasoning + tool use + memory + workflow control).

Graph‑based Workflow Architecture (LangGraph is explicitly graph‑driven).

Reactive/Deliberative Hybrid (reactive tool calls, deliberative checkpoints).

Human‑in‑the‑Loop Agent (interrupt_before ensures approval before execution).


🧩 1. LLM Initialization
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

This line creates the LLM client — it’s the interface to GPT‑4o.
At this point, the model is idle; it hasn’t yet received any messages or made decisions.

⚙️ 2. LLM Binding to Tools
llm_with_tools = llm_openai.bind_tools(tools)

Here, you’re extending the LLM’s capabilities by binding tool definitions.
This means the model can now decide to call get_weather, get_country_info, or get_public_holidays when appropriate.
It’s the first step toward making the LLM agentic — able to act, not just chat.

🧠 3. LLM Decision Point — call_model()
def call_model(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

This is the core LLM interaction:

The LLM receives the conversation history (state["messages"]).

It analyzes the latest user message.

It decides whether to:

Answer directly (no tool call), or

Generate a tool call instruction (e.g., {"tool": "get_weather", "parameters": {"city": "Kolkata"}}).

This is the decision phase — the LLM is reasoning and planning.


🔄 4. Tool Execution Phase
If the LLM’s output contains a tool call, the ToolNode executes it:
workflow.add_node("tools", ToolNode(tools))

The tool runs (e.g., calls an API), returns data, and sends a ToolMessage back into the graph.

🗣️ 5. LLM Response Interpretation
After tool execution, control loops back to the agent node:

workflow.add_edge("tools", "agent")

Now the LLM sees the tool’s output and synthesizes a final user-facing message:

“The weather in Kolkata is 22.5°C and partly cloudy.”

This is the response phase — the LLM interprets structured tool results and turns them into natural language.


'''


'''

1. The "Graph" vs. The "Runner"
Think of your workflow (the code where you added nodes and edges) as a set of blueprints for a factory.

app = workflow.compile(...): This turns the blueprints into a working factory.

run_with_approval: This is your factory manager.

When you write app.invoke(...) inside run_with_approval, you are definitely running the graph. But you are running it in a way that allows you to "reach in" and pause it.

2. How the link actually works
Normally, you might just run
# The "normal" way
app.invoke({"messages": [...]})

This tells the graph: "Start, run until you reach the END, and then give me the final output."

When you use run_with_approval, you are doing this:

Start: You trigger app.invoke. The graph starts moving.

Pause: Because you have interrupt_before=["agent"], the factory stops right at the gate. The graph state is now "paused" in the database (via MemorySaver).

Hold: The app.invoke function inside your runner finishes because it hit the interrupt, returning control back to your Python script.

Manage: Now your script is running, not the graph. This is where your input() or logic lives.

Resume: When you call app.invoke(None, ...) inside your runner, you are telling the factory: "The obstacle is gone; please continue from where you left off."

To extend your analogy further:

The Blueprint (workflow): The map of the roads the car can take.

The Engine (app.invoke): The motor that actually moves the car forward along those roads.

The Driver (run_with_approval): You. You have your hand on the gear shift. You decide when to start the engine, when to stop at a red light (the interrupt), and when to press the gas again (the resume).

Because you are the driver, you have control over the speed and safety of the journey.

Without the "driver" function, the engine would just drive at full speed from point A to point B without letting you check the map, look at the gas gauge, or decide if you actually want to take that turn.





🔎 Putting it together
User asks → “get weather for Kolkata.”

call_model → LLM decides: “I need to call get_weather.”

Tool node executes → runs get_weather("kolkata"), gets JSON result.

Back to call_model → LLM reads tool result and produces natural language answer.

Final output → “Weather in Kolkata is 22.5°C, partly cloudy.”

✅ Key Insight
call_model itself is not the agent — it’s just the LLM node.

The agent is the whole graph:

call_model (decide what to do)

tool_execution (do it)

loop back to call_model (interpret result)

produce final answer.

So the "messages": [response] coming out of call_model can contain either:

A tool call instruction (which the tool node executes), or

A final answer (if no tool is needed).

'''
