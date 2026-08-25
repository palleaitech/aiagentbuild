# This defines your worker agents (country_worker, politics_worker, rag_worker).

from typing import TypedDict, Annotated, List
import operator
from langchain_core.messages import BaseMessage
#from langchain_openai import ChatOpenAI
# Ensure you are importing your actual custom tools correctly, e.g.:
from app.agents.tools import search_internal_docs
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from app.core.llm import get_llm

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

def create_worker_agent(tools):
    # Use summarization tier (or reasoning if tool execution requires strict OpenAI JSON-calling)
    llm_openai = get_llm(tier="summarization", temperature=0.7).bind_tools(tools)

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

