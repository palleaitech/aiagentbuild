# =====================================================================
# Imports & Setup
# =====================================================================
import os
import datetime
import uuid
import operator
import traceback
from typing import Annotated, List, Optional, TypedDict

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from pgvector.sqlalchemy import Vector

from langchain.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from dotenv import load_dotenv
import psycopg

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

# =====================================================================
# Database Setup
# =====================================================================
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    thread_id = Column(String, primary_key=True, index=True)
    user_prompt = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    routed_worker = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(3072), nullable=False)
    source_file = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# Tools Definition
# =====================================================================
@tool
def search_internal_docs(query: str) -> str:
    """Search internal curriculum documents and guidelines using vector similarity."""
    db = SessionLocal()
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)
        query_vector = embeddings.embed_query(query)  
        result = db.query(DocumentChunkModel).order_by(DocumentChunkModel.embedding.cosine_distance(query_vector)).limit(50).all()
        if not result:
            return "No relevant documents found." 
        return "\n\n".join(r.content for r in result)
    finally:
        db.close()

@tool
def get_prime_minister_of_india() -> str:
    """Get the current Prime Minister of India."""
    return "Narendra Modi"

@tool
def get_capital_of_country(country: str) -> str:
    """Get the capital of a given country."""
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

@tool
def get_climate_of_country(country: str) -> str:
    """Get the climate of a given country."""
    return "cool and hot" 

tools = [get_prime_minister_of_india, get_capital_of_country, get_climate_of_country, search_internal_docs]

# =====================================================================
# Agent State Schema
# =====================================================================
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    city: str
    next_worker: str
    input: str
    plan: List[str]
    current_step_index: int
    execution_history: Annotated[List[str], operator.add]
    critique: str
    final_output: str    

# =====================================================================
# Planner-Executor-Critic Workflow Graph
# =====================================================================
def human_approval_node(state: AgentState):
    human_decision = interrupt({
        "plan": state.get("plan"),
        "message": "Please review the plan. Resume with 'approved' or provide an updated list of steps."
    })
    
    updated_plan = human_decision if isinstance(human_decision, list) and len(human_decision) > 0 else state.get("plan", [])
    
    return Command(
        update={"plan": updated_plan},
        goto="executor"
    )

