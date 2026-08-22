# This handles standard chat sessions, CRUD operations, and master routing.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage

from app.database import get_db
from app.models.chat import ChatSessionModel
from app.config import OPENAI_API_KEY
from app.agents.tools import get_capital_of_country, get_climate_of_country, get_prime_minister_of_india, search_internal_docs
from app.agents.workers import create_worker_agent
from app.agents.master_graph import create_master_graph

router = APIRouter(prefix="", tags=["Chat"])

# Initialize workers and master graph for chat
country_worker = create_worker_agent(OPENAI_API_KEY, [get_capital_of_country, get_climate_of_country])
politics_worker = create_worker_agent(OPENAI_API_KEY, [get_prime_minister_of_india])
rag_worker = create_worker_agent(OPENAI_API_KEY, [search_internal_docs])

workers = {
    "country_worker": country_worker,
    "politics_worker": politics_worker,
    "rag_worker": rag_worker
}
master_graph = create_master_graph(OPENAI_API_KEY, workers)

class QueryRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = "default-session"

class ChatUpdateRequest(BaseModel):
    new_response: str

@router.post("/chat")
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

@router.get("/chats/{thread_id}")
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

@router.put("/chats/{thread_id}")
def update_chat_session(thread_id: str, request: ChatUpdateRequest, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    session_record.ai_response = request.new_response
    db.commit()
    return {"status": "success", "message": f"Session {thread_id} updated successfully."}

@router.delete("/chats/{thread_id}")
def delete_chat_session(thread_id: str, db: Session = Depends(get_db)):
    session_record = db.query(ChatSessionModel).filter(ChatSessionModel.thread_id == thread_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    db.delete(session_record)
    db.commit()
    return {"status": "success", "message": f"Chat session {thread_id} deleted successfully."}

