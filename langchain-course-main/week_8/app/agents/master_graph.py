# This handles master worker routing.

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from app.agents.workers import AgentState

def create_master_graph(api_key: str, workers: dict):
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

