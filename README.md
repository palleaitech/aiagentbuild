uv pip install -r requirements.txt
langchain: The core framework providing standardized abstractions for models, prompts, and agent architectures

langchain: This package is the entry point. It contains the high-level create_agent harness and the abstractions you need to define tools, prompts, and connect to models.

langchain-core: This is automatically pulled in. It contains the foundational "bricks" (the interfaces for LLMs, chat models, and the standard message schemas) that all agentic logic relies on.

langchain-openai (or your specific model provider): Required to integrate with LLMs like GPT-4o
Model Integration: You won't have the specialized code to talk to OpenAI, Anthropic, or Google Gemini. You will need to install the specific provider package later (e.g., pip install langchain-openai)

langchain-community: Contains various third-party integrations and utility tools.



Use uv init. It will set up your project structure, pyproject.toml, and handle your environment and dependencies automatically.
langchain-core: While langchain depends on it, explicitly including it is a best practice. It contains the base abstractions (like Runnable and LCEL) that power the entire ecosystem and ensures version compatibility across your integrations.

How LangSmith Works in Your Architecture
Automatic Tracing: Because your master router, worker nodes, and planner-executor-critic loops are built using LangGraph, every API call to /chat or /run-planner-agent automatically sends deep execution traces to your LangSmith dashboard.

Debugging Interrupts & Human-in-the-Loop: When your planner pauses at an interrupt() node awaiting human approval, LangSmith lets you inspect the exact state snapshot, memory thread ID, and input payloads leading right up to the interruption.

Latency & Token Tracking: You can monitor token usage across your dynamic multi-provider LLM factory (OpenAI vs. Gemini tiers) and track how long individual worker node routing takes.
