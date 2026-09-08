import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from a .env file automatically
load_dotenv()

# LangChain & OpenAI imports
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langgraph.prebuilt import create_react_agent

# Project Database & Routers
from app.database import engine, Base, SessionLocal
from app.models import chat, documents  # Ensures models register with Base
from app.models.documents import DocumentChunkModel
from app.services.rag_service import ingest_document
from app.routers import chat as chat_router, planner as planner_router
from app.core.llm import get_llm

# MCP Architecture Imports
from mcp_client import MCPClientManager
from mcp_bridge import get_langchain_mcp_tools

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Initialize MCP Client Manager instance globally
mcp_client_manager = MCPClientManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Unified application lifecycle manager for MCP subprocess and startup tasks."""
    # 1. Boot up standalone MCP Server process via stdio
    server_path = os.path.abspath("mcp_server.py")
    await mcp_client_manager.connect_to_server(server_path)
    print("🚀 MCP Server connected successfully via stdio!")

    # 2. Run automated background PDF ingestion if database is empty
    try:
        db = SessionLocal()
        count = db.query(DocumentChunkModel).count()
        if count == 0:
            print("Database is empty. Automatically ingesting PDF document...")
            ingest_document("agentic-ai-developer-bootcamp-curriculum.pdf")
        else:
            print(f"Database already contains {count} chunks. Skipping ingestion.")
        db.close()
    except Exception as e:
        print(f"Startup ingestion note: {e}")

    yield

    # 3. Clean shutdown for MCP server subprocess
    await mcp_client_manager.__aexit__(None, None, None)
    print("🛑 MCP Server connection closed.")

app = FastAPI(
    title="Modular Multi-Agent-Worker-API with MCP Host",
    version="2.0",
    lifespan=lifespan
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # React & Streamlit origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register All Domain Routers ---
app.include_router(chat_router.router)
app.include_router(planner_router.router)  # 👈 This registers /run-planner-agent and /resume-planner-agent!

# --- Secure RAG Integration Setup ---
client = OpenAI()

# DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres_vector_db:5432/vector_db")
DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/vector_db")
COLLECTION_NAME = "my_docs"

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = PGVector(
    connection_string=DB_CONNECTION,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

template = """You are an expert AI assistant for the Agentic AI Developer Bootcamp. 
Note: The backend infrastructure for this application uses FastAPI, Docker, LangChain, and PostgreSQL with the pgvector extension for vector embeddings.

Answer the question based on the context below and your system knowledge of the architecture:
{context}

Question: {input}
"""
prompt = ChatPromptTemplate.from_template(template)
rag_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "input": RunnablePassthrough()}
    | prompt
    | rag_llm
    | StrOutputParser()
)

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    status: str

@app.post("/api/secure-chat", response_model=ChatResponse)
async def secure_chat(payload: ChatRequest):
    """Secured chat endpoint leveraging the RAG chain."""
    try:
        answer = rag_chain.invoke(payload.query)
        return ChatResponse(response=answer, status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- MCP Agent Endpoints ---
class AgentQueryRequest(BaseModel):
    prompt: str

@app.post("/api/agent/run")
async def run_agent_workflow(request: AgentQueryRequest):
    """Executes a LangGraph agent that dynamically discovers and uses MCP tools."""
    try:
        # 1. Dynamically fetch latest tools from the MCP server via the bridge
        tools = await get_langchain_mcp_tools(mcp_client_manager)
        
        # 2. Use your project's centralized LLM configuration
        llm = get_llm(tier="reasoning", temperature=0.7)
        
        # 3. Define the strict architectural system prompt
        system_prompt = (
            "You are an expert AI developer assistant for this project. "
            "CRITICAL ARCHITECTURE RULE: When asked about vector databases, embedding storage, or infrastructure, "
            "you must state that the project uses **PostgreSQL with the pgvector extension**. "
            "Ignore any other vector databases (such as FAISS, Pinecone, Milvus, or Weaviate) mentioned in generic curriculum text."
        )
        
        # 4. Create ReAct agent graph with the enforced system prompt
        agent_executor = create_react_agent(
            model=llm, 
            tools=tools, 
            prompt=system_prompt
        )
        
        # 5. Invoke the agent with the user's prompt
        response = await agent_executor.ainvoke({
            "messages": [("user", request.prompt)]
        })
        
        final_message = response["messages"][-1].content
        return {
            "status": "success",
            "prompt": request.prompt,
            "agent_response": final_message,
            "tools_used": [t.name for t in tools]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agent/tools")
async def list_tools():
    """Lists all available tools currently registered in the running MCP server."""
    try:
        tools = await mcp_client_manager.list_available_tools()
        return {"available_tools": [{"name": t.name, "description": t.description} for t in tools]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "Modular Agentic FastAPI Backend is running successfully with RAG, MCP Host & Planners!"}