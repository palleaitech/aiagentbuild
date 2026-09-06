# This wires up the FastAPI application, initializes database tables, and registers your routers.

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import chat, documents  # Ensures models register with Base
from app.models.documents import DocumentChunkModel
from app.services.rag_service import ingest_document
from app.routers import chat as chat_router, planner as planner_router

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

# Register Routers
app.include_router(chat_router.router)
app.include_router(planner_router.router)

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
    return {"message": "Modular Agentic FastAPI Backend is running successfully!"}