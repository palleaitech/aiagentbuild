# This handles starting and resuming your long-running planner graph workflows using PostgresSaver

import uuid
import traceback
import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
from app.celery_app import run_planner_celery_task

from app.config import OPENAI_API_KEY, DATABASE_URL
from app.agents.planner_graph import create_human_in_the_loop_graph

router = APIRouter(prefix="", tags=["Planner Agent"])

# Setup Postgres checkpointer with autocommit=True for DDL safety
conn = psycopg.connect(DATABASE_URL, autocommit=True)
checkpointer = PostgresSaver(conn)
checkpointer.setup()

planner_app = create_human_in_the_loop_graph(api_key=OPENAI_API_KEY, checkpointer=checkpointer)

class TaskRequest(BaseModel):
    goal: str
    city: Optional[str] = "Chennai"
    webhook_url: Optional[str] = None
    execution_engine: Optional[str] = "background"  # 👈 Choose between "background" or "celery"

class ResumeRequest(BaseModel):
    thread_id: str
    updated_plan: Optional[List[str]] = None

def run_planner_in_background(thread_id: str, initial_state: dict, webhook_url: Optional[str] = None):
    """Executes the planner graph asynchronously and fires a webhook on completion."""
    try:
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
        planner_app.invoke(initial_state, config=config)
        state = planner_app.get_state(config)
        
        # Safely handle state values without serialization errors
        safe_messages = []
        if state.values and "messages" in state.values:
            for msg in state.values["messages"]:
                content = getattr(msg, "content", str(msg))
                safe_messages.append({"type": getattr(msg, "type", "unknown"), "content": content})

        safe_values = state.values.copy() if state.values else {}
        safe_values["messages"] = safe_messages

        result_payload = {
            "status": "paused_for_approval" if state.next else "completed",
            "thread_id": thread_id,
            "next_step": state.next,
            "result": safe_values
        }

        if webhook_url:
            with httpx.Client() as client:
                client.post(webhook_url, json=result_payload, timeout=10.0)
                print(f"Webhook successfully sent to {webhook_url}")
                
    except Exception as e:
        error_payload = {"status": "error", "thread_id": thread_id, "detail": str(e)}
        print(f"Background planner task failed: {e}")
        if webhook_url:
            try:
                with httpx.Client() as client:
                    client.post(webhook_url, json=error_payload, timeout=10.0)
            except Exception as webhook_err:
                print(f"Failed to deliver error webhook: {webhook_err}")


@router.post("/run-planner-agent")
async def run_planner_agent(request: TaskRequest, background_tasks: BackgroundTasks):
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

        # 🔀 Pluggable Routing based on user choice
        if request.execution_engine == "celery":
            task = run_planner_celery_task.delay(
                thread_id=thread_id, 
                goal=request.goal, 
                city=request.city, 
                webhook_url=request.webhook_url
            )
            return {
                "status": "queued_via_celery",
                "task_id": task.id,
                "thread_id": thread_id,
                "message": "Task handed off to Redis/Celery worker cluster."
            }
        else:
            # Fallback to your working FastAPI BackgroundTasks
            background_tasks.add_task(
                run_planner_in_background,
                thread_id=thread_id,
                initial_state=initial_state,
                webhook_url=request.webhook_url
            )
            return {
                "status": "accepted_via_background_tasks",
                "thread_id": thread_id,
                "message": "Task running in local FastAPI background thread."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume-planner-agent")
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

    