def create_human_in_the_loop_graph(api_key, checkpointer):
    def planner_node(state: AgentState):
        messages = state.get("messages", [])
        user_prompt = messages[-1].content if messages else state.get("input", "Perform the task.")
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert planner. Break down the user's request into a short, concise sequential list of MAXIMUM 4 numbered steps."),
            ("user", "Goal: {input}")
        ])
        chain = prompt | ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=api_key)
        response = chain.invoke({"input": user_prompt})
        steps = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
        return {
            "input": user_prompt,
            "plan": steps, 
            "current_step_index": 0,
            "messages": [HumanMessage(content=f"Plan created with {len(steps)} steps.")]
        }

    def executor_node(state: AgentState):
        current_index = state["current_step_index"]
        current_step = state["plan"][current_index] if current_index < len(state["plan"]) else "Finalize itinerary"
        critique = state.get("critique", "")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a precise executor. Execute the current step. If there is critique/feedback from the critic, fix and adjust your output accordingly."),
            ("user", "Goal: {input}\nPlan: {plan}\nCurrent Step Index: {index}\nCurrent Step: {step}\nCritic Feedback: {critique}\nHistory: {history}")
        ])
        chain = prompt | ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=api_key)
        response = chain.invoke({
            "input": state["input"],
            "plan": state["plan"],
            "index": current_index,
            "step": current_step,
            "critique": critique,
            "history": state["execution_history"]
        })
        result = f"Step {current_index}: {current_step} | Output: {response.content}"
        return {"execution_history": [result]}

    def critic_node(state: AgentState):
        history = state.get("execution_history", [])
        if not history:
            return {"critique": "APPROVED", "current_step_index": state.get("current_step_index", 0)}
        
        latest_execution = history[-1]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a strict quality control critic. Evaluate if the latest execution step successfully accomplished its goal. Reply with 'APPROVED' if good, or provide feedback for correction."),
            ("user", "Goal: {input}\nLatest Execution: {execution}")
        ])
        chain = prompt | ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=api_key)
        response = chain.invoke({
            "input": state.get("input", ""),
            "execution": latest_execution
        })
        critique = response.content.strip()
        current_index = state.get("current_step_index", 0)
        next_index = current_index + 1 if "APPROVED" in critique.upper() else current_index
        return {"critique": critique, "current_step_index": next_index}

    def should_continue(state):
        current_index = state.get("current_step_index", 0)
        plan = state.get("plan", [])
        if current_index >= len(plan):
            return "finish"
        return "continue"

    def evaluation_node(state: AgentState):
        """
        Evaluates the final execution results and history to ensure 
        high quality and strict alignment with the original user goal.
        """
        user_prompt = state.get("input", "")
        history = state.get("execution_history", [])
        final_summary = "\n".join(history) if history else "No execution history recorded."

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an objective AI response evaluator. Grade the execution history on a scale of 1-5 for accuracy, completeness, and helpfulness. Format your output as: SCORE: [1-5] | RATIONALE: [your brief note]"),
            ("user", "Original Goal: {prompt}\nExecution History:\n{history}")
        ])
        
        chain = prompt | ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=api_key)
        evaluation_result = chain.invoke({"prompt": user_prompt, "history": final_summary})
        
        print(f"\n--- PLANNER EVALUATION REPORT ---\n{evaluation_result.content}\n-----------------------------------\n")
        
        return {"critique": evaluation_result.content}

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("evaluator", evaluation_node)
    
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "human_approval")
    graph.add_edge("human_approval", "executor")
    graph.add_edge("executor", "critic")
    graph.add_conditional_edges("critic", should_continue, {"continue": "executor", "finish": "evaluator"})
    # Evaluator is the final step before ending
    graph.add_edge("evaluator", END)

    return graph.compile(checkpointer=checkpointer)

# Shared Checkpointer (Can be toggled to PostgresSaver next)
# Initialize PostgresSaver correctly using connection string
# Open a connection with autocommit=True so DDL commands and concurrent indexes can run freely
conn = psycopg.connect(database_url, autocommit=True)
checkpointer = PostgresSaver(conn)
checkpointer.setup()  # This will now create the internal tables without failing
planner_app = create_human_in_the_loop_graph(api_key=api_key, checkpointer=checkpointer)

# =====================================================================
# Master Graph & Workers
# =====================================================================
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

    def make_worker_node(worker_app, worker_name):
        def worker_node(state: AgentState):
            sub_config = {"configurable": {"thread_id": f"sub-{worker_name}"}}
            latest_message = state["messages"][-1]
            result = worker_app.invoke({"messages": [latest_message]}, config=sub_config)
            return {"messages": result["messages"]}
        return worker_node

    for name, worker in workers.items():
        graph.add_node(name, make_worker_node(worker, name))
        graph.add_edge(name, END)
    
    graph.add_edge(START, "master")
    graph.add_conditional_edges("master", lambda state: state["next_worker"], list(workers.keys()))

    return graph.compile()

def create_worker_agent(api_key, tools):
    llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key).bind_tools(tools)

    def call_model(state: AgentState):
        response = llm_openai.invoke(state["messages"])
        return {"messages": [response]} 

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    workflow.add_edge("agent", END)

    return workflow.compile(checkpointer=MemorySaver())

country_worker = create_worker_agent(api_key, [get_capital_of_country, get_climate_of_country])
politics_worker = create_worker_agent(api_key, [get_prime_minister_of_india])
rag_worker = create_worker_agent(api_key, [search_internal_docs])

workers = {
    "country_worker": country_worker,
    "politics_worker": politics_worker,
    "rag_worker": rag_worker
}

master_graph = create_master_graph(api_key, workers)

# =====================================================================
# FastAPI Application & Endpoints
# =====================================================================
app = FastAPI(title="Multi-Agent-Worker-API", version="1.0")

class QueryRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = "default-session"

class TaskRequest(BaseModel):
    goal: str
    city: Optional[str] = "Chennai"

