# Import required modules
from langchain.tools import tool                     # Decorator to define custom tools callable by the agent
from typing import Annotated, Optional, Optional, TypedDict              # For structured state typing
import operator

from langchain_core import documents                                      # Used to accumulate messages in state
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

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends, HTTPException
import datetime

from pgvector.sqlalchemy import Vector
from langchain_openai import OpenAIEmbeddings

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

@tool
def search_internal_docs(query: str) -> str:
  """
    Search internal curriculum documents and guidelines using vector similarity.
    """

  db = SessionLocal()
  try:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)
    query_vector = embeddings.embed_query(query)  

    # query pgvector for closest matching chunks using cosine similarity
    result = db.query(DocumentChunkModel).order_by(DocumentChunkModel.embedding.cosine_distance(query_vector)).limit(50).all()

    if not result:
        return "No relevant documents found." 
    return "\n\n".join(r.content for r in result)
  finally:
    db.close()

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
tools = [get_prime_minister_of_india, get_capital_of_country, get_climate_of_country, search_internal_docs]

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
        - rag_worker: Handles internal curriculum documents, bootcamp schedules, and private knowledge.

        Decide which worker should handle the following request:
        "{user_prompt}"

        Respond ONLY with the exact worker name: country_worker, politics_worker, or rag_worker.
        """
        decision = llm.invoke([
             SystemMessage(content="Respond ONLY with one of: country_worker, politics_worker, rag_worker"),
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

# # Validate API key presence
if not api_key:
  raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Initialize the LLM (GPT-4o) with given parameters
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

country_worker = create_worker_agent(api_key, [get_capital_of_country, get_climate_of_country])
politics_worker = create_worker_agent(api_key, [get_prime_minister_of_india])
rag_worker = create_worker_agent(api_key, [search_internal_docs])

workers = {
    "country_worker":country_worker,
    "politics_worker":politics_worker,
    "rag_worker":rag_worker
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

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        # Check if chunks already exist; if not, ingest automatically on startup
        count = db.query(DocumentChunkModel).count()
        if count == 0:
            print("Database is empty. Automatically ingesting PDF document...")
            ingest_document("agentic-ai-developer-bootcamp-curriculum.pdf")
        else:
            print(f"Database already contains {count} chunks. Skipping ingestion.")
    except Exception as e:
        print(f"Startup ingestion note: {e}")
    finally:
        db.close() 

@app.post("/chat")
def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)): 
    #try:
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
    # except Exception as e:
    #     db.rollback() # Rollback transaction if something crashes
    #     print(f"\n[ERROR CRASH]: {str(e)}\n")
    #     raise HTTPException(status_code=500, detail=str(e))

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

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"  # 👈 Fixed typo (__tablename__ instead of __table_name__)
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # Ensure Integer or matching type
    content = Column(Text, nullable=False)
    embedding = Column(Vector(3072), nullable=False)  # 👈 Changed to 3072 to match text-embedding-3-large
    source_file = Column(Text, nullable=True)

# Automatically create the new table in PostgreSQL
Base.metadata.create_all(bind=engine)

def ingest_document(pdf_path: str):
    """
    Load a PDF, split it into chunks, embed each chunk, and save to PostgreSQL.
    """

    # Load the PDF
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    db = SessionLocal()

    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)

        for i, chunk in enumerate(chunks):
          vector = embeddings.embed_query(chunk.page_content)

          doc_entry = DocumentChunkModel(
              content=chunk.page_content,
              embedding=vector,
              source_file=os.path.basename(pdf_path)
          )
          db.add(doc_entry)
    
        db.commit()
        print(f"Successfully ingested {len(chunks)} chunks from {pdf_path}")
    finally:
      db.close()

#=====================================================================================================#
# running as normal python file, not as FastAPI server, so we can ingest a sample document for testing
#=====================================================================================================#
if __name__ == "__main__":
    # for docker compose, we can use a relative path to the PDF file in the same directory as this script
    ingest_document("agentic-ai-developer-bootcamp-curriculum.pdf")
    print("Test document successfully added to PostgreSQL!")  

    # To view the actual text chunks and their corresponding embedding vectors stored in your PostgreSQL database
    db = SessionLocal()
    try:
        # Fetch all stored document chunks from PostgreSQL
        chunks = db.query(DocumentChunkModel).all()
        print(f"Total chunks found in database: {len(chunks)}\n")
        
        for chunk in chunks:
            print(f"--- Chunk ID: {chunk.id} | Source: {chunk.source_file} ---")
            print(f"Content Preview: {chunk.content[:150]}...")
            print(f"Vector Embedding Length: {len(chunk.embedding)} dimensions")
            print(f"First 5 vector values: {chunk.embedding[:5]}\n")
    finally:
        db.close()

# uvicorn 1-rag-psql-pgvector:app --reload
# "What is covered in Week 3 of the bootcamp?",
# docker compose exec web python -c "from docker_rag_psql_pgvector import ingest_document; ingest_document('agentic-ai-developer-bootcamp-curriculum.pdf')"

"""
Here is the complete list of all 3 components of your stack, including what they are, their purpose, and how to verify each one:

