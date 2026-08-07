# Import LLM wrappers for OpenAI and Google Gemini
from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI

# Load environment variables from a .env file
from dotenv import load_dotenv
import os

# Import LangGraph components for building stateful workflows
from langgraph.graph import StateGraph, START, END

# TypedDict lets us define a structured dictionary for state
from typing import TypedDict


# Load environment variables (like API keys) from .env file
load_dotenv()

# Fetch the OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

# Safety check: if no API key is found, raise an error
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Initialize OpenAI LLM with chosen model and temperature
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)


# Define the state structure for the workflow
class TravelState(TypedDict):
    city: str
    weather: str
    temperature: str
    booking_status: str
    activity: str


# Node: decide weather based on city
def check_weather_node(state: TravelState) -> str:
    return {"weather": "rainy" if state["city"].lower() == "london" else "sunny"}
    
# Node: decide activity based on weather
def decide_activity_node(state: TravelState) -> str:
    if state["weather"] == "rainy":
        return {"activity": "visit museum"}
    else:
        return {"activity": "go hiking"}

# Node: simulate booking a flight
def book_flight_node(state: TravelState) -> str:
    return {"booking_status": "flight booked successfully"}

# Node: simulate booking a hotel
def book_hotel_node(state: TravelState) -> str:
    return {"booking_status": "hotel booked successfully"}


# Build the workflow graph with defined state
workflow = StateGraph(TravelState)    

# Add nodes (functions) to the graph
workflow.add_node("check_weather", check_weather_node)
workflow.add_node("decide_activity", decide_activity_node)
workflow.add_node("book_flight", book_flight_node)
workflow.add_node("book_hotel", book_hotel_node)

# Define edges (execution order of nodes)
workflow.add_edge(START, "check_weather")       # Start → check_weather
workflow.add_edge("check_weather", "decide_activity")  # After weather → decide activity
workflow.add_conditional_edges(
    "decide_activity",
    lambda state: "book_flight" if state["weather"] == "sunny" else "book_hotel",
    {
        "book_flight": "book_flight",
        "book_hotel": "book_hotel",
    },
)
workflow.add_edge("book_flight", END)         # After flight → book hotel
workflow.add_edge("book_hotel", END)                   # End after hotel booking


# Compile the workflow into an executable graph
compiled_workflow = workflow.compile()

# Optional: visualize the graph as a Mermaid diagram (PNG output)
compiled_workflow.get_graph().draw_mermaid_png(output_file_path="simple_state_graph.png")

# Run the workflow with initial state values
result = compiled_workflow.invoke({
    "city": "London",
    "weather": "",
    "temperature": 29.3,
    "booking_status": "confirmed",   
    "activity": ""
})

# Print the final state after workflow execution
print("Final Result:", result)