class ResumeRequest(BaseModel):
    thread_id: str
    updated_plan: Optional[List[str]] = None

class ChatUpdateRequest(BaseModel):
    new_response: str

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
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

@app.post("/run-planner-agent")
async def run_planner_agent(request: TaskRequest):
    try:
        initial_state = {
            "messages": [HumanMessage(content=request.goal)],
            "city": request.city,
            "next_worker": "",
            "input": request.goal,
            "plan": [],
            "current_step_index": 0,
            "execution_history": [],
            "critique": "",
            "final_output": ""
        }
        
        thread_id = f"planner-session-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

        planner_app.invoke(initial_state, config=config)
        state = planner_app.get_state(config)
        
        if state.next:
            return {
                "status": "paused_for_approval",
                "thread_id": thread_id,
                "next_step": state.next,
                "generated_plan": state.values.get("plan"),
                "message": "Plan generated successfully. Review the plan and call /resume-planner-agent with this thread_id to proceed."
            }

        return {"status": "completed", "thread_id": thread_id, "result": state.values}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resume-planner-agent")
async def resume_planner_agent(request: ResumeRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}, "recursion_limit": 50}
        resume_value = request.updated_plan if (request.updated_plan and request.updated_plan != ["string"]) else "approved"

        planner_app.invoke(Command(resume=resume_value), config=config)
        final_state_snapshot = planner_app.get_state(config)

        return {"status": "completed", "thread_id": request.thread_id, "result": final_state_snapshot.values}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)): 
    config = {"configurable": {"thread_id": request.thread_id}}
    result = master_graph.invoke({"messages": [HumanMessage(content=request.prompt)]}, config=config)
    
    routed_worker = result.get("next_worker")
    ai_response = result["messages"][-1].content
    
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

