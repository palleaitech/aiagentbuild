# Import LLM wrappers for OpenAI and Google Gemini
from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI

# Load environment variables from a .env file
from dotenv import load_dotenv
import os

# Import LangGraph components for building stateful workflows
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate

# TypedDict lets us define a structured dictionary for state
from typing import TypedDict
from pydantic import BaseModel

# Load environment variables (like API keys) from .env file
load_dotenv()

# Fetch the OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

# Safety check: if no API key is found, raise an error
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Initialize OpenAI LLM with chosen model and temperature
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

# -------------------------------
# PromptManager Implementation
# -------------------------------
class PromptManager:
  def __init__(self): 
     # centralised prompt management for the application
     self.prompts = {
        "support system": ChatPromptTemplate.from_messages([
           ("system", "You are a helpful support agent. "),
            ("human", "{question}")
        ]),
        "travel_agent": ChatPromptTemplate.from_messages([
           ("system", "You are a travel agent. "),
            ("human", "plan a trip to {city} witha budget of {budget}.")
        ])
     }

  def get_prompt(self, name, **kwargs):
      """ Retrive and format by a name and keyword arguments. """
      if name not in self.prompts:
          raise ValueError(f"Prompt '{name}' not found.")
      return self.prompts[name].invoke(kwargs)
  
# -------------------------------
# Define State for LangGraph
# -------------------------------
class AgentState(TypedDict):
    task: str
    question: str
    city: str
    budget: str
    response: str

class SupportResponse(BaseModel):
    steps: list[str]
    notes: str

# -------------------------------
# Final Output (BaseModel)
# -------------------------------
class AgentOutput(BaseModel):
    task: str
    question: str
    city: str
    budget: str
    response: str | SupportResponse

# -------------------------------
# Usage Example
# -------------------------------
pm = PromptManager()

# -------------------------------
# Define Nodes
# -------------------------------

def support_system_node(state: AgentState) -> str:
    """ Get support from prompt manager and invoke LLM. """
    prompt = pm.get_prompt("support system", question=state["question"])
    response = llm_openai.invoke(prompt)
    return {"response": response.content}

def travel_agent_node(state: AgentState) -> str:
    """ Get travel plan from prompt manager and invoke LLM. """
    prompt = pm.get_prompt("travel_agent", city=state["city"], budget=state["budget"])
    response = llm_openai.invoke(prompt)
    return {"response": response.content}
# -------------------------------
# Build Graph
# -------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("support_system", support_system_node)
workflow.add_node("travel_agent", travel_agent_node)

# conditional branching which agent to invoke based on the task
def route_task(state: AgentState):
    if state["task"] == "support":
        return "support_system"
    elif state["task"] == "travel":
        return "travel_agent"
    else:
        return END
    
# Use add_conditional_edges instead of add_edge
workflow.add_conditional_edges(
    START,
    route_task,
    {
        "support_system": "support_system",
        "travel_agent": "travel_agent",
        END: END
    }
)   
workflow.add_edge("support_system", END)
workflow.add_edge("travel_agent", END)

# compile workflow to ensure all nodes and edges are valid
compiled_workflow = workflow.compile()

# -------------------------------
# Run Examples
# -------------------------------
result1 = compiled_workflow.invoke({
    "task": "support", 
    "question": "How do I reset my password?",
    "city": "",
    "budget": "", 
    "response": ""
    })

print("---------------------------------------------------------------------")
print("\n--- Support System Result ---")
print("Task:", result1["task"])
print("Question:", result1["question"])
print("Response:\n", result1["response"])

print("------------------PYDANTIC OUTPUT--------------------------------------")
support_result = AgentOutput(**result1)
print("\n--- Support System Result ---")
print(f"**Task:** {support_result.task}")
print(f"**Question:** {support_result.question}")
print("\n**Response:**\n")
print(support_result.response)

print("---------------------------------------------------------------------")

result2 = compiled_workflow.invoke({
    "task": "travel", 
    "question": "",
    "city": "Paris", 
    "budget": "$2000", 
    "response": ""
    })

print("---------------------------------------------------------------------")
support_result = AgentOutput(**result1)
print("\n--- Support System Result ---")
print("Task:", support_result.task)
print("Question:", support_result.question)
print("\n**Response:**\n")
print(support_result.response)

print("------------------PYDANTIC OUTPUT--------------------------------------")
travel_output = AgentOutput(**result2)
print("\n--- Travel Agent Result ---")
print(f"**Task:** {travel_output.task}")
print(f"**City:** {travel_output.city}")
print(f"**Budget:** {travel_output.budget}")
print("\n**Response:**\n")
print(travel_output.response)

print("---------------------------------------------------------------------")