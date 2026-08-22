# This handles starting and resuming your long-running planner graph workflows using PostgresSaver

import uuid
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg

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

class ResumeRequest(BaseModel):
    thread_id: str
    updated_plan: Optional[List[str]] = None

@router.post("/run-planner-agent")
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

    