@app.put("/chats/{thread_id}")
def update_chat_session(thread_id: str, request: ChatUpdateRequest, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    session_record.ai_response = request.new_response
    db.commit()
    return {"status": "success", "message": f"Session {thread_id} updated successfully."}

@app.delete("/chats/{thread_id}")
def delete_chat_session(thread_id: str, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    db.delete(session_record)
    db.commit()
    return {"status": "success", "message": f"Chat session {thread_id} deleted successfully."}

# =====================================================================
# Document Ingestion Helper
# =====================================================================
def ingest_document(pdf_path: str):
    """Load a PDF, split it into chunks, embed each chunk, and save to PostgreSQL."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    db = SessionLocal()

    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)

        for chunk in chunks:
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

if __name__ == "__main__":
    ingest_document("agentic-ai-developer-bootcamp-curriculum.pdf")
    print("Test document successfully added to PostgreSQL!")

# uvicorn 1-rag-psql-pgvector:app --reload
# uvicorn planner_excutr:app --reload
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
docker compose exec web python planner_excutr.py

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

"Write a step-by-step itinerary to explore historical locations in Chennai.",

pgadmin:
CREATE TABLE IF NOT EXISTS planner_sessions (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255),
    goal TEXT,
    plan TEXT,
    execution_history TEXT,
    critique TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

//------------------------------------------------------------------------------------------------
Overview of Your Services
Your project contains three main components:

PostgreSQL Database (postgres_vector_db): Stores your relational tables and vector embeddings using pgvector.

FastAPI Application (agentic_fastapi_app): The backend running your multi-agent workflows, RAG tools, and endpoints (e.g., /docs, /chat).

pgAdmin GUI (pgadmin_gui): A web interface to view and manage your PostgreSQL database visually.

Approach 1: Running with Docker (Recommended)
Docker packages everything into isolated containers so you don't have to install PostgreSQL or configure complex environments manually on your local machine.

How to start everything:
Open PowerShell in your project root directory (E:\BuildAnAgent\langchain-course-main) and run:

Bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
How your code connects to the database inside Docker:
Your application uses the Docker internal network hostname db:

Python
DATABASE_URL = "postgresql://postgres:venkatpalle@db:5432/agent_db"
How to access your services:

FastAPI Swagger Docs: http://localhost:8000/docs

pgAdmin GUI: http://localhost:5051 (connected via host db, user postgres, password venkatpalle)

Approach 2: Running Directly on Local (Without Docker)
If you choose to run your application directly on your Windows host machine using Python/Miniconda instead of containers, you must run PostgreSQL locally on your machine.

Database setup without Docker:

You must install PostgreSQL natively on Windows and enable the vector extension manually by running:

SQL
CREATE EXTENSION IF NOT EXISTS vector;
How your code connects to the database locally:
Because it's running on your host machine instead of inside Docker's network, you must change the database hostname from db to localhost:

Python
DATABASE_URL = "postgresql://postgres:venkatpalle@localhost:5432/agent_db"
How to start your services locally:

Run FastAPI / Uvicorn manually via terminal:

Bash
uvicorn week_6.planner_excutr:app --reload
Access FastAPI Docs: http://localhost:8000/docs

Run pgAdmin: If installed as a native Windows desktop app, you open it directly from your Windows start menu and connect using host localhost.

docker compose down && docker compose build --no-cache && docker compose up -d

planner-executor-critic-agent
"Write a step-by-step itinerary to explore historical locations in Chennai.",

rag-agent
 "What is covered in Week 3 of the bootcamp?",

DEBUGGING:pgAdmin
"detail": "duplicate key value violates unique constraint \"planner_sessions_pkey\"\nDETAIL:  Key (thread_id)=(planner-session-1) already exists."


// TROUBLESHOOT
if fast api is not opening
run query at agent_db in pgadmin
pgadmin - CREATE EXTENSION IF NOT EXISTS vector;
alternatively, you can run the following command in your terminal to create the vector extension inside your PostgreSQL container:
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;"


if planner-session is not appearing
    Open pgAdmin (http://localhost:5051).

Expand your database (agent_db) -> Schemas -> public -> Tables.

If planner_sessions is missing, open the Query Tool in pgAdmin and run this SQL command:


CREATE TABLE IF NOT EXISTS planner_sessions (
    thread_id VARCHAR(255) PRIMARY KEY,
    goal TEXT,
    plan JSONB,
    execution_history JSONB,
    critique TEXT
);

 docker logs agentic_fastapi_app
  docker logs agentic_fastapi_app --tail 20

That traceback reveals the real issue now: your code is clean of name errors, but PostgreSQL is throwing a ProgrammingError because the vector extension hasn't been enabled in your database yet:    
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedObject) type "vector" does not exist
How to Fix It:
You need to run the SQL command to create the vector extension inside your PostgreSQL container.
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;"  

uv.lck: generation
uv pip compile pyproject.toml --output-file uv.lock

agentic_fastapi_app  | sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedObject) type "vector" does not exist
agentic_fastapi_app  | LINE 5:  embedding VECTOR(3072) NOT NULL,
agentic_fastapi_app  |                    ^
agentic_fastapi_app  |
agentic_fastapi_app  | [SQL:
agentic_fastapi_app  | CREATE TABLE document_chunks (
agentic_fastapi_app  |  id SERIAL NOT NULL,
agentic_fastapi_app  |  content TEXT NOT NULL,
agentic_fastapi_app  |  embedding VECTOR(3072) NOT NULL,
agentic_fastapi_app  |  source_file TEXT,
agentic_fastapi_app  |  PRIMARY KEY (id)
agentic_fastapi_app  | )
agentic_fastapi_app  |
agentic_fastapi_app  | ]
agentic_fastapi_app  | (Background on this error at: https://sqlalche.me/e/20/f405)
postgres_vector_db   |          id SERIAL NOT NULL,
postgres_vector_db   |          content TEXT NOT NULL,
postgres_vector_db   |          embedding VECTOR(3072) NOT NULL,
postgres_vector_db   |          source_file TEXT,
postgres_vector_db   |          PRIMARY KEY (id)

That error happens because you ran docker compose down -v earlier, which wiped out your PostgreSQL database volume. When the database was recreated fresh, the pgvector extension was not enabled inside PostgreSQL yet, so when SQLAlchemy tried to create the document_chunks table with a VECTOR(3072) column, PostgreSQL didn't recognize what VECTOR was.
docker exec -it postgres_vector_db psql -U postgres -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

"""