1. The Database: postgres_vector_db
What it is: A PostgreSQL instance with the pgvector extension installed, acting as your persistent data store and vector database for the agentic RAG course.

How to verify: Run this command in your terminal to check the connection and see your tables (chat_sessions, document_chunks):

Bash
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "\dt"
2. The Backend Application: agentic_fastapi_app
What it is: Your FastAPI backend server running your RAG application code and LLM/agent workflows.

How to verify: Open your browser and go to your Swagger documentation endpoint:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

3. The Management GUI: pgadmin_gui
What it is: A visual administration tool for PostgreSQL that lets you inspect your tables, monitor rows, and run custom queries.

How to verify: Open your browser and go to your configured pgAdmin port:

//------------------
docker compose down -v
docker compose build --no-cache
docker compose up -d
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec web python docker_rag_psql_pgvector.py

docker rm pgadmin_gui
docker logs agentic_fastapi_app
docker logs postgres_vector_db
docker logs pgadmin_gui
docker port pgadmin_gui

With Docker (What you just did): Because pgAdmin runs inside an isolated container, it cannot see your computer's outside network by default. That is why you had to expose and map a port (like mapping container port 80 to your host port 5051) so your web browser could reach it via http://localhost:5051.

Running Directly on Local (Without Docker): If you install pgAdmin directly on your Windows machine as a native desktop application, you just double-click the app icon, and it opens right in your browser (usually on port 80 or 5051) without needing any manual port mapping configuration.

Both methods do the exact same thing, but Docker requires that explicit port bridge (5051:80) so the container can talk to your host machine!

All containers (postgres_vector_db, pgadmin_gui, and agentic_fastapi_app) are now successfully up and running.

You can access pgAdmin in your browser at:
http://localhost:5051

To verify that each of your three Docker containers is running properly and communicating as expected, you can use the following verification methods for each service:

1. Verify agentic_fastapi_app (FastAPI Server)
Status Check (Docker Logs): Check if the application started successfully and is listening for requests:

Bash
docker logs agentic_fastapi_app
Endpoint / Browser Check: Open your web browser or test via curl at:

Swagger UI Documentation: http://localhost:8000/docs

Interactive Chat Endpoint test: Send a POST request to http://localhost:8000/chat with your JSON payload.

2. Verify postgres_vector_db (PostgreSQL + pgvector)
Status Check (Docker Logs): Check if the database instance is ready to accept connections:

Bash
docker logs postgres_vector_db
Interactive CLI / Connection Check: Run a quick command inside the database container to verify connection and check that your tables (chat_sessions and document_chunks) exist:

Bash
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "\dt"

3. Verify pgadmin_gui (pgAdmin Interface)
Status Check (Docker Logs): Check if the web GUI initialized properly:

Bash
docker logs pgadmin_gui
Browser Access Check:

Open your browser and go to http://localhost:5051.

Log in using your credentials (admin@admin.com / password).

Verify that you can register your server using host db, database agent_db, user postgres, and password venkatpalle to visually inspect your tables and vector columns.


"""