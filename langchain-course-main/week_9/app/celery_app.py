import os
from celery import Celery
from app.config import DATABASE_URL
from app.agents.planner_graph import create_human_in_the_loop_graph
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
import httpx

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="app.celery_app.run_planner_celery_task")
def run_planner_celery_task(self, thread_id: str, goal: str, city: str, webhook_url: str = None):
    """Celery background execution counterpart to FastAPI BackgroundTasks."""
    print(f"Executing Celery task for thread: {thread_id}")
    try:
        conn = psycopg.connect(DATABASE_URL, autocommit=True)
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()

        # Instantiated cleanly without hardcoded API keys; relies on get_llm() factory inside planner_graph
        planner_app = create_human_in_the_loop_graph(checkpointer=checkpointer)

        initial_state = {
            "messages": [HumanMessage(content=goal)],
            "city": city,
            "next_worker": "",
            "input": goal,
            "plan": [],
            "current_step_index": 0,
            "execution_history": [],
            "critique": "",
            "final_output": ""
        }

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
        planner_app.invoke(initial_state, config=config)
        state = planner_app.get_state(config)

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

        return result_payload
    except Exception as e:
        error_payload = {"status": "error", "thread_id": thread_id, "detail": str(e)}
        if webhook_url:
            with httpx.Client() as client:
                client.post(webhook_url, json=error_payload, timeout=10.0)
        raise e