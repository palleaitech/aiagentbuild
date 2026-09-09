import os
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage

from app.database import get_db
from app.models.chat import ChatSessionModel
from app.agents.workers import create_worker_agent
from app.agents.master_graph import create_master_graph

from langchain_mcp_adapters.client import MultiServerMCPClient

router = APIRouter(prefix="", tags=["Chat"])

master_graph = None

async def initialize_mcp_environment():
    global mcp_client
    server_script_path = str(Path(__file__).resolve().parent.parent.parent / "mcp_server.py")
    
    mcp_client = MultiServerMCPClient({
        "agentic_server": {
            "command": "python",
            "args": [server_script_path],
            "transport": "stdio",
            # 👇 Pass the entire parent process environment (including Docker environment variables)
            "env": dict(os.environ)
        }
    })
    
    mcp_tools = await mcp_client.get_tools()
    # ... rest of your code
    print("🛠️ DISCOVERED MCP TOOLS:", [t.name for t in mcp_tools])
    
    rag_tools = [t for t in mcp_tools if t.name == "search_internal_docs"]
    other_tools = [t for t in mcp_tools if t.name != "search_internal_docs"]

    country_worker = create_worker_agent(other_tools)
    politics_worker = create_worker_agent(other_tools)
    rag_worker = create_worker_agent(
        rag_tools,
        system_prompt=(
            "You are an expert technical and architecture assistant. "
            "MANDATORY RULE: Whenever a user asks about databases, infrastructure, vector embeddings, or technical stacks, "
            "you MUST call the `search_internal_docs` tool first. Never answer technical questions from your own memory."
        )
    )

    workers = {
        "country_worker": country_worker,
        "politics_worker": politics_worker,
        "rag_worker": rag_worker
    }
    return create_master_graph(workers)

class QueryRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = "default-session"

class ChatUpdateRequest(BaseModel):
    new_response: str

@router.post("/chat")
async def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)): 
    global master_graph
    if master_graph is None:
        master_graph = await initialize_mcp_environment()

    config = {"configurable": {"thread_id": request.thread_id}}
    
    # ⚡ MUST use ainvoke so async MCP tools execute correctly via ToolNode
    result = await master_graph.ainvoke({"messages": [HumanMessage(content=request.prompt)]}, config=config)
    
    routed_worker = result.get("next_worker")
    raw_response = result["messages"][-1].content
    
    if isinstance(raw_response, list):
        ai_response = "".join([chunk.get("text", str(chunk)) if isinstance(chunk, dict) else str(chunk) for chunk in raw_response])
    else:
        ai_response = str(raw_response)
    
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