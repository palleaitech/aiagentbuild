import streamlit as st
import requests
import time

# FastAPI Backend URL
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Multi-Agent AI Studio", page_icon="🤖", layout="wide")

st.title("🤖 Modular Multi-Agent & Planner Studio")
st.sidebar.title("Navigation")
app_mode = st.sidebar.selectbox("Choose Mode", ["Master-Worker Chat", "Planner-Executor-Critic (HitL)"])

# -------------------------------------------------------------
# MODE 1: MASTER-WORKER CHAT
# -------------------------------------------------------------
if app_mode == "Master-Worker Chat":
    st.header("💬 Master-Worker Intelligent Chat")
    st.markdown("Ask general questions, country details, political facts, or internal curriculum documents. The Master agent will automatically route your request to the correct worker.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input chat box
    user_query = st.chat_input("Type your message here...")
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Master agent is routing and thinking..."):
                try:
                    # Calls your FastAPI chat endpoint
                    response = requests.post(f"{BACKEND_URL}/chat", json={"prompt": user_query}, timeout=30)
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

    # Initialize session states for thread management
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "planner_status" not in st.session_state:
        st.session_state.planner_status = "idle"
    if "current_plan" not in st.session_state:
        st.session_state.current_plan = []

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
                    
                    # Give background task a moment to hit the interrupt state
                    time.sleep(2.5)
                    
                    # Fetch state or simulate review pause
                    st.info("Task is now paused at the Human Approval node awaiting review.")
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

    # If task is paused, show approval interface
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
                            result_data = res.json()
                            st.success("Workflow completed successfully!")
                            
                            st.markdown("### 📝 Final Execution Report")
                            
                            # Extract result content and format nicely as human-readable markdown
                            result_content = result_data.get("result", {})
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
                                else:
                                    messages = result_content.get("messages", [])
                                    for msg in messages:
                                        content = msg.get("content", "")
                                        if content and len(content.strip()) > 10:
                                            st.markdown(content)
                            else:
                                st.write(str(result_content))
                                
                            st.session_state.planner_status = "completed"
                        else:
                            st.error(f"Failed to resume: {res.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col2:
            if st.button("🔄 Reset Workflow"):
                st.session_state.thread_id = None
                st.session_state.planner_status = "idle"
                st.session_state.current_plan = []
                st.rerun()