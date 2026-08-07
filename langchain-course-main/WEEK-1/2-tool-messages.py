from email.mime import message

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

#llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

print("================================BINDING TOOLS WITH LLM ============================================")

# -------------------------------
# 1. Define tools (no LLM calls inside)
# -------------------------------
@tool
def get_prime_minister_of_india_bindingLLM() -> str:
    """Return the current Prime Minister of India."""
    # Pure function: returns static data
    return "Narendra Modi"

@tool
def get_capital_of_country_bindingLLM(country: str) -> str:
    """Return the capital of a given country."""
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

@tool
def get_climate_of_country_bindingLLM(country: str) -> str:
    """Return the climate of a given country."""
    climates = {"india": "Tropical monsoon", "france": "Temperate"}
    return climates.get(country.lower(), "Unknown")

# -------------------------------
# 2. Collect tools and build a lookup map
# -------------------------------
toolsbindingLLM = [
    get_prime_minister_of_india_bindingLLM,
    get_capital_of_country_bindingLLM,
    get_climate_of_country_bindingLLM
]

# Map tool name → tool function, so we can execute them later
tools_map = {tool.name: tool for tool in toolsbindingLLM}

# -------------------------------
# 3. Bind tools to the LLM
# -------------------------------
llm_openai = ChatOpenAI(
    model_name="gpt-4o",
    temperature=0.7,
    openai_api_key=api_key
).bind_tools(toolsbindingLLM)

# -------------------------------
# 4. Prompts list (questions to ask)
# -------------------------------
prompts = [
    "Who is the current Prime Minister of India?",
    "What is the capital of France?",
    "What is the climate in India?"
]

# -------------------------------
# 5. Main loop: ask each prompt
# -------------------------------
for prompt in prompts:
    # Build conversation history
    messages = [
        SystemMessage(content="You are a helpful assistant. Always include tool results in your final answer."),
        HumanMessage(content=prompt)
    ]

    # -------------------------------
    # First invocation: LLM decides which tool to call
    # -------------------------------
    response = llm_openai.invoke(messages)
    print(f"Prompt: {prompt}")

    # -------------------------------
    # If the LLM responded with a tool call
    # -------------------------------
    if response.tool_calls:
        # Add the tool call into the conversation history
        messages.append(response)

        # Execute each tool call requested
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]   # Which tool
            tool_args = tool_call["args"]   # Arguments
            tool_id = tool_call["id"]       # Unique ID

            # Run the actual Python function
            tool_to_run = tools_map[tool_name]
            tool_output = tool_to_run.invoke(tool_args)

            # Append tool result back into history
            messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))
            print(f"ToolMessage: {messages[-1].content}")
            print(f"AIMessage: content='{messages[-1].content}', tool_calls={getattr(messages[-1], 'tool_calls', None)}")
            # -------------------------------
            # Second invocation: feed tool result back to LLM
            # -------------------------------
            final_response = llm_openai.invoke(messages)

            # Now the LLM generates a natural language answer
            print(f"LLM Response: {final_response.content}\n")

    else:
        # If no tool was needed, just print the direct answer
        print(f"LLM Response: {response.content}\n")

    print("===================================================================================================\n")
    print("Whole Messages: ", messages)
    print("===================================================================================================\n")
    