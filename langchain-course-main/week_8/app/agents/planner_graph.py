# This houses your multi-step Planner-Executor-Critic graph, human approval interrupt node, and the custom evaluation node.

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
# from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from app.agents.workers import AgentState
from app.core.llm import get_llm

llm = get_llm(tier="reasoning", temperature=0.7)

def human_approval_node(state: AgentState):
    human_decision = interrupt({
        "plan": state.get("plan"),
        "message": "Please review the plan. Resume with 'approved' or provide an updated list of steps."
    })
    
    updated_plan = human_decision if isinstance(human_decision, list) and len(human_decision) > 0 else state.get("plan", [])
    
    return Command(
        update={"plan": updated_plan},
        goto="executor"
    )

def create_human_in_the_loop_graph(checkpointer):
    def planner_node(state: AgentState):
        messages = state.get("messages", [])
        user_prompt = messages[-1].content if messages else state.get("input", "Perform the task.")
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert travel and research planner. Break down the user's request into a comprehensive, detailed sequential list of 8 to 12 granular steps covering all days, hubs, and food locations."),
            ("user", "Goal: {input}")
        ])
        chain = prompt | llm
        response = chain.invoke({"input": user_prompt})
        steps = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
        return {
            "input": user_prompt,
            "plan": steps, 
            "current_step_index": 0,
            "messages": [HumanMessage(content=f"Plan created with {len(steps)} steps.")]
        }

    def executor_node(state: AgentState):
        current_index = state["current_step_index"]
        current_step = state["plan"][current_index] if current_index < len(state["plan"]) else "Finalize itinerary"
        critique = state.get("critique", "")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a precise executor. Execute the current step. If there is critique/feedback from the critic, fix and adjust your output accordingly."),
            ("user", "Goal: {input}\nPlan: {plan}\nCurrent Step Index: {index}\nCurrent Step: {step}\nCritic Feedback: {critique}\nHistory: {history}")
        ])
        chain = prompt | llm
        response = chain.invoke({
            "input": state["input"],
            "plan": state["plan"],
            "index": current_index,
            "step": current_step,
            "critique": critique,
            "history": state["execution_history"]
        })
        result = f"{current_step} | Output: {response.content}"
        return {"execution_history": [result]}

    def critic_node(state: AgentState):
        history = state.get("execution_history", [])
        if not history:
            return {"critique": "APPROVED", "current_step_index": state.get("current_step_index", 0)}
        
        latest_execution = history[-1]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a strict quality control critic. Evaluate if the latest execution step successfully accomplished its goal. Reply with 'APPROVED' if good, or provide feedback for correction."),
            ("user", "Goal: {input}\nLatest Execution: {execution}")
        ])
        chain = prompt | llm
        response = chain.invoke({
            "input": state.get("input", ""),
            "execution": latest_execution
        })
        critique = response.content.strip()
        current_index = state.get("current_step_index", 0)
        next_index = current_index + 1 if "APPROVED" in critique.upper() else current_index
        return {"critique": critique, "current_step_index": next_index}

    def should_continue(state):
        current_index = state.get("current_step_index", 0)
        plan = state.get("plan", [])
        if current_index >= len(plan):
            return "finish"
        return "continue"

    def evaluation_node(state: AgentState):
        user_prompt = state.get("input", "")
        history = state.get("execution_history", [])
        final_summary = "\n".join(history) if history else "No execution history recorded."

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an objective AI response evaluator. Grade the execution history on a scale of 1-5 for accuracy, completeness, and helpfulness. Format your output as: SCORE: [1-5] | RATIONALE: [your brief note]"),
            ("user", "Original Goal: {prompt}\nExecution History:\n{history}")
        ])
        
        chain = prompt | llm
        evaluation_result = chain.invoke({"prompt": user_prompt, "history": final_summary})
        
        print(f"\n--- PLANNER EVALUATION REPORT ---\n{evaluation_result.content}\n-----------------------------------\n")
        
        return {"critique": evaluation_result.content}

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("evaluator", evaluation_node)
    
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "human_approval")
    graph.add_edge("human_approval", "executor")
    graph.add_edge("executor", "critic")
    graph.add_conditional_edges("critic", should_continue, {"continue": "executor", "finish": "evaluator"})
    graph.add_edge("evaluator", END)

    return graph.compile(checkpointer=checkpointer)

