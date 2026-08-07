# Import required modules
from langchain.tools import tool                     # Decorator to define custom tools callable by the agent
from typing import Annotated, Optional, Optional, TypedDict              # For structured state typing
import operator                                      # Used to accumulate messages in state
from langgraph.graph import StateGraph, START, END   # Core graph framework for agent workflow
from langgraph.prebuilt import ToolNode, tools_condition  # Prebuilt tool execution + routing logic
from langchain_openai import ChatOpenAI              # OpenAI LLM integration
from langchain_core.messages import (SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage)
from langgraph.checkpoint.memory import MemorySaver  # Checkpointer to persist agent state
from dotenv import load_dotenv                       # Load environment variables from .env file
import os
# --- FastAPI Imports ---
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Annotated, TypedDict  # Ensure Optional is imported

from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends, HTTPException
import datetime



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
    next_worker: str   # ✅ add this field

# -------------------------------
# Master Graph
# -------------------------------
def create_master_graph(api_key, workers: dict):
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)
  
    def master_router(state: AgentState):
        user_prompt = state["messages"][-1].content
        routing_prompt = f"""
        You are a Master agent.
        Available workers:
        - country_worker: Handles geography, capitals, climate, and country-related queries.
        - politics_worker: Handles political leaders, government roles, and political facts.

        Decide which worker should handle the following request:
        "{user_prompt}"

        Respond ONLY with the worker name.
        """
        decision = llm.invoke([
             SystemMessage(content="Respond ONLY with one of: country_worker, politics_worker"),
             HumanMessage(content=routing_prompt)])
      
        return {"next_worker": decision.content.strip()}

    graph = StateGraph(AgentState)
    graph.add_node("master", master_router)

    # Define wrapper nodes for workers to correctly pass state and return messages
    def make_worker_node(worker_app, worker_name):
        def worker_node(state: AgentState):
            # Give the subgraph its own thread configuration so it doesn't collide with the master thread
            sub_config = {"configurable": {"thread_id": f"sub-{worker_name}"}}
            
            # Pass only the latest human message or the relevant message history to avoid duplication
            latest_message = state["messages"][-1]
            
            result = worker_app.invoke({"messages": [latest_message]}, config=sub_config)
            return {"messages": result["messages"]}
        return worker_node

    # Add worker nodes and their terminal edges once
    for name, worker in workers.items():
        graph.add_node(name, make_worker_node(worker, name))
        graph.add_edge(name, END)
    
    # Edges: START → Master → Conditional Worker → END
    graph.add_edge(START, "master")
    graph.add_conditional_edges(
        "master", 
        lambda state: state["next_worker"], 
        list(workers.keys())
    )

    return graph.compile()

# -------------------------------
# Build the workflow graph
# -------------------------------

def create_worker_agent(api_key, tools):
  llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

  def call_model(state: AgentState):
      response = llm_openai.invoke(state["messages"])
      return {"messages": [response]}  # ✅ Return raw response instead of wrapping in AIMessage(content=...)

  workflow = StateGraph(AgentState)
  workflow.add_node("agent", call_model)
  workflow.add_node("tools", ToolNode(tools))
  workflow.add_edge(START, "agent")
  workflow.add_conditional_edges("agent", tools_condition)
  workflow.add_edge("tools", "agent")
  workflow.add_edge("agent", END)

  checkpointer = MemorySaver()
  return workflow.compile(checkpointer=checkpointer) # (Note: removed interrupt_before inside worker for clean master execution, or keep if needed)

# =====================================================================
# 4. RUNTIME EXECUTION SIMULATION
# =====================================================================
#if __name__ == "__main__":

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

master_graph  = create_master_graph(api_key, workers)

database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the table structure for chat sessions
class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    thread_id = Column(String, primary_key=True, index=True)
    user_prompt = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    routed_worker = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Automatically create the table in PostgreSQL
Base.metadata.create_all(bind=engine)

# Dependency to handle DB sessions cleanly in FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# create FastAPI app instance
app = FastAPI(title="Multi-Agent-wroker_API", version="1.0")


class QueryRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = "default-session"

@app.post("/chat")
def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)): 
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Invoke the compiled master graph
        result = master_graph.invoke(
            {"messages": [HumanMessage(content=request.prompt)]}, 
            config=config
        )
        
        routed_worker = result.get("next_worker")
        ai_response = result["messages"][-1].content
        
        # ✅ SAVING TO POSTGRESQL (The missing piece)
        db_session_entry = ChatSessionModel(
            thread_id=request.thread_id,
            user_prompt=request.prompt,
            ai_response=ai_response,
            routed_worker=routed_worker
        )
        db.merge(db_session_entry)
        db.commit()
        
        return {
            "status": "success",
            "thread_id": request.thread_id,
            "question": request.prompt,
            "routed_worker": routed_worker,
            "response": ai_response
        }
    except Exception as e:
        db.rollback() # Rollback transaction if something crashes
        print(f"\n[ERROR CRASH]: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))

# 1. READ: Get a specific chat session by thread_id
@app.get("/chats/{thread_id}")
def get_chat_session(thread_id: str, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    return {
        "thread_id": session_record.thread_id,
        "user_prompt": session_record.user_prompt,
        "ai_response": session_record.ai_response,
        "routed_worker": session_record.routed_worker,
        "created_at": session_record.created_at
    }

# 2. UPDATE: Modify an existing chat session's prompt or response
class ChatUpdateRequest(BaseModel):
    new_response: str

@app.put("/chats/{thread_id}")
def update_chat_session(thread_id: str, request: ChatUpdateRequest, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    session_record.ai_response = request.new_response
    db.commit()
    
    return {"status": "success", "message": f"Session {thread_id} updated successfully."}

# 3. DELETE: Remove a chat session from PostgreSQL
@app.delete("/chats/{thread_id}")
def delete_chat_session(thread_id: str, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    db.delete(session_record)
    db.commit()
    
    return {"status": "success", "message": f"Chat session {thread_id} deleted successfully."}

# # Define a list of test questions
# questions = [
#     "Use the get_climate_of_country tool to tell me the climate of India.",
#     "What is the capital of France?",
#     "Prime Minister of India?"
# ]

# # Run each question cleanly through the master graph
# for q in questions:
#     print(f"\n--- QUESTION: {q} ---")
#     result = master_graph.invoke({"messages": [HumanMessage(content=q)]})
#     print(f"Routed Worker: {result.get('next_worker')}")
#     print(f">>> AI ANSWER: {result['messages'][-1].content}")


"""
Code
Central StateGraph
   ├── Master Node (LLM routing)
   │       ↓ conditional edges
   ├── Country Worker (subgraph)
   │       └── Agent → Tools → Agent → End
   └── Politics Worker (subgraph)
           └── Agent → Tools → Agent → End
State: Shared across the whole graph (messages, variables).

Nodes: Master node + worker subgraphs.

Edges: Conditional edges route from Master → chosen worker → back to Master or End.

"""