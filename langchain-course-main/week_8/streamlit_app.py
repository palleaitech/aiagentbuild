import streamlit as st
import requests
import time
import os

# FastAPI Backend URL
# Read from environment variable set in docker-compose, falling back to localhost if run outside Docker
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Set page config ONCE at the very top
st.set_page_config(page_title="Multi-Agent AI Studio", page_icon="🤖", layout="wide")

st.sidebar.title("Navigation")
app_mode = st.sidebar.selectbox(
    "Choose Mode", 
    [
        "Master-Worker Chat", 
        "Planner-Executor-Critic (HitL)", 
        "Secure Knowledge RAG (Guardrails)"
    ]
)

# -------------------------------------------------------------
# MODE 1: MASTER-WORKER CHAT
# -------------------------------------------------------------
if app_mode == "Master-Worker Chat":
    st.header("💬 Master-Worker Intelligent Chat")
    st.markdown("Ask general questions, country details, political facts, or internal curriculum documents. The Master agent will automatically route your request to the correct worker.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if st.sidebar.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_query = st.chat_input("Type your message here...")
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Master agent is routing and thinking..."):
                try:
                    response = requests.post(f"{BACKEND_URL}/chat", json={"prompt": user_query}, timeout=120)
                    if response.status_code == 200:
                        data = response.json()
                        reply = data.get("response", "No response content.")
                        worker = data.get("routed_worker", "unknown")
                        
                        full_response = f"**[Routed to: `{worker}`]**\n\n{reply}"
                        st.markdown(full_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": full_response})
                    else:
                        st.error(f"Error from server: {response.text}")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

# -------------------------------------------------------------
# MODE 2: PLANNER-EXECUTOR-CRITIC WITH HUMAN APPROVAL
# -------------------------------------------------------------
elif app_mode == "Planner-Executor-Critic (HitL)":
    st.header("📋 Multi-Step Planner & Human Approval Studio")
    st.markdown("Submit a high-level goal. The Planner will break it down, pause for your review, and let you resume execution.")

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "planner_status" not in st.session_state:
        st.session_state.planner_status = "idle"
    if "current_plan" not in st.session_state:
        st.session_state.current_plan = []
    if "result_data" not in st.session_state:
        st.session_state.result_data = None

    goal_input = st.text_input("Enter your complex goal:", "Plan a 3-day itinerary for Chennai focusing on tech hubs and local food.")
    execution_engine = st.selectbox("Execution Engine", ["background", "celery"])

    if st.button("🚀 Start Planner Agent"):
        with st.spinner("Initializing workflow and generating plan..."):
            try:
                payload = {
                    "goal": goal_input,
                    "city": "Chennai",
                    "execution_engine": execution_engine
                }
                res = requests.post(f"{BACKEND_URL}/run-planner-agent", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.thread_id = data.get("thread_id")
                    st.success(f"Task started successfully! Thread ID: `{st.session_state.thread_id}`")
                    
                    time.sleep(2.5)
                    
                    st.session_state.planner_status = "paused_for_approval"
                    st.session_state.current_plan = [
                        "Step 1: Research major IT parks in Taramani and OMR.",
                        "Step 2: Identify famous authentic Chettinad and Biryani spots.",
                        "Step 3: Structure a balanced 3-day timeline."
                    ]
                    st.rerun()
                else:
                    st.error(f"Failed to start planner: {res.text}")
            except Exception as e:
                st.error(f"Error connecting to backend: {e}")

    if st.session_state.thread_id and st.session_state.planner_status == "paused_for_approval":
        st.markdown("---")
        st.subheader("🛑 Action Required: Review Generated Plan")
        st.write(f"Active Thread ID: `{st.session_state.thread_id}`")

        edited_plan = []
        for i, step in enumerate(st.session_state.current_plan):
            edited_step = st.text_input(f"Step {i+1}", step, key=f"step_{i}")
            edited_plan.append(edited_step)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve & Resume Execution"):
                with st.spinner("Resuming graph execution from PostgreSQL checkpointer..."):
                    try:
                        resume_payload = {
                            "thread_id": st.session_state.thread_id,
                            "updated_plan": edited_plan
                        }
                        res = requests.post(f"{BACKEND_URL}/resume-planner-agent", json=resume_payload)
                        if res.status_code in [200, 201]:
                            st.session_state.result_data = res.json()
                            st.session_state.planner_status = "completed"
                            st.rerun()
                        else:
                            st.error(f"Failed to resume: {res.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col2:
            if st.button("🔄 Reset Workflow"):
                st.session_state.thread_id = None
                st.session_state.planner_status = "idle"
                st.session_state.current_plan = []
                st.session_state.result_data = None
                st.rerun()

    if st.session_state.planner_status == "completed" and st.session_state.result_data:
        st.success("Workflow completed successfully!")
        st.markdown("### 📝 Final Execution Report")
        
        result_content = st.session_state.result_data.get("result", {})
        if isinstance(result_content, dict):
            plan_steps = result_content.get("plan", [])
            if plan_steps:
                st.markdown("#### 🗺️ Final Approved Plan")
                for step in plan_steps:
                    st.markdown(f"- {step}")
                st.markdown("---")
            
            exec_history = result_content.get("execution_history", [])
            if exec_history:
                st.markdown("#### 🔍 Execution & Research Findings")
                for item in exec_history:
                    st.markdown(f"> {item}")
        
        if st.button("🔄 Start New Plan"):
            st.session_state.thread_id = None
            st.session_state.planner_status = "idle"
            st.session_state.current_plan = []
            st.session_state.result_data = None
            st.rerun()

# -------------------------------------------------------------
# MODE 3: SECURE KNOWLEDGE RAG (GUARDRAILS)
# -------------------------------------------------------------
elif app_mode == "Secure Knowledge RAG (Guardrails)":
    st.header("🔒 Secure Knowledge Assistant")
    st.markdown("Ask questions grounded in our verified documentation, protected by runtime guardrails.")

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    for message in st.session_state.rag_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if rag_prompt := st.chat_input("Type your question here..."):
        st.session_state.rag_messages.append({"role": "user", "content": rag_prompt})
        with st.chat_message("user"):
            st.markdown(rag_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing request and checking security rails..."):
                try:
                    api_url = f"{BACKEND_URL}/api/secure-chat"
                    response = requests.post(api_url, json={"query": rag_prompt}, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("response")
                        status = data.get("status")
                        
                        st.markdown(answer)
                        
                        if status == "blocked_by_guardrail":
                            st.caption("🛡️ *Note: This query was intercepted and blocked by the security guardrail.*")
                            
                        st.session_state.rag_messages.append({"role": "assistant", "content": answer})
                    else:
                        st.error(f"Server returned status code {response.status_code}")
                except Exception as e:
                    st.error(f"Failed to connect to backend service: {e}")