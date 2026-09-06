# This wires up the FastAPI application, initializes database tables, and registers your routers.

import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.database import engine, Base, SessionLocal
from app.models import chat, documents  # Ensures models register with Base
from app.models.documents import DocumentChunkModel
from app.services.rag_service import ingest_document
from app.routers import chat as chat_router, planner as planner_router

import httpx

# Point to the internal Docker container network for Ollama
OLLAMA_URL = "http://ollama:11434/api/chat"

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Modular Multi-Agent-Worker-API", version="2.0")

# Configure CORS in FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # Allows React (3000) and Streamlit (8501)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Register Existing Routers
app.include_router(chat_router.router)
app.include_router(planner_router.router)

# --- Secure RAG & Guardrail Integration Setup ---
client = OpenAI()

DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres_vector_db:5432/vector_db")
COLLECTION_NAME = "my_docs"

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = PGVector(
    connection_string=DB_CONNECTION,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

template = """Answer the question based only on the following context:
{context}

Question: {input}
"""
prompt = ChatPromptTemplate.from_template(template)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "input": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    status: str

def check_input_guardrails(user_input: str) -> bool:
    """Screens user input for prompt injections, jailbreaks, or violations using Llama Guard 3."""
    try:
        payload = {
            "model": "llama-guard3",
            "messages": [
                {"role": "user", "content": user_input}
            ],
            "stream": False
        }
        
        # Synchronous HTTP call to the local Ollama container
        response = httpx.post(OLLAMA_URL, json=payload, timeout=10.0)
        if response.status_code == 200:
            result = response.json()
            verdict = result.get("message", {}).get("content", "").strip().lower()
            
            # Llama Guard responds with 'safe' if allowed, or 'unsafe\nS2,S5...' if blocked
            is_safe = verdict.startswith("safe")
            return is_safe
        else:
            print(f"Llama Guard warning: Received status {response.status_code}")
            return False # Fail closed for security if model errors out
            
    except Exception as e:
        print(f"Llama Guard connection error: {e}")
        return False # Fail closed on network/connection failure

# Register Secure RAG Endpoint Directly
@app.post("/api/secure-chat", response_model=ChatResponse)
async def secure_chat(payload: ChatRequest):
    try:
        # 1. Run Input Guardrails
        is_safe = check_input_guardrails(payload.query)
        if not is_safe:
            return ChatResponse(
                response="I'm sorry, but I can only answer authorized enterprise knowledge queries.",
                status="blocked_by_guardrail"
            )

        # 2. Execute RAG Chain
        answer = rag_chain.invoke(payload.query)
        return ChatResponse(
            response=answer,
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# -----------------------------------------------

def startup_ingestion_task():
    db = SessionLocal()
    try:
        count = db.query(DocumentChunkModel).count()
        if count == 0:
            print("Database is empty. Automatically ingesting PDF document in background...")
            ingest_document("agentic-ai-developer-bootcamp-curriculum.pdf")
        else:
            print(f"Database already contains {count} chunks. Skipping ingestion.")
    except Exception as e:
        print(f"Startup ingestion note: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event(background_tasks: BackgroundTasks = BackgroundTasks()):
    # Queue PDF ingestion as a background task on startup
    background_tasks.add_task(startup_ingestion_task)

@app.get("/")
def root():
    return {"message": "Modular Agentic FastAPI Backend is running successfully with Secure RAG Rails